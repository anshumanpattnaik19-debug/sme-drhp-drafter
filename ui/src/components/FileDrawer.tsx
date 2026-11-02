import { useEffect, useMemo, useState } from "react";
import { ExternalLink, RefreshCw, Trash2, X } from "lucide-react";
import { api } from "../lib/api";
import { useApp, useProject } from "../lib/state";
import type { Block, Fact, IssuerFile } from "../lib/types";
import { bytes, cn, FACT_TYPE_LABEL, factDisplay, FORMAT_LABEL, num, pct } from "../lib/utils";
import { FileIcon } from "./FileIcon";
import { FileStatusChip } from "./StatusChip";
import { Badge, Button, Drawer, EmptyState, Input, Select, Skeleton, Tabs, useToast } from "./ui";

type Detail = IssuerFile & { blocks: Block[]; facts: Fact[] };

function BlockView({ b, highlight }: { b: Block; highlight?: string }) {
  const kindTone = { text: "neutral", ocr: "warning", needs_ocr: "danger", table: "info", row: "success" } as const;
  return (
    <div className={cn("group rounded-md border border-transparent px-3 py-2 hover:border-border hover:bg-subtle/50", highlight && "border-primary/40 bg-primary-soft/30")}>
      <div className="mb-1 flex items-center gap-2">
        <span className="font-mono text-2xs text-fg-subtle">{b.loc}</span>
        {b.kind !== "text" && <Badge tone={kindTone[b.kind]}>{b.kind === "needs_ocr" ? "not read · needs OCR" : b.kind}</Badge>}
      </div>
      {b.kind === "row" ? (
        <div className="flex flex-wrap gap-1">
          {b.text.split(" | ").map((c, i) => (
            <span key={i} className={cn("rounded border border-border bg-surface px-1.5 py-0.5 font-mono text-[11.5px]", i === 0 && "font-semibold")}>{c || "·"}</span>
          ))}
        </div>
      ) : b.kind === "table" ? (
        <div className="overflow-x-auto scroll-thin">
          <table className="doc-table">
            <tbody>
              {b.text.split("\n").map((r, i) => (
                <tr key={i}>{r.split(" | ").map((c, j) => <td key={j}>{c}</td>)}</tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <p className="whitespace-pre-wrap text-[12.5px] leading-relaxed text-fg">{b.text || <span className="italic text-fg-subtle">No text layer on this page.</span>}</p>
      )}
    </div>
  );
}

export function FileDrawer({ fid, onClose, initialTab = "preview", focusLoc }: { fid: string | null; onClose: () => void; initialTab?: "preview" | "text" | "facts" | "details"; focusLoc?: string }) {
  const { project, refresh, startJob, bump } = useProject();
  const { meta } = useApp();
  const toast = useToast();
  const [d, setD] = useState<Detail | null>(null);
  const [tab, setTab] = useState<"preview" | "text" | "facts" | "details">(initialTab);
  const [q, setQ] = useState("");
  const pid = project?.id ?? "";
  const live = project?.files.find((f) => f.id === fid);

  useEffect(() => {
    if (!fid || !pid) return;
    setD(null);
    setQ("");
    api.file(pid, fid).then((x) => {
      setD(x);
      const previewable = ["pdf", "pdf_scanned", "pdf_mixed", "image"].includes(x.format);
      setTab(initialTab === "preview" && !previewable ? "text" : initialTab);
    }).catch((e) => toast("error", "Could not open file", e.message));
  }, [fid, pid, live?.status, initialTab]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    if (tab === "text" && focusLoc) {
      setTimeout(() => document.getElementById(`blk-${focusLoc}`)?.scrollIntoView({ block: "center", behavior: "smooth" }), 80);
    }
  }, [tab, focusLoc, d]);

  const groups = useMemo(() => {
    const m = new Map<string, { value: string; label: string }[]>();
    meta?.doc_types.forEach((t) => { if (!m.has(t.category)) m.set(t.category, []); m.get(t.category)!.push(t); });
    return [...m.entries()];
  }, [meta]);

  const facts = (d?.facts ?? []).filter((f) => !q || `${f.label} ${f.value}`.toLowerCase().includes(q.toLowerCase()));
  const blocks = (d?.blocks ?? []).filter((b) => !q || b.text.toLowerCase().includes(q.toLowerCase()));
  const previewable = d && ["pdf", "pdf_scanned", "pdf_mixed", "image"].includes(d.format);

  const changeType = async (v: string) => {
    if (!d) return;
    try {
      await api.patchFile(pid, d.id, v);
      await refresh();
      setD({ ...d, ...(await api.file(pid, d.id)) });
      toast("success", "Classification updated");
    } catch (e) { toast("error", "Update failed", (e as Error).message); }
  };
  const reprocess = async () => {
    if (!d) return;
    try { startJob(await api.process(pid, { file_ids: [d.id] })); } catch (e) { toast("error", "Could not reprocess", (e as Error).message); }
  };
  const remove = async () => {
    if (!d) return;
    await api.deleteFile(pid, d.id);
    await refresh();
    bump();
    toast("success", `Removed ${d.name}`);
    onClose();
  };

  return (
    <Drawer open={!!fid} onClose={onClose}>
      {!d ? (
        <div className="space-y-3 p-6"><Skeleton className="h-8 w-2/3" /><Skeleton className="h-4 w-1/3" /><Skeleton className="mt-6 h-96 w-full" /></div>
      ) : (
        <>
          <div className="flex items-start gap-3 border-b border-border px-5 py-4">
            <FileIcon format={d.format} size="lg" />
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-[15px] font-semibold text-fg" title={d.name}>{d.name}</h2>
              <div className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-1 text-xs text-fg-subtle">
                {d.folder && <span>{d.folder}</span>}
                <span>{FORMAT_LABEL[d.format] ?? d.format}</span>
                <span>{bytes(d.size)}</span>
                {d.pages ? <span>{d.pages} page{d.pages > 1 ? "s" : ""}</span> : null}
                {live && <FileStatusChip f={live} />}
              </div>
            </div>
            <div className="flex items-center gap-1">
              <a href={api.rawUrl(pid, d.id)} target="_blank" rel="noreferrer"><Button size="sm" variant="ghost" icon={<ExternalLink className="h-3.5 w-3.5" />}>Original</Button></a>
              <Button size="sm" variant="ghost" icon={<RefreshCw className="h-3.5 w-3.5" />} onClick={reprocess}>Reprocess</Button>
              <Button size="icon-sm" variant="ghost" onClick={remove} aria-label="Delete file" title="Remove file"><Trash2 className="h-4 w-4 text-danger" /></Button>
              <Button size="icon-sm" variant="ghost" onClick={onClose} aria-label="Close"><X className="h-4 w-4" /></Button>
            </div>
          </div>
          <div className="flex items-center gap-3 border-b border-border bg-subtle/50 px-5 py-2.5">
            <span className="text-xs font-medium text-fg-muted">Document type</span>
            <Select value={d.doc_type} onChange={(e) => changeType(e.target.value)} className="h-8 w-72 text-[13px]">
              {groups.map(([cat, items]) => (
                <optgroup key={cat} label={cat}>{items.map((t) => <option key={t.value} value={t.value}>{t.label}</option>)}</optgroup>
              ))}
            </Select>
            <Badge tone={d.doc_type_locked ? "primary" : d.confidence >= 0.8 ? "success" : "warning"}>
              {d.doc_type_locked ? "Set by you" : `Auto · ${pct(d.confidence)}`}
            </Badge>
            <span className="text-xs text-fg-subtle">{d.category}</span>
          </div>
          <div className="flex items-center justify-between gap-3 px-5 pt-2">
            <Tabs
              value={tab}
              onChange={setTab}
              className="flex-1 border-b-0"
              tabs={[
                ...(previewable ? [{ value: "preview" as const, label: "Preview" }] : []),
                { value: "text" as const, label: "Extracted text", count: d.blocks.length },
                { value: "facts" as const, label: "Facts", count: d.facts.length },
                { value: "details" as const, label: "Details" },
              ]}
            />
            {(tab === "text" || tab === "facts") && <Input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter…" className="h-8 w-48 text-[13px]" />}
          </div>
          <div className="min-h-0 flex-1 overflow-y-auto border-t border-border scroll-thin">
            {tab === "preview" && previewable && (
              d.format === "image" ? (
                <div className="flex justify-center bg-subtle p-6"><img src={api.rawUrl(pid, d.id)} alt={d.name} className="max-h-[78vh] rounded border border-border bg-white shadow-paper" /></div>
              ) : (
                <iframe title={d.name} src={api.rawUrl(pid, d.id)} className="h-full min-h-[70vh] w-full bg-subtle" />
              )
            )}
            {tab === "text" && (
              <div className="space-y-1 p-3">
                {blocks.length === 0 ? <EmptyState title={d.status === "processed" ? "No text" : "Not read yet"} description={d.status === "processed" ? "No block matches the filter." : "Process the file to extract its text."} /> :
                  blocks.slice(0, 400).map((b, i) => <div key={i} id={`blk-${b.loc}`}><BlockView b={b} highlight={focusLoc === b.loc ? "1" : undefined} /></div>)}
                {blocks.length > 400 && <p className="p-3 text-center text-xs text-fg-subtle">Showing the first 400 of {num(blocks.length)} blocks. Use the filter to narrow down.</p>}
              </div>
            )}
            {tab === "facts" && (
              facts.length === 0 ? <EmptyState title="No facts" description="No typed facts were extracted from this file." /> : (
                <table className="w-full text-[13px]">
                  <thead className="sticky top-0 bg-surface text-left text-2xs uppercase tracking-wider text-fg-subtle">
                    <tr className="border-b border-border"><th className="px-5 py-2 font-medium">Label</th><th className="px-3 py-2 font-medium">Value</th><th className="px-3 py-2 font-medium">Period</th><th className="px-3 py-2 font-medium">Location</th></tr>
                  </thead>
                  <tbody>
                    {facts.slice(0, 500).map((f) => (
                      <tr key={f.id} className="border-b border-border/70 hover:bg-subtle/60">
                        <td className="px-5 py-2"><div className="flex items-center gap-2"><Badge tone="outline">{FACT_TYPE_LABEL[f.type]}</Badge><span className="text-fg">{f.label}</span></div></td>
                        <td className="px-3 py-2 font-medium tabular text-fg">{factDisplay(f)}</td>
                        <td className="px-3 py-2 text-fg-muted">{f.period || "–"}</td>
                        <td className="px-3 py-2 font-mono text-2xs text-fg-subtle">{f.loc}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              )
            )}
            {tab === "details" && (
              <dl className="grid grid-cols-[180px_1fr] gap-x-4 gap-y-3 p-5 text-[13px]">
                {[
                  ["Format", FORMAT_LABEL[d.format] ?? d.format],
                  ["Pages", d.pages ?? "n/a (no pages)"],
                  ["Text blocks", num(d.blocks.length)],
                  ["Characters", num(d.chars ?? 0)],
                  ["Pages OCR'd", d.ocr_pages ?? 0],
                  ["Pages not read", d.needs_ocr_pages ?? 0],
                  ["Facts extracted", num(d.facts.length)],
                  ["Uploaded", d.uploaded_at?.replace("T", " ")],
                  ["Processed", d.processed_at?.replace("T", " ") ?? "–"],
                ].map(([k, v]) => (
                  <div key={String(k)} className="contents"><dt className="text-fg-subtle">{k}</dt><dd className="tabular text-fg">{v}</dd></div>
                ))}
                {d.warnings && d.warnings.length > 0 && (
                  <div className="contents"><dt className="text-fg-subtle">Warnings</dt><dd className="space-y-1">{d.warnings.map((w) => <div key={w} className="text-warning">{w}</div>)}</dd></div>
                )}
                {d.error && <div className="contents"><dt className="text-fg-subtle">Error</dt><dd className="text-danger">{d.error}</dd></div>}
              </dl>
            )}
          </div>
        </>
      )}
    </Drawer>
  );
}
