import { Fragment, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Check, ChevronLeft, ChevronRight, CircleCheck, Database, ExternalLink, Pencil, Plus, Search, Trash2, X } from "lucide-react";
import { api } from "../lib/api";
import { useProject } from "../lib/state";
import type { Fact, FactType } from "../lib/types";
import { cn, FACT_TYPE_LABEL, factDisplay, num } from "../lib/utils";
import { Page } from "../components/ProjectShell";
import { Badge, Button, Card, Dialog, EmptyState, Field, Input, PageHeader, Segmented, Select, Skeleton, useToast, type Tone } from "../components/ui";

const PAGE = 50;
const TYPE_TONE: Record<string, Tone> = {
  amount: "primary", percent: "info", date: "warning", count: "neutral", person: "success", entity: "success",
  place: "neutral", identifier: "outline", short_text: "neutral",
};

function EditableCell({ value, onSave, className }: { value: string; onSave: (v: string) => Promise<void>; className?: string }) {
  const [editing, setEditing] = useState(false);
  const [v, setV] = useState(value);
  useEffect(() => setV(value), [value]);
  if (!editing)
    return (
      <button onClick={(e) => { e.stopPropagation(); setEditing(true); }} className={cn("group/ec flex w-full items-center gap-1.5 rounded px-1 py-0.5 text-left hover:bg-muted", className)}>
        <span className="min-w-0 flex-1 truncate">{value || <span className="text-fg-subtle">–</span>}</span>
        <Pencil className="h-3 w-3 shrink-0 text-fg-subtle opacity-0 group-hover/ec:opacity-100" />
      </button>
    );
  const commit = async () => { if (v !== value) await onSave(v); setEditing(false); };
  return (
    <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
      <Input autoFocus value={v} onChange={(e) => setV(e.target.value)} className="h-7 text-[13px]"
        onKeyDown={(e) => { if (e.key === "Enter") commit(); if (e.key === "Escape") { setV(value); setEditing(false); } }} />
      <Button size="icon-sm" variant="ghost" onClick={commit} aria-label="Save"><Check className="h-3.5 w-3.5 text-success" /></Button>
      <Button size="icon-sm" variant="ghost" onClick={() => { setV(value); setEditing(false); }} aria-label="Cancel"><X className="h-3.5 w-3.5" /></Button>
    </div>
  );
}

function AddFactDialog({ open, onClose, onAdd, files }: { open: boolean; onClose: () => void; onAdd: (f: Partial<Fact>) => Promise<void>; files: { id: string; name: string }[] }) {
  const [f, setF] = useState<Partial<Fact>>({ type: "short_text" });
  const [busy, setBusy] = useState(false);
  useEffect(() => { if (open) setF({ type: "short_text", label: "", value: "", unit: "", period: "" }); }, [open]);
  const submit = async () => { setBusy(true); try { await onAdd(f); onClose(); } finally { setBusy(false); } };
  return (
    <Dialog open={open} onClose={onClose} title="Add a fact" description="For information the files do not contain, e.g. a figure confirmed by the issuer. Facts you add are marked reviewed and take priority in routing."
      footer={<><Button variant="ghost" onClick={onClose}>Cancel</Button><Button variant="primary" onClick={submit} loading={busy} disabled={!f.label?.trim() || !f.value?.trim()}>Add fact</Button></>}>
      <div className="grid grid-cols-2 gap-4">
        <Field label="Label" required className="col-span-2"><Input autoFocus value={f.label} onChange={(e) => setF({ ...f, label: e.target.value })} placeholder="e.g. Installed capacity of blown film line" /></Field>
        <Field label="Value" required><Input value={f.value} onChange={(e) => setF({ ...f, value: e.target.value })} placeholder="e.g. 7,200" /></Field>
        <Field label="Type">
          <Select value={f.type} onChange={(e) => setF({ ...f, type: e.target.value as FactType })}>
            {Object.entries(FACT_TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
        </Field>
        <Field label="Unit"><Input value={f.unit} onChange={(e) => setF({ ...f, unit: e.target.value })} placeholder="e.g. ₹ lakhs, MTPA, %" /></Field>
        <Field label="Period"><Input value={f.period} onChange={(e) => setF({ ...f, period: e.target.value })} placeholder="e.g. FY 2025-26" /></Field>
        <Field label="Source file" hint="Optional: the file this fact relates to." className="col-span-2">
          <Select value={f.file_id ?? ""} onChange={(e) => setF({ ...f, file_id: e.target.value || null })}>
            <option value="">Entered by user (no file)</option>
            {files.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}
          </Select>
        </Field>
        <Field label="Note" className="col-span-2"><Input value={f.note ?? ""} onChange={(e) => setF({ ...f, note: e.target.value })} placeholder="e.g. Confirmed by CFO email of 30 Oct 2026" /></Field>
      </div>
    </Dialog>
  );
}

export default function FactsPage() {
  const { project, version, refresh } = useProject();
  const nav = useNavigate();
  const toast = useToast();
  const [facts, setFacts] = useState<Fact[] | null>(null);
  const [q, setQ] = useState("");
  const [type, setType] = useState("");
  const [file, setFile] = useState("");
  const [rev, setRev] = useState<"all" | "used" | "unreviewed" | "reviewed" | "user">("all");
  const [page, setPage] = useState(0);
  const [sel, setSel] = useState<Set<string>>(new Set());
  const [open, setOpen] = useState<string | null>(null);
  const [adding, setAdding] = useState(false);
  const pid = project?.id ?? "";

  useEffect(() => { if (pid) api.facts(pid).then(setFacts).catch((e) => toast("error", "Could not load facts", e.message)); }, [pid, version]); // eslint-disable-line react-hooks/exhaustive-deps

  const filtered = useMemo(() => {
    const ql = q.toLowerCase();
    return (facts ?? []).filter((f) =>
      (!ql || `${f.label} ${f.value} ${f.period} ${f.file_name}`.toLowerCase().includes(ql)) &&
      (!type || f.type === type) && (!file || f.file_id === file) &&
      (rev === "all" || (rev === "used" ? (f.used_in?.length ?? 0) > 0 : rev === "reviewed" ? f.reviewed : rev === "unreviewed" ? !f.reviewed : f.origin === "user")));
  }, [facts, q, type, file, rev]);
  useEffect(() => { setPage(0); setSel(new Set()); }, [q, type, file, rev]);

  const rows = filtered.slice(page * PAGE, page * PAGE + PAGE);
  const pages = Math.max(1, Math.ceil(filtered.length / PAGE));
  const filesWithFacts = useMemo(() => {
    const ids = new Set((facts ?? []).map((f) => f.file_id));
    return (project?.files ?? []).filter((f) => ids.has(f.id));
  }, [facts, project?.files]);

  const patch = async (id: string, p: Partial<Fact>) => {
    try {
      const upd = await api.patchFact(pid, id, p);
      setFacts((xs) => xs?.map((x) => (x.id === id ? upd : x)) ?? null);
    } catch (e) { toast("error", "Update failed", (e as Error).message); }
  };
  const bulk = async (action: "review" | "delete") => {
    const ids = [...sel];
    for (const id of ids) {
      if (action === "review") await api.patchFact(pid, id, { reviewed: true }).catch(() => {});
      else await api.deleteFact(pid, id).catch(() => {});
    }
    setSel(new Set());
    setFacts(await api.facts(pid));
    refresh();
    toast("success", action === "review" ? `Marked ${ids.length} fact(s) reviewed` : `Deleted ${ids.length} fact(s)`);
  };
  const add = async (f: Partial<Fact>) => {
    try {
      const nf = await api.addFact(pid, f);
      setFacts((xs) => [nf, ...(xs ?? [])]);
      refresh();
      toast("success", "Fact added");
    } catch (e) { toast("error", "Could not add fact", (e as Error).message); }
  };

  const reviewed = (facts ?? []).filter((f) => f.reviewed).length;
  const allSel = rows.length > 0 && rows.every((r) => sel.has(r.id));

  return (
    <Page>
      <PageHeader
        eyebrow="Step 3 · Fact store"
        title="Facts"
        description="Typed values extracted from the documents, each with its file and location. Drafts may only use figures that are here or in Offer details."
        actions={
          <>
            {facts && <Badge tone={reviewed ? "success" : "neutral"}>{num(reviewed)} of {num(facts.length)} reviewed</Badge>}
            <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => setAdding(true)}>Add fact</Button>
          </>
        }
      />

      <div className="mb-3 flex flex-wrap items-center gap-2">
        <Input icon={<Search className="h-4 w-4" />} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search label, value, period or file" className="w-80" />
        <Select value={type} onChange={(e) => setType(e.target.value)} className="w-36">
          <option value="">All types</option>
          {Object.entries(FACT_TYPE_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
        </Select>
        <Select value={file} onChange={(e) => setFile(e.target.value)} className="w-72">
          <option value="">All source files</option>
          {filesWithFacts.map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
        </Select>
        <Segmented size="sm" value={rev} onChange={setRev} options={[{ value: "all", label: "All" }, { value: "used", label: `Used in draft ${(facts ?? []).filter((f) => f.used_in?.length).length}` }, { value: "unreviewed", label: "Unreviewed" }, { value: "reviewed", label: "Reviewed" }, { value: "user", label: "Added by you" }]} />
      </div>

      {sel.size > 0 && (
        <div className="mb-3 flex items-center gap-3 rounded-lg border border-primary/30 bg-primary-soft/60 px-4 py-2 text-[13px] animate-fade-in">
          <span className="font-medium text-fg">{sel.size} selected</span>
          <Button size="sm" variant="secondary" icon={<CircleCheck className="h-3.5 w-3.5" />} onClick={() => bulk("review")}>Mark reviewed</Button>
          <Button size="sm" variant="ghost" icon={<Trash2 className="h-3.5 w-3.5 text-danger" />} onClick={() => bulk("delete")}>Delete</Button>
          <button className="ml-auto text-xs text-fg-muted hover:text-fg" onClick={() => setSel(new Set())}>Clear selection</button>
        </div>
      )}

      <Card className="overflow-hidden">
        {facts === null ? (
          <div className="space-y-2 p-4">{Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}</div>
        ) : facts.length === 0 ? (
          <EmptyState icon={<Database />} title="No facts yet" description="Upload and process the issuer's documents first. Facts appear here as each file is read."
            action={<Button onClick={() => nav(`/p/${pid}/documents`)}>Go to documents</Button>} />
        ) : (
          <>
            <table className="w-full table-fixed text-[13px]">
              <colgroup><col className="w-10" /><col className="w-[110px]" /><col /><col className="w-[22%]" /><col className="w-[13%]" /><col className="w-[22%]" /><col className="w-12" /></colgroup>
              <thead>
                <tr className="border-b border-border bg-subtle/60 text-left text-2xs uppercase tracking-wider text-fg-subtle">
                  <th className="py-2 pl-4"><input type="checkbox" checked={allSel} onChange={() => setSel(allSel ? new Set() : new Set(rows.map((r) => r.id)))} className="accent-[rgb(var(--primary))]" aria-label="Select page" /></th>
                  <th className="px-2 py-2 font-medium">Type</th>
                  <th className="px-2 py-2 font-medium">Label</th>
                  <th className="px-2 py-2 font-medium">Value</th>
                  <th className="px-2 py-2 font-medium">Period</th>
                  <th className="px-2 py-2 font-medium">Source</th>
                  <th className="py-2 pr-3 text-right font-medium">OK</th>
                </tr>
              </thead>
              <tbody>
                {rows.map((f) => (
                  <Fragment key={f.id}>
                    <tr onClick={() => setOpen(open === f.id ? null : f.id)} className={cn("cursor-pointer border-b border-border/70 hover:bg-subtle/60", sel.has(f.id) && "bg-primary-soft/40", open === f.id && "bg-subtle/60")}>
                      <td className="py-1.5 pl-4" onClick={(e) => e.stopPropagation()}>
                        <input type="checkbox" checked={sel.has(f.id)} className="accent-[rgb(var(--primary))]" aria-label="Select fact"
                          onChange={() => setSel((s) => { const n = new Set(s); n.has(f.id) ? n.delete(f.id) : n.add(f.id); return n; })} />
                      </td>
                      <td className="px-2 py-1.5"><Badge tone={TYPE_TONE[f.type]}>{FACT_TYPE_LABEL[f.type]}</Badge></td>
                      <td className="px-1 py-1.5"><EditableCell value={f.label} onSave={(v) => patch(f.id, { label: v })} className="text-fg" /></td>
                      <td className="px-1 py-1.5">
                        <div className="flex items-center gap-1">
                          <EditableCell value={f.value} onSave={(v) => patch(f.id, { value: v })} className="font-medium tabular text-fg" />
                          {f.unit && f.type !== "identifier" && <span className="shrink-0 text-2xs text-fg-subtle">{f.unit}</span>}
                        </div>
                      </td>
                      <td className="px-1 py-1.5"><EditableCell value={f.period} onSave={(v) => patch(f.id, { period: v })} className="text-fg-muted" /></td>
                      <td className="truncate px-2 py-1.5 text-xs text-fg-muted" title={`${f.file_name} · ${f.loc}`}>
                        {f.origin === "user" ? <Badge tone="primary">Added by you</Badge> : <><span className="text-fg">{f.file_name}</span> <span className="font-mono text-2xs text-fg-subtle">{f.loc}</span></>}
                        {f.edited && <Badge tone="warning" className="ml-1">edited</Badge>}
                        {f.superseded && <Badge tone="danger" className="ml-1">superseded</Badge>}
                      </td>
                      <td className="py-1.5 pr-3 text-right" onClick={(e) => e.stopPropagation()}>
                        <button onClick={() => patch(f.id, { reviewed: !f.reviewed })} aria-label={f.reviewed ? "Mark unreviewed" : "Mark reviewed"}
                          className={cn("inline-flex h-6 w-6 items-center justify-center rounded-full border transition-colors", f.reviewed ? "border-success bg-success text-white" : "border-border-strong text-transparent hover:border-success hover:text-success")}>
                          <Check className="h-3.5 w-3.5" />
                        </button>
                      </td>
                    </tr>
                    {open === f.id && (
                      <tr className="border-b border-border bg-subtle/40">
                        <td />
                        <td colSpan={6} className="px-2 py-3">
                          <div className="flex items-start gap-4">
                            <div className="min-w-0 flex-1">
                              <div className="mb-1 text-2xs font-medium uppercase tracking-wider text-fg-subtle">Source text</div>
                              <p className="rounded-md border border-border bg-surface px-3 py-2 font-serif text-[13px] leading-relaxed text-fg">{f.snippet || "No source text (entered by user)."}</p>
                              {f.note && <p className="mt-1 text-xs text-fg-muted">Note: {f.note}</p>}
                            </div>
                            <div className="flex shrink-0 flex-col gap-1.5">
                              <div className="text-2xs text-fg-subtle">Displayed as <span className="font-medium text-fg">{factDisplay(f)}</span></div>
                              {f.file_id && <Button size="sm" icon={<ExternalLink className="h-3.5 w-3.5" />} onClick={() => nav(`/p/${pid}/documents?file=${f.file_id}&tab=text&loc=${encodeURIComponent(f.loc)}`)}>Open source</Button>}
                              <Button size="sm" variant="ghost" icon={<Trash2 className="h-3.5 w-3.5 text-danger" />} onClick={async () => { await api.deleteFact(pid, f.id); setFacts((xs) => xs?.filter((x) => x.id !== f.id) ?? null); }}>Delete fact</Button>
                            </div>
                          </div>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                ))}
              </tbody>
            </table>
            {rows.length === 0 && <EmptyState icon={<Search />} title="No facts match" description="Change the search or filters." />}
            <div className="flex items-center justify-between border-t border-border px-4 py-2.5 text-xs text-fg-muted">
              <span className="tabular">{filtered.length ? `${page * PAGE + 1}–${Math.min(filtered.length, (page + 1) * PAGE)} of ${num(filtered.length)}` : "0 results"}</span>
              <div className="flex items-center gap-1">
                <Button size="icon-sm" variant="ghost" disabled={page === 0} onClick={() => setPage(page - 1)} aria-label="Previous page"><ChevronLeft className="h-4 w-4" /></Button>
                <span className="px-2 tabular">Page {page + 1} of {pages}</span>
                <Button size="icon-sm" variant="ghost" disabled={page >= pages - 1} onClick={() => setPage(page + 1)} aria-label="Next page"><ChevronRight className="h-4 w-4" /></Button>
              </div>
            </div>
          </>
        )}
      </Card>
      <AddFactDialog open={adding} onClose={() => setAdding(false)} onAdd={add} files={project?.files ?? []} />
    </Page>
  );
}
