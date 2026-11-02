import { useMemo, useRef, useState, type DragEvent } from "react";
import { useSearchParams } from "react-router-dom";
import {
  ChevronDown, FileStack, FolderUp, MoreHorizontal, Play, RefreshCw, Search, Trash2, UploadCloud, Eye, FilePlus2,
} from "lucide-react";
import { api } from "../lib/api";
import { useApp, useProject } from "../lib/state";
import type { IssuerFile } from "../lib/types";
import { bytes, cn, FORMAT_LABEL, num } from "../lib/utils";
import { Page } from "../components/ProjectShell";
import { FileIcon } from "../components/FileIcon";
import { FileStatusChip } from "../components/StatusChip";
import { FileDrawer } from "../components/FileDrawer";
import { Badge, Button, Card, EmptyState, Input, Menu, PageHeader, Progress, Segmented, Switch, Tooltip, useToast } from "../components/ui";

const ACCEPT = ".pdf,.docx,.xlsx,.xlsm,.png,.jpg,.jpeg,.tif,.tiff,.bmp,.txt,.md,.csv";
type Pending = { file: File; path: string };

async function walkEntry(entry: FileSystemEntry, prefix = ""): Promise<Pending[]> {
  if (entry.isFile) {
    return new Promise((res) => (entry as FileSystemFileEntry).file((f) => res([{ file: f, path: prefix + f.name }]), () => res([])));
  }
  if (entry.isDirectory) {
    const reader = (entry as FileSystemDirectoryEntry).createReader();
    const all: FileSystemEntry[] = [];
    await new Promise<void>((done) => {
      const read = () => reader.readEntries((batch) => { if (!batch.length) return done(); all.push(...batch); read(); }, () => done());
      read();
    });
    const nested = await Promise.all(all.map((e) => walkEntry(e, `${prefix}${entry.name}/`)));
    return nested.flat();
  }
  return [];
}

function uploadWithProgress(pid: string, items: Pending[], onProgress: (f: number) => void) {
  return new Promise<{ added: IssuerFile[]; rejected: { name: string; reason: string }[] }>((resolve, reject) => {
    const fd = new FormData();
    items.forEach(({ file, path }) => { fd.append("files", file, file.name); fd.append("paths", path); });
    const xhr = new XMLHttpRequest();
    xhr.open("POST", `/api/projects/${pid}/files`);
    xhr.upload.onprogress = (e) => e.lengthComputable && onProgress(e.loaded / e.total);
    xhr.onload = () => (xhr.status < 300 ? resolve(JSON.parse(xhr.responseText)) : reject(new Error(xhr.responseText || xhr.statusText)));
    xhr.onerror = () => reject(new Error("Upload failed: the drafting service did not respond."));
    xhr.send(fd);
  });
}

export default function DocumentsPage() {
  const { project, refresh, startJob, job } = useProject();
  const { meta, health } = useApp();
  const toast = useToast();
  const [params, setParams] = useSearchParams();
  const openFid = params.get("file");
  const [drag, setDrag] = useState(false);
  const [upload, setUpload] = useState<{ n: number; frac: number } | null>(null);
  const [auto, setAuto] = useState(true);
  const [q, setQ] = useState("");
  const [status, setStatus] = useState<"all" | "attention" | "queued">("all");
  const [collapsed, setCollapsed] = useState<Record<string, boolean>>({});
  const filesInput = useRef<HTMLInputElement>(null);
  const folderInput = useRef<HTMLInputElement>(null);

  const pid = project?.id ?? "";
  const files = project?.files ?? [];
  const processing = job?.kind === "process" && job.status === "running";
  const queued = files.filter((f) => f.status === "queued" || f.status === "failed");
  const attention = (f: IssuerFile) => f.status === "failed" || !!f.needs_ocr_pages || (f.status === "processed" && f.doc_type === "other");

  const doUpload = async (items: Pending[]) => {
    const ok = items.filter((i) => ACCEPT.split(",").some((ext) => i.file.name.toLowerCase().endsWith(ext)));
    const skipped = items.length - ok.length;
    if (!ok.length) {
      toast("error", "No supported files", "Supported: PDF, Word (.docx), Excel (.xlsx), images and text.");
      return;
    }
    setUpload({ n: ok.length, frac: 0 });
    try {
      const res = await uploadWithProgress(pid, ok, (frac) => setUpload({ n: ok.length, frac }));
      await refresh();
      const rej = res.rejected.length + skipped;
      toast("success", `Uploaded ${res.added.length} file${res.added.length === 1 ? "" : "s"}`, rej ? `${rej} skipped (unsupported type or too large)` : undefined);
      if (auto && res.added.length && !processing) {
        try { startJob(await api.process(pid, { file_ids: res.added.map((f) => f.id) })); } catch (e) { toast("error", "Could not start processing", (e as Error).message); }
      }
    } catch (e) {
      toast("error", "Upload failed", (e as Error).message);
    } finally {
      setUpload(null);
    }
  };

  const onDrop = async (e: DragEvent) => {
    e.preventDefault();
    setDrag(false);
    const entries = [...e.dataTransfer.items].map((i) => i.webkitGetAsEntry?.()).filter(Boolean) as FileSystemEntry[];
    if (entries.length) doUpload((await Promise.all(entries.map((en) => walkEntry(en)))).flat());
    else doUpload([...e.dataTransfer.files].map((f) => ({ file: f, path: f.name })));
  };

  const onPick = (list: FileList | null) => {
    if (!list) return;
    doUpload([...list].map((f) => ({ file: f, path: (f as File & { webkitRelativePath?: string }).webkitRelativePath || f.name })));
  };

  const processAll = async (force = false) => {
    try { startJob(await api.process(pid, { force })); } catch (e) { toast("error", "Could not start processing", (e as Error).message); }
  };

  const shown = files.filter((f) =>
    (!q || `${f.name} ${f.doc_label} ${f.folder}`.toLowerCase().includes(q.toLowerCase())) &&
    (status === "all" || (status === "attention" ? attention(f) : f.status === "queued")),
  );
  const byCat = useMemo(() => {
    const order = meta?.categories ?? [];
    const m = new Map<string, IssuerFile[]>();
    order.forEach((c) => m.set(c, []));
    shown.forEach((f) => { if (!m.has(f.category)) m.set(f.category, []); m.get(f.category)!.push(f); });
    return [...m.entries()].filter(([, v]) => v.length);
  }, [shown, meta]);

  const totals = {
    processed: files.filter((f) => f.status === "processed").length,
    pages: files.reduce((a, f) => a + (f.pages || 0), 0),
    attention: files.filter(attention).length,
  };

  return (
    <Page>
      <PageHeader
        eyebrow="Step 1 · Inputs"
        title="Issuer documents"
        description="Upload the files the issuer gave the lead manager. Each file is read with its page or cell kept, classified by type, and its facts extracted."
        actions={
          files.length > 0 && (
            <>
              <Menu
                trigger={<Button variant="secondary" icon={<MoreHorizontal className="h-4 w-4" />}>More</Button>}
                items={[{ label: "Reprocess all files", icon: <RefreshCw />, onClick: () => processAll(true), disabled: processing }]}
              />
              <Button variant="primary" icon={<Play className="h-4 w-4" />} onClick={() => processAll(false)} disabled={!queued.length || processing} loading={processing}>
                {processing ? "Processing…" : queued.length ? `Process ${queued.length} file${queued.length > 1 ? "s" : ""}` : "All processed"}
              </Button>
            </>
          )
        }
      />

      <div
        onDragOver={(e) => { e.preventDefault(); setDrag(true); }}
        onDragLeave={(e) => { if (e.currentTarget === e.target) setDrag(false); }}
        onDrop={onDrop}
        className={cn(
          "relative rounded-xl border-2 border-dashed transition-colors",
          drag ? "border-primary bg-primary-soft/50" : "border-border-strong bg-surface",
          files.length ? "px-6 py-5" : "px-6 py-14",
        )}
      >
        <div className={cn("flex items-center gap-5", files.length ? "flex-row" : "flex-col text-center")}>
          <div className={cn("flex shrink-0 items-center justify-center rounded-xl bg-primary-soft text-primary", files.length ? "h-11 w-11" : "h-14 w-14")}>
            <UploadCloud className={files.length ? "h-5 w-5" : "h-6 w-6"} />
          </div>
          <div className="min-w-0 flex-1">
            <div className="text-sm font-semibold text-fg">{drag ? "Drop to upload" : "Drag files or a whole folder here"}</div>
            <div className="mt-0.5 text-xs text-fg-muted">PDF (digital or scanned), Word .docx, Excel .xlsx, JPG / PNG / TIFF images · up to 200 MB per file</div>
            {upload && (
              <div className="mt-3 max-w-md">
                <div className="mb-1 flex justify-between text-2xs text-fg-subtle"><span>Uploading {upload.n} file(s)…</span><span className="tabular">{Math.round(upload.frac * 100)}%</span></div>
                <Progress value={upload.frac} />
              </div>
            )}
          </div>
          <div className={cn("flex items-center gap-2", !files.length && "mt-1")}>
            <Button icon={<FilePlus2 className="h-4 w-4" />} onClick={() => filesInput.current?.click()} disabled={!!upload}>Add files</Button>
            <Button icon={<FolderUp className="h-4 w-4" />} onClick={() => folderInput.current?.click()} disabled={!!upload}>Add folder</Button>
          </div>
        </div>
        <div className={cn("flex items-center gap-2 text-xs text-fg-muted", files.length ? "mt-4 border-t border-border pt-3" : "mt-6 justify-center")}>
          <Switch checked={auto} onChange={setAuto} label="Process after upload" />
          <span>Read and extract automatically after upload</span>
          {health && !health.ocr_available && <Badge tone="warning" className="ml-2">OCR not installed: scanned pages will be skipped</Badge>}
        </div>
        <input ref={filesInput} type="file" multiple accept={ACCEPT} className="hidden" onChange={(e) => { onPick(e.target.files); e.target.value = ""; }} />
        <input ref={folderInput} type="file" multiple className="hidden" {...({ webkitdirectory: "", directory: "" } as object)} onChange={(e) => { onPick(e.target.files); e.target.value = ""; }} />
      </div>

      {files.length > 0 && (
        <>
          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2">
              <Input icon={<Search className="h-4 w-4" />} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search files" className="w-64" />
              <Segmented
                size="sm"
                value={status}
                onChange={setStatus}
                options={[
                  { value: "all", label: `All ${files.length}` },
                  { value: "attention", label: `Needs attention ${totals.attention}` },
                  { value: "queued", label: `Queued ${files.filter((f) => f.status === "queued").length}` },
                ]}
              />
            </div>
            <div className="text-xs text-fg-subtle tabular">
              {totals.processed} of {files.length} read · {num(totals.pages)} pages · {num(project?.stats.facts ?? 0)} facts
            </div>
          </div>

          <Card className="mt-3 overflow-hidden">
            <table className="w-full table-fixed text-[13px]">
              <colgroup>
                <col className="w-[38%]" /><col className="w-[22%]" /><col className="w-[11%]" /><col className="w-[7%]" /><col className="w-[7%]" /><col className="w-[12%]" /><col className="w-12" />
              </colgroup>
              <thead>
                <tr className="border-b border-border bg-subtle/60 text-left text-2xs font-medium uppercase tracking-wider text-fg-subtle">
                  <th className="py-2 pl-4 pr-3 font-medium">File</th>
                  <th className="px-3 py-2 font-medium">Document type</th>
                  <th className="px-3 py-2 font-medium">Format</th>
                  <th className="px-3 py-2 text-right font-medium">Pages</th>
                  <th className="px-3 py-2 text-right font-medium">Facts</th>
                  <th className="px-3 py-2 font-medium">Status</th>
                  <th className="w-10 py-2 pr-3" />
                </tr>
              </thead>
              {byCat.map(([cat, list]) => (
                <tbody key={cat}>
                  <tr className="border-b border-border bg-subtle/30">
                    <td colSpan={7} className="py-1.5 pl-4">
                      <button className="flex items-center gap-1.5 text-xs font-semibold text-fg-muted hover:text-fg" onClick={() => setCollapsed((c) => ({ ...c, [cat]: !c[cat] }))}>
                        <ChevronDown className={cn("h-3.5 w-3.5 transition-transform", collapsed[cat] && "-rotate-90")} />
                        {cat}
                        <span className="font-normal text-fg-subtle">· {list.length}</span>
                      </button>
                    </td>
                  </tr>
                  {!collapsed[cat] && list.map((f) => (
                    <tr key={f.id} className="group cursor-pointer border-b border-border/70 transition-colors last:border-0 hover:bg-subtle/60" onClick={() => setParams({ file: f.id })}>
                      <td className="max-w-0 py-2 pl-4 pr-3">
                        <div className="flex items-center gap-3">
                          <FileIcon format={f.format} />
                          <div className="min-w-0">
                            <div className="truncate font-medium text-fg" title={f.name}>{f.name}</div>
                            <div className="truncate text-2xs text-fg-subtle">{f.folder ? `${f.folder} · ` : ""}{bytes(f.size)}</div>
                          </div>
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex items-center gap-1.5">
                          <span className={cn("truncate", f.doc_type === "other" ? "text-warning" : "text-fg")}>{f.doc_label}</span>
                          {!f.doc_type_locked && f.status === "processed" && f.confidence < 0.8 && (
                            <Tooltip content="Low-confidence classification. Open the file to confirm."><span className="h-1.5 w-1.5 rounded-full bg-warning" /></Tooltip>
                          )}
                        </div>
                      </td>
                      <td className="px-3 py-2 text-fg-muted">{f.status !== "processed" && f.format === "pdf" ? "PDF" : FORMAT_LABEL[f.format] ?? f.format}</td>
                      <td className="px-3 py-2 text-right tabular text-fg-muted">{f.pages ?? "–"}</td>
                      <td className="px-3 py-2 text-right tabular text-fg-muted">{f.facts ?? "–"}</td>
                      <td className="px-3 py-2"><FileStatusChip f={f} /></td>
                      <td className="py-2 pr-3 text-right" onClick={(e) => e.stopPropagation()}>
                        <Menu
                          trigger={<Button variant="ghost" size="icon-sm" className="opacity-0 group-hover:opacity-100" aria-label="File actions"><MoreHorizontal className="h-4 w-4" /></Button>}
                          items={[
                            { label: "Open", icon: <Eye />, onClick: () => setParams({ file: f.id }) },
                            { label: "Reprocess", icon: <RefreshCw />, disabled: processing, onClick: async () => { try { startJob(await api.process(pid, { file_ids: [f.id] })); } catch (e) { toast("error", "Could not reprocess", (e as Error).message); } } },
                            "sep",
                            { label: "Remove", icon: <Trash2 />, danger: true, onClick: async () => { await api.deleteFile(pid, f.id); refresh(); } },
                          ]}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              ))}
            </table>
            {byCat.length === 0 && <EmptyState icon={<FileStack />} title="No files match" description="Change the search or the filter." />}
          </Card>
        </>
      )}

      <FileDrawer fid={openFid} onClose={() => setParams({})} initialTab={(params.get("tab") as "text") || "preview"} focusLoc={params.get("loc") || undefined} />
    </Page>
  );
}
