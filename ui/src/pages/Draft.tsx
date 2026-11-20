import { useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import {
  AlertTriangle, ArrowLeft, ArrowRight, Check, CheckCircle2, ChevronDown, Circle, CircleDashed, ExternalLink, FileWarning,
  Loader2, MoreHorizontal, PenLine, Plus, RotateCcw, Save, Sparkles, Trash2, Wand2, X, XCircle, FlaskConical, ShieldCheck,
  FileText, HelpCircle, ListChecks, Undo2,
} from "lucide-react";
import { api } from "../lib/api";
import { useApp, useProject } from "../lib/state";
import type { Draft, DraftBlock, Fact, SectionData, SectionDef, SectionRow, Source } from "../lib/types";
import { ago, cn, factDisplay } from "../lib/utils";
import { RichText } from "../components/RichText";
import { EngineBadge, SignOffBadge, WRITER_META, WriterBadge } from "../components/WriterBadge";
import { Badge, Button, Dialog, EmptyState, Field, Input, Menu, Progress, Segmented, Skeleton, Tabs, Textarea, Tooltip, useToast } from "../components/ui";

/* ---------------- outline ---------------- */

function StatusIcon({ s, running }: { s: SectionRow; running: boolean }) {
  if (running) return <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" />;
  if (s.status !== "drafted") return <Circle className="h-3.5 w-3.5 text-border-strong" />;
  if (s.review?.status === "reviewed") return <ShieldCheck className="h-3.5 w-3.5 text-success" />;
  if (s.ungrounded) return <AlertTriangle className="h-3.5 w-3.5 text-danger" />;
  if (s.narrative_pending) return <PenLine className="h-3.5 w-3.5 text-warning" />;
  return <CheckCircle2 className="h-3.5 w-3.5 text-fg-subtle" />;
}

function Outline({ sections, current, onPick, runningKey, queued }: { sections: SectionRow[]; current: string; onPick: (k: string) => void; runningKey?: string | null; queued: Set<string> }) {
  const [filter, setFilter] = useState<"all" | "slm" | "todo">("all");
  const [closed, setClosed] = useState<Record<string, boolean>>({});
  const parts = [...new Set(sections.map((s) => s.part))];
  const show = (s: SectionRow) => filter === "all" || (filter === "slm" ? s.writer.startsWith("slm") : s.review?.status !== "reviewed");
  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <div className="px-3 pb-2">
        <Segmented size="sm" value={filter} onChange={setFilter} options={[{ value: "all", label: "All" }, { value: "slm", label: "SLM" }, { value: "todo", label: "Open" }]} />
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto px-2 pb-4 scroll-thin">
        {parts.map((part) => {
          const items = sections.filter((s) => s.part === part && show(s));
          if (!items.length) return null;
          const done = sections.filter((s) => s.part === part && s.status === "drafted").length;
          const all = sections.filter((s) => s.part === part).length;
          return (
            <div key={part} className="mt-2">
              <button onClick={() => setClosed((c) => ({ ...c, [part]: !c[part] }))} className="flex w-full items-center gap-1 px-2 py-1 text-2xs font-semibold uppercase tracking-wider text-fg-subtle hover:text-fg">
                <ChevronDown className={cn("h-3 w-3 transition-transform", closed[part] && "-rotate-90")} />
                <span className="flex-1 truncate text-left">{part}</span>
                <span className="tabular font-normal">{done}/{all}</span>
              </button>
              {!closed[part] && items.map((s) => (
                <button
                  key={s.key}
                  onClick={() => onPick(s.key)}
                  className={cn(
                    "group flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-[13px] transition-colors",
                    current === s.key ? "bg-surface text-fg shadow-card ring-1 ring-border" : "text-fg-muted hover:bg-muted hover:text-fg",
                  )}
                >
                  {queued.has(s.key) && runningKey !== s.key ? <CircleDashed className="h-3.5 w-3.5 text-fg-subtle" /> : <StatusIcon s={s} running={runningKey === s.key} />}
                  <span className="min-w-0 flex-1 truncate">{s.title}</span>
                  <span className={cn("shrink-0 font-mono text-[10px] text-fg-subtle", s.writer.startsWith("slm") && "text-primary")}>{WRITER_META[s.writer].short}</span>
                </button>
              ))}
            </div>
          );
        })}
      </div>
    </div>
  );
}

/* ---------------- document blocks ---------------- */

function BlockView({ b, idx, facts, selected, onSelect, onFact }: { b: DraftBlock; idx: number; facts: Map<string, Fact>; selected: boolean; onSelect: (i: number) => void; onFact: (f: Fact) => void }) {
  const cited = (b.facts || []).map((id) => facts.get(id)).filter(Boolean) as Fact[];
  const nsrc = cited.length + (b.sources?.length ?? 0);
  if (b.type === "heading") return <h3 id={`b-${idx}`} className="mb-2 mt-7 font-sans text-[15px] font-semibold tracking-tight text-paper-fg first:mt-0">{b.text}</h3>;
  if (b.type === "brief") {
    return (
      <div id={`b-${idx}`} onClick={() => onSelect(idx)} className={cn("my-3 cursor-pointer rounded-md border border-dashed border-warning/50 bg-warning-soft/40 px-4 py-3 font-sans", selected && "ring-1 ring-warning/50")}>
        <div className="flex items-center gap-2 text-[12px] font-semibold text-warning"><PenLine className="h-3.5 w-3.5" /> Prose to be written · drafting brief</div>
        <p className="mt-0.5 text-[11.5px] text-fg-muted">{b.text}</p>
        {(b.items || []).length === 0 ? (
          <p className="mt-2 text-[12.5px] text-fg-muted">No facts were routed to this sub-heading. <span className="placeholder-chip">[●]</span> Input needed from the issuer.</p>
        ) : (
          <ul className="mt-2 space-y-1">
            {(b.items || []).map((it) => (
              <li key={it.fact_id} className="flex items-baseline gap-2 text-[12.5px]">
                <span className="h-1 w-1 shrink-0 translate-y-[-2px] rounded-full bg-fg-subtle" />
                <span className="min-w-0 flex-1">
                  <span className="text-fg-muted">{it.label}{it.period ? ` (${it.period})` : ""}: </span>
                  <span className="font-semibold tabular text-fg">{it.value}</span>
                  <span className="ml-1.5 text-2xs text-fg-subtle">{it.file_name} · {it.loc}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </div>
    );
  }
  if (b.type === "table") {
    const [head, ...body] = b.rows || [];
    return (
      <div id={`b-${idx}`} onClick={() => onSelect(idx)} className={cn("relative my-4 -mx-3 cursor-pointer rounded-md px-3 py-2", selected ? "bg-primary-soft/40 ring-1 ring-primary/30" : "hover:bg-subtle/60")}>
        {b.caption && <div className="mb-1.5 font-sans text-[12.5px] font-semibold text-paper-fg">{b.caption}</div>}
        <div className="overflow-x-auto scroll-thin">
          <table className="doc-table">
            {head && <thead><tr>{head.map((c, i) => <th key={i}><RichText text={c} /></th>)}</tr></thead>}
            <tbody>{body.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={cn(j > 0 && /^[\d(₹–-]/.test(c) && "text-right")}><RichText text={c} facts={cited} onFact={onFact} /></td>)}</tr>)}</tbody>
          </table>
        </div>
        {b.sources && b.sources.length > 0 && (
          <div className="mt-1 font-sans text-[11px] italic text-fg-subtle">Source: {b.sources.map((s) => `${s.file_name} (${s.loc})`).join("; ")}</div>
        )}
        {nsrc > 0 && <span className="absolute -left-7 top-3 rounded bg-primary-soft px-1 font-sans text-[10px] font-semibold text-primary">{nsrc}</span>}
      </div>
    );
  }
  if (b.type === "note")
    return (
      <div id={`b-${idx}`} className="my-3 flex gap-2 rounded-md border border-dashed border-border-strong bg-subtle/60 px-3 py-2 font-sans text-[12.5px] text-fg-muted">
        <FileWarning className="mt-0.5 h-3.5 w-3.5 shrink-0" />
        <span><RichText text={b.text} /></span>
      </div>
    );
  return (
    <div id={`b-${idx}`} onClick={() => onSelect(idx)} className={cn("group relative -mx-3 cursor-pointer rounded-md px-3 py-1 transition-colors", selected ? "bg-primary-soft/40 ring-1 ring-primary/30" : "hover:bg-subtle/60")}>
      {nsrc > 0 && (
        <Tooltip content={`${nsrc} source(s). Click to see them.`} side="left" className="absolute -left-7 top-2.5">
          <span className="rounded bg-primary-soft px-1 font-sans text-[10px] font-semibold text-primary">{nsrc}</span>
        </Tooltip>
      )}
      {b.template && <span className="float-right ml-2 mt-2 font-sans"><Badge tone="outline">Standard risk</Badge></span>}
      <p className="my-1.5 text-[15.5px] text-paper-fg"><RichText text={b.text} facts={cited} onFact={onFact} /></p>
    </div>
  );
}

function AutoTextarea(props: React.TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) { el.style.height = "auto"; el.style.height = `${el.scrollHeight + 2}px`; }
  }, [props.value]);
  return <Textarea ref={ref} rows={2} {...props} className={cn("resize-none font-serif text-[15px]", props.className)} />;
}

function BlockEditor({ blocks, onChange }: { blocks: DraftBlock[]; onChange: (b: DraftBlock[]) => void }) {
  const upd = (i: number, p: Partial<DraftBlock>) => onChange(blocks.map((b, j) => (j === i ? { ...b, ...p } : b)));
  const del = (i: number) => onChange(blocks.filter((_, j) => j !== i));
  const insert = (i: number, type: DraftBlock["type"]) => {
    const nb: DraftBlock = type === "table" ? { type, text: "", rows: [["Particulars", "Details"], ["", ""]], facts: [] } : { type, text: "", facts: [] };
    onChange([...blocks.slice(0, i + 1), nb, ...blocks.slice(i + 1)]);
  };
  return (
    <div className="space-y-3">
      {blocks.map((b, i) => (
        <div key={i} className="group relative rounded-md border border-transparent p-1 hover:border-border">
          <div className="absolute -left-24 top-1 flex w-20 flex-col items-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
            <span className="font-sans text-2xs uppercase text-fg-subtle">{b.type}</span>
            <button onClick={() => del(i)} className="font-sans text-2xs text-danger hover:underline">Remove</button>
          </div>
          {b.type === "heading" ? (
            <Input value={b.text} onChange={(e) => upd(i, { text: e.target.value })} className="font-semibold" />
          ) : b.type === "table" ? (
            <div className="overflow-x-auto scroll-thin">
              <table className="doc-table">
                <tbody>
                  {(b.rows || []).map((r, ri) => (
                    <tr key={ri}>
                      {r.map((c, ci) => (
                        <td key={ci} className="p-0">
                          <input value={c} onChange={(e) => upd(i, { rows: (b.rows || []).map((rr, x) => (x === ri ? rr.map((cc, y) => (y === ci ? e.target.value : cc)) : rr)) })}
                            className={cn("w-full bg-transparent px-2 py-1.5 outline-none focus:bg-primary-soft/40", ri === 0 && "font-semibold")} />
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
              <button className="mt-1 font-sans text-2xs text-primary hover:underline" onClick={() => upd(i, { rows: [...(b.rows || []), new Array((b.rows?.[0] || ["", ""]).length).fill("")] })}>+ Add row</button>
            </div>
          ) : b.type === "brief" ? (
            <div className="rounded-md border border-dashed border-warning/50 bg-warning-soft/40 p-3 font-sans text-[12.5px]">
              <div className="font-semibold text-warning">Drafting brief: {b.sub}</div>
              <ul className="mt-1 space-y-0.5 text-fg-muted">
                {(b.items || []).slice(0, 8).map((it) => <li key={it.fact_id}>{it.label}: <b className="text-fg">{it.value}</b></li>)}
              </ul>
              <Button size="xs" variant="secondary" className="mt-2" onClick={() => upd(i, { type: "paragraph", text: "", items: undefined })}>
                Write prose for this sub-heading
              </Button>
            </div>
          ) : (
            <AutoTextarea value={b.text} onChange={(e) => upd(i, { text: e.target.value })} />
          )}
          <div className="absolute -bottom-3 left-1/2 z-10 hidden -translate-x-1/2 gap-1 group-hover:flex">
            {(["paragraph", "heading", "table"] as const).map((t) => (
              <button key={t} onClick={() => insert(i, t)} className="rounded-full border border-border bg-surface px-2 py-0.5 font-sans text-2xs text-fg-muted shadow-card hover:text-primary">+ {t}</button>
            ))}
          </div>
        </div>
      ))}
      {blocks.length === 0 && <Button size="sm" icon={<Plus className="h-3.5 w-3.5" />} onClick={() => onChange([{ type: "paragraph", text: "", facts: [] }])}>Add paragraph</Button>}
    </div>
  );
}

/* ---------------- inspector ---------------- */

function Metric({ label, value, tone, sub }: { label: string; value: string; tone?: "success" | "danger" | "warning"; sub?: string }) {
  return (
    <div className="rounded-lg border border-border bg-surface p-3">
      <div className="text-2xs font-medium text-fg-subtle">{label}</div>
      <div className={cn("mt-1 text-lg font-semibold tabular", tone === "success" && "text-success", tone === "danger" && "text-danger", tone === "warning" && "text-warning")}>{value}</div>
      {sub && <div className="text-2xs text-fg-subtle">{sub}</div>}
    </div>
  );
}

function FactRow({ f, onOpen, active }: { f: Fact; onOpen: (f: Fact) => void; active?: boolean }) {
  return (
    <button onClick={() => onOpen(f)} className={cn("block w-full rounded-md border px-3 py-2 text-left transition-colors", active ? "border-primary bg-primary-soft/50" : "border-border bg-surface hover:border-border-strong")}>
      <div className="flex items-start justify-between gap-2">
        <span className="line-clamp-2 text-xs text-fg-muted">{f.label}{f.period ? ` · ${f.period}` : ""}</span>
        <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-fg-subtle" />
      </div>
      <div className="mt-0.5 text-[13px] font-semibold tabular text-fg">{factDisplay(f)}</div>
      <div className="mt-1 truncate text-2xs text-fg-subtle">{f.file_name} · <span className="font-mono">{f.loc}</span></div>
    </button>
  );
}

function Inspector({ sec, draft, facts, selected, activeFact, presentTypes, onOpenFact, onOpenSource, onJump, open, onClose }: {
  sec: SectionDef; draft: Draft | null; facts: Map<string, Fact>; selected: number | null; activeFact: Fact | null; presentTypes: Set<string>;
  onOpenFact: (f: Fact) => void; onOpenSource: (s: Source) => void; onJump: (i: number) => void;
  open: boolean; onClose: () => void;
}) {
  const [tab, setTab] = useState<"checks" | "sources">("checks");
  useEffect(() => { if (selected !== null || activeFact) setTab("sources"); }, [selected, activeFact]);
  const v = draft?.verification;
  const missing = sec.needs.filter((n) => !presentTypes.has(n));
  const selFacts = selected !== null && draft ? (draft.blocks[selected]?.facts || []).map((id) => facts.get(id)).filter(Boolean) as Fact[] : [];
  const selSources: Source[] = selected !== null && draft ? draft.blocks[selected]?.sources || [] : [];
  const routed = draft ? draft.routed.map((id) => facts.get(id)).filter(Boolean) as Fact[] : [];
  const allSources: Source[] = draft
    ? [...new Map(draft.blocks.flatMap((b) => b.sources || []).map((s) => [`${s.file_name}|${s.loc}`, s])).values()]
    : [];
  const phBlocks = draft ? draft.blocks.map((b, i) => ({ b, i })).filter(({ b }) => (b.text || (b.rows || []).flat().join(" ")).includes("[●]")) : [];

  return (
    <aside className={cn("shrink-0 flex-col border-l border-border bg-surface",
      open ? "fixed bottom-0 right-0 top-14 z-30 flex w-[min(340px,100vw)] shadow-pop" : "hidden xl:flex xl:w-[340px]")}>
      <div className="flex items-center justify-between border-b border-border px-3 py-2 xl:hidden">
        <span className="text-[13px] font-semibold text-fg">Checks and sources</span>
        <Button size="icon-sm" variant="ghost" onClick={onClose} aria-label="Close checks"><X className="h-4 w-4" /></Button>
      </div>
      <Tabs value={tab} onChange={setTab} className="px-3 pt-2" tabs={[{ value: "checks", label: "Checks" }, { value: "sources", label: "Sources", count: draft ? (selected !== null ? selFacts.length + selSources.length : allSources.length + routed.length) : undefined }]} />
      <div className="min-h-0 flex-1 space-y-5 overflow-y-auto p-4 scroll-thin">
        {tab === "checks" && (
          <>
            {missing.length > 0 && (
              <div className="rounded-lg border border-danger/25 bg-danger-soft/60 p-3">
                <div className="flex items-center gap-1.5 text-xs font-semibold text-danger"><XCircle className="h-3.5 w-3.5" /> Missing inputs</div>
                <p className="mt-1 text-xs text-fg-muted">No file is classified as: {missing.join(", ").replace(/_/g, " ")}. Upload it or reclassify a file under Documents.</p>
              </div>
            )}
            {!draft || !v ? (
              <p className="text-[13px] text-fg-muted">Checks run when the section is drafted: grounding of every figure, [●] placeholders, mandatory items and DRHP-stage rules.</p>
            ) : (
              <>
                <div className="flex items-start gap-2 rounded-lg border border-info/25 bg-info-soft/50 px-3 py-2 text-xs text-fg">
                  <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-info" />
                  <span>These checks catch invented or misplaced figures and missing items. They do not confirm the disclosure is right: that needs your sign-off.</span>
                </div>
                <div className="grid grid-cols-3 gap-2">
                  <Metric label="Traced in place" value={String(v.grounded)} tone={v.grounded ? "success" : undefined} sub="to the cited source" />
                  <Metric label="Weak" value={String((v.weak || []).length)} tone={(v.weak || []).length ? "warning" : undefined} sub="found elsewhere" />
                  <Metric label="Not found" value={String(v.ungrounded.length)} tone={v.ungrounded.length ? "danger" : "success"} sub="in any input" />
                </div>
                <div className="grid grid-cols-2 gap-2">
                  <Metric label="Placeholders [●]" value={String(v.placeholders)} tone={v.placeholders ? "warning" : "success"} sub="inputs still needed" />
                  <Metric label="Prose pending" value={String(v.narrative_pending ?? 0)} tone={v.narrative_pending ? "warning" : "success"} sub="sub-headings as briefs" />
                </div>
                {(v.missing_inputs || []).length > 0 && (
                  <section>
                    <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-danger"><XCircle className="h-3.5 w-3.5" /> To request from the issuer</h4>
                    <ul className="space-y-1.5">
                      {v.missing_inputs.map((m) => (
                        <li key={m.item} className="rounded-md border border-danger/20 bg-danger-soft/40 px-2.5 py-1.5 text-xs">
                          <span className="font-medium text-fg">{m.item}</span>
                          <span className="block text-fg-muted">Expected in: {m.where}</span>
                        </li>
                      ))}
                    </ul>
                  </section>
                )}
                {(v.weak || []).length > 0 && (
                  <section>
                    <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-warning"><AlertTriangle className="h-3.5 w-3.5" /> Not traced to the cited source</h4>
                    <div className="space-y-1.5">
                      {v.weak.slice(0, 10).map((u, i) => (
                        <div key={i} className="rounded-md border border-warning/25 bg-warning-soft/40 px-2.5 py-1.5 text-xs">
                          <span className="font-semibold tabular text-warning">{u.figure}</span>
                          <span className="ml-1 text-fg-muted">…{u.context.trim()}…</span>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
                {v.ungrounded.length > 0 && (
                  <section>
                    <h4 className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-danger"><AlertTriangle className="h-3.5 w-3.5" /> Not found in the inputs</h4>
                    <div className="space-y-1.5">
                      {v.ungrounded.map((u, i) => (
                        <div key={i} className="rounded-md border border-danger/20 bg-danger-soft/40 px-2.5 py-1.5 text-xs">
                          <span className="font-semibold tabular text-danger">{u.figure}</span>
                          <span className="ml-1 text-fg-muted">…{u.context.trim()}…</span>
                        </div>
                      ))}
                    </div>
                  </section>
                )}
                {v.checklist.length > 0 && (
                  <section>
                    <h4 className="mb-2 flex items-center justify-between text-xs font-semibold text-fg">
                      Mandatory items <span className="font-normal tabular text-fg-subtle">{v.checklist.filter((c) => c.covered).length}/{v.checklist.length}</span>
                    </h4>
                    <Progress value={v.checklist_coverage ?? 0} tone={(v.checklist_coverage ?? 0) >= 0.9 ? "success" : "warning"} className="mb-2" />
                    <ul className="space-y-1">
                      {v.checklist.map((c) => {
                        const st = c.status ?? (c.covered ? "covered" : "missing");
                        return (
                          <li key={c.item} className="flex items-start gap-2 text-[13px]">
                            {st === "covered" ? <Check className="mt-0.5 h-3.5 w-3.5 shrink-0 text-success" /> : st === "unconfirmed" ? <HelpCircle className="mt-0.5 h-3.5 w-3.5 shrink-0 text-warning" /> : <X className="mt-0.5 h-3.5 w-3.5 shrink-0 text-danger" />}
                            <span className={cn("flex-1", st === "covered" ? "text-fg" : "text-fg-muted")}>{c.item}</span>
                            {st === "unconfirmed" && <span className="text-2xs text-warning">to confirm</span>}
                          </li>
                        );
                      })}
                    </ul>
                    <p className="mt-2 text-2xs text-fg-subtle">Covered = built from an issuer schedule or a red flag. To confirm = only mentioned in prose. Placeholder list until the reviewer fixes the checklist.</p>
                  </section>
                )}
                <section>
                  <h4 className="mb-2 text-xs font-semibold text-fg">DRHP-stage rules</h4>
                  {v.drhp_stage.length === 0 ? (
                    <div className="flex items-center gap-2 text-[13px] text-success"><CheckCircle2 className="h-3.5 w-3.5" /> No price, price band, lot size or offer date stated</div>
                  ) : v.drhp_stage.map((s) => <div key={s} className="flex items-center gap-2 text-[13px] text-danger"><XCircle className="h-3.5 w-3.5" /> {s}</div>)}
                </section>
                {phBlocks.length > 0 && (
                  <section>
                    <h4 className="mb-2 text-xs font-semibold text-fg">Where [●] appears</h4>
                    <div className="space-y-1">
                      {phBlocks.slice(0, 12).map(({ b, i }) => (
                        <button key={i} onClick={() => onJump(i)} className="block w-full truncate rounded px-2 py-1 text-left text-xs text-fg-muted hover:bg-muted hover:text-fg">
                          {(b.text || (b.rows || []).map((r) => r.join(" ")).join(" ")).slice(0, 90)}
                        </button>
                      ))}
                    </div>
                  </section>
                )}
                <section className="border-t border-border pt-4 text-2xs leading-relaxed text-fg-subtle">
                  {WRITER_META[sec.writer].help}
                  {draft.latency_s !== undefined && <> · {draft.latency_s.toFixed(2)} s</>}
                  {draft.usage?.completion_tokens && <> · {draft.usage.completion_tokens} tokens</>}
                </section>
              </>
            )}
          </>
        )}
        {tab === "sources" && (
          !draft ? <p className="text-[13px] text-fg-muted">Sources appear once the section is drafted.</p> : (
            <>
              {activeFact && (
                <section>
                  <h4 className="mb-2 text-xs font-semibold text-fg">Selected figure</h4>
                  <FactRow f={activeFact} onOpen={onOpenFact} active />
                  <p className="mt-2 rounded-md bg-subtle px-2.5 py-2 font-serif text-xs leading-relaxed text-fg-muted">{activeFact.snippet}</p>
                </section>
              )}
              {(selected !== null ? selSources : allSources).length > 0 && (
                <section>
                  <h4 className="mb-2 text-xs font-semibold text-fg">{selected !== null ? "Schedules and passages this block is built from" : "Issuer schedules used in this section"}</h4>
                  <div className="space-y-1.5">
                    {(selected !== null ? selSources : allSources).slice(0, 30).map((s, i) => (
                      <button key={i} onClick={() => s.file_id && onOpenSource(s)} className="block w-full rounded-md border border-border bg-surface px-3 py-2 text-left transition-colors hover:border-border-strong">
                        <div className="flex items-start justify-between gap-2">
                          <span className="truncate text-[12.5px] font-medium text-fg">{s.file_name}</span>
                          <ExternalLink className="mt-0.5 h-3 w-3 shrink-0 text-fg-subtle" />
                        </div>
                        <div className="font-mono text-2xs text-fg-subtle">{s.loc}</div>
                        {s.snippet && <div className="mt-1 line-clamp-3 text-xs text-fg-muted">{s.snippet}</div>}
                      </button>
                    ))}
                  </div>
                </section>
              )}
              <section>
                <h4 className="mb-2 text-xs font-semibold text-fg">{selected !== null ? "Facts cited in this block" : "Facts routed to this section"}</h4>
                {(selected !== null ? selFacts : routed).length === 0 ? (
                  <p className="text-[13px] text-fg-muted">{selected !== null ? "This block cites no facts." : "No facts were routed to this section."}</p>
                ) : (
                  <div className="space-y-1.5">{(selected !== null ? selFacts : routed).slice(0, 60).map((f) => <FactRow key={f.id} f={f} onOpen={onOpenFact} active={activeFact?.id === f.id} />)}</div>
                )}
              </section>
            </>
          )
        )}
      </div>
    </aside>
  );
}

/* ---------------- page ---------------- */

export default function DraftPage() {
  const { key } = useParams();
  const navigate = useNavigate();
  const { project, version, job, startJob, cancelJob } = useProject();
  const { health, openSettings } = useApp();
  const toast = useToast();
  const pid = project?.id ?? "";
  const [sections, setSections] = useState<SectionRow[] | null>(null);
  const [data, setData] = useState<SectionData | null>(null);
  const [facts, setFacts] = useState<Map<string, Fact>>(new Map());
  const [selected, setSelected] = useState<number | null>(null);
  const [activeFact, setActiveFact] = useState<Fact | null>(null);
  const [editing, setEditing] = useState<DraftBlock[] | null>(null);
  const [saving, setSaving] = useState(false);
  const docRef = useRef<HTMLDivElement>(null);
  const [signing, setSigning] = useState(false);
  const [inspectorOpen, setInspectorOpen] = useState(false);
  const [phoneDoc, setPhoneDoc] = useState(false);          // on a phone the list and the document are separate screens
  const [reviewer, setReviewer] = useState(() => { try { return localStorage.getItem("reviewer") || ""; } catch { return ""; } });
  const [signNote, setSignNote] = useState("");

  const current = key || sections?.[0]?.key || "";
  const drafting = job?.kind === "draft" && job.status === "running";
  const queued = new Set(drafting ? (job?.keys ?? []).slice(job!.done) : []);

  useEffect(() => { if (pid) api.sections(pid).then(setSections).catch(() => {}); }, [pid, version]);
  const factsKey = drafting ? -1 : version; // facts do not change while sections are being drafted
  useEffect(() => {
    if (!pid) return;
    api.facts(pid).then((fs) => setFacts(new Map(fs.map((f) => [f.id, f])))).catch(() => {});
  }, [pid, factsKey]);
  useEffect(() => {
    if (!pid || !current || editing) return;
    api.section(pid, current).then(setData).catch(() => {});
  }, [pid, current, version]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { setSelected(null); setActiveFact(null); setEditing(null); docRef.current?.scrollTo({ top: 0 }); }, [current]);

  const presentTypes = useMemo(() => new Set((project?.files ?? []).filter((f) => f.status === "processed").map((f) => f.doc_type)), [project?.files]);
  const idx = sections?.findIndex((s) => s.key === current) ?? -1;
  const go = (k: string) => { setPhoneDoc(true); navigate(`/p/${pid}/draft/${k}`); };
  const drafted = sections?.filter((s) => s.status === "drafted").length ?? 0;
  const row = sections?.[idx];
  const sec = data?.section;
  const draft = data?.draft ?? null;
  const versions = data?.versions ?? [];

  const run = async (keys?: string[], skip = false) => {
    if (health?.use_model && health.model.serverless && health.model.workers_running === 0)
      toast("info", "Waking the model", "The first section can take 3 to 6 minutes while the model starts. Later ones are quick. You can leave this page open.");
    if (health?.use_model && health.model.reachable === false)
      toast("error", "The model is not reachable", "Sections that need prose will be left as drafting briefs. Check Settings, or try again in a minute.");
    try { startJob(await api.draft(pid, keys, skip)); } catch (e) { toast("error", "Could not start drafting", (e as Error).message); }
  };
  const save = async () => {
    if (!editing) return;
    setSaving(true);
    try {
      const d = await api.saveSection(pid, current, editing);
      setData((x) => (x ? { ...x, draft: d } : x));
      setEditing(null);
      api.sections(pid).then(setSections);
      toast("success", "Section saved", "Checks were re-run on your edits.");
    } catch (e) { toast("error", "Could not save", (e as Error).message); } finally { setSaving(false); }
  };
  const clear = async () => {
    await api.clearSection(pid, current);
    setData((x) => (x ? { ...x, draft: null } : x));
    api.sections(pid).then(setSections);
  };
  const pickVersion = async (n: number) => {
    try {
      setData(await api.selectVersion(pid, current, n));
      api.sections(pid).then(setSections);
      toast("success", `Using Draft ${n}`, "The review, the export and the assistant now use this draft of the section.");
    } catch (e) { toast("error", "Could not switch draft", (e as Error).message); }
  };
  const dropVersion = async (n: number) => {
    try {
      setData(await api.deleteVersion(pid, current, n));
      api.sections(pid).then(setSections);
    } catch (e) { toast("error", "Could not delete the draft", (e as Error).message); }
  };
  const jump = (i: number) => { setSelected(i); document.getElementById(`b-${i}`)?.scrollIntoView({ behavior: "smooth", block: "center" }); };
  const openFact = (f: Fact) => f.file_id && navigate(`/p/${pid}/documents?file=${f.file_id}&tab=text&loc=${encodeURIComponent(f.loc)}`);
  const openSource = (s: Source) => s.file_id && navigate(`/p/${pid}/documents?file=${s.file_id}&tab=text&loc=${encodeURIComponent(s.loc.split(",")[0])}`);
  const signedOff = draft?.review?.status === "reviewed";
  const doSignoff = async (reviewed: boolean, reviewer = "", note = "") => {
    try {
      const d = await api.signoff(pid, current, reviewed, reviewer, note);
      setData((x) => (x ? { ...x, draft: d } : x));
      api.sections(pid).then(setSections);
      setSigning(false);
      toast("success", reviewed ? "Section signed off" : "Sign-off withdrawn");
    } catch (e) { toast("error", "Could not update sign-off", (e as Error).message); }
  };

  const isRunningHere = drafting && job?.current === current;
  const isMock = !health?.use_model;

  return (
    <div className="flex h-full">
      {/* outline */}
      <div className={cn("w-full shrink-0 flex-col border-r border-border bg-subtle/50 md:flex md:w-[280px]", phoneDoc ? "hidden" : "flex")}>
        <div className="border-b border-border p-3">
          <div className="mb-2 flex items-center justify-between text-xs">
            <span className="font-semibold text-fg">Sections</span>
            <span className="tabular text-fg-subtle">{drafted} of {sections?.length ?? 0} drafted</span>
          </div>
          <Progress value={sections?.length ? drafted / sections.length : 0} className="mb-3" />
          <div className="flex gap-1.5">
            <Button variant="primary" size="sm" className="flex-1" icon={<Sparkles className="h-3.5 w-3.5" />} loading={drafting}
              disabled={drafting || !sections || drafted === sections.length} onClick={() => run(undefined, drafted > 0)}>
              {drafting ? `Drafting ${job!.done}/${job!.total}` : sections && drafted === sections.length ? "All sections drafted" : drafted ? "Draft remaining" : "Draft all sections"}
            </Button>
            {drafting && <Button size="sm" variant="secondary" className="h-8 text-danger" icon={<X className="h-3.5 w-3.5" />} onClick={cancelJob} aria-label="Cancel drafting">Cancel</Button>}
            <Menu
              trigger={<Button size="icon-sm" className="h-8 w-8" aria-label="More drafting actions"><MoreHorizontal className="h-4 w-4" /></Button>}
              items={[
                { label: "Redraft all sections", icon: <RotateCcw />, disabled: drafting, onClick: () => run() },
                { label: "Redraft SLM sections", icon: <Wand2 />, disabled: drafting, onClick: () => run(sections?.filter((s) => s.writer.startsWith("slm")).map((s) => s.key)) },
              ]}
            />
          </div>
        </div>
        {sections ? <Outline sections={sections} current={current} onPick={go} runningKey={drafting ? job?.current : null} queued={queued} /> : <div className="space-y-2 p-3">{Array.from({ length: 10 }).map((_, i) => <Skeleton key={i} className="h-7" />)}</div>}
      </div>

      {/* document */}
      <div className={cn("min-w-0 flex-1 flex-col md:flex", phoneDoc ? "flex" : "hidden")}>
        <div className="flex min-h-12 shrink-0 flex-wrap items-center justify-between gap-x-3 gap-y-2 border-b border-border bg-surface px-3 py-2 md:px-5">
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <Button size="sm" variant="ghost" className="md:hidden" icon={<ArrowLeft className="h-3.5 w-3.5" />} onClick={() => setPhoneDoc(false)}>Sections</Button>
            <Button size="icon-sm" variant="ghost" disabled={idx <= 0} onClick={() => sections && go(sections[idx - 1].key)} aria-label="Previous section"><ArrowLeft className="h-4 w-4" /></Button>
            <Button size="icon-sm" variant="ghost" disabled={!sections || idx >= sections.length - 1} onClick={() => sections && go(sections[idx + 1].key)} aria-label="Next section"><ArrowRight className="h-4 w-4" /></Button>
            <span className="min-w-[80px] truncate text-[13px] font-semibold text-fg" title={sec?.title}>{sec?.title ?? "…"}</span>
            {sec && <span className="hidden shrink-0 2xl:inline-flex"><WriterBadge writer={sec.writer} /></span>}
            {draft && versions.length > 0 && (
              <Menu
                trigger={<Button size="sm" variant="secondary" icon={<ChevronDown className="h-3.5 w-3.5" />} aria-label="Choose a draft">Draft {draft.version ?? 1} · {versions.length} saved</Button>}
                items={[
                  ...[...versions].reverse().map((v) => ({
                    label: `Draft ${v.n}${v.selected ? "  (in use)" : ""} · ${v.words} words · ${v.ungrounded} not found · ${v.placeholders ?? 0} [●]${v.review === "reviewed" ? " · signed off" : ""}${v.edited ? " · edited" : ""}`,
                    onClick: () => { if (!v.selected) pickVersion(v.n); },
                  })),
                  ...(versions.length > 1 ? [{ label: `Delete Draft ${draft.version ?? 1}`, icon: <Trash2 />, danger: true, onClick: () => dropVersion(draft.version ?? 1) }] : []),
                ]}
              />
            )}
            {draft && <span className="hidden shrink-0 sm:inline-flex"><EngineBadge engine={draft.edited ? "user" : draft.engine} model={draft.model_name} /></span>}
            {draft && <span className="hidden shrink-0 sm:inline-flex"><SignOffBadge review={draft.review} /></span>}
            {draft && <span className="hidden whitespace-nowrap text-2xs text-fg-subtle 2xl:inline">Updated {ago(draft.updated_at)}</span>}
          </div>
          <div className="flex flex-wrap items-center gap-1.5">
            {editing ? (
              <>
                <Button size="sm" variant="ghost" onClick={() => setEditing(null)}>Cancel</Button>
                <Button size="sm" variant="primary" icon={<Save className="h-3.5 w-3.5" />} onClick={save} loading={saving}>Save edits</Button>
              </>
            ) : (
              <>
                <Button size="sm" variant="ghost" className="xl:hidden" icon={<ListChecks className="h-3.5 w-3.5" />} onClick={() => setInspectorOpen(true)}>Checks</Button>
                {draft && <Button size="sm" icon={<PenLine className="h-3.5 w-3.5" />} onClick={() => setEditing(JSON.parse(JSON.stringify(draft.blocks)))} disabled={isRunningHere}>Edit</Button>}
                <Button size="sm" variant={draft ? "secondary" : "primary"} icon={draft ? <RotateCcw className="h-3.5 w-3.5" /> : <Sparkles className="h-3.5 w-3.5" />} onClick={() => run([current])} disabled={drafting} loading={isRunningHere}>
                  {draft ? (versions.length >= 3 ? "Redraft (replaces oldest)" : `Redraft as Draft ${(Math.max(0, ...versions.map((v) => v.n))) + 1}`) : "Draft section"}
                </Button>
                {draft && (signedOff ? (
                  <Button size="sm" variant="ghost" icon={<Undo2 className="h-3.5 w-3.5" />} onClick={() => doSignoff(false)}>Withdraw sign-off</Button>
                ) : (
                  <Button size="sm" variant="primary" icon={<ShieldCheck className="h-3.5 w-3.5" />} onClick={() => setSigning(true)} disabled={isRunningHere}>Sign off</Button>
                ))}
                {draft && (
                  <Menu trigger={<Button size="icon-sm" variant="ghost" aria-label="Section actions"><MoreHorizontal className="h-4 w-4" /></Button>}
                    items={[{ label: "Clear draft", icon: <Trash2 />, danger: true, onClick: clear }]} />
                )}
              </>
            )}
          </div>
        </div>

        <div ref={docRef} className="min-h-0 flex-1 overflow-y-auto bg-bg scroll-thin" onClick={() => { setSelected(null); setActiveFact(null); }}>
          {draft && !editing && (draft.narrative_pending?.length ?? 0) > 0 && (
            <div className="mx-auto mt-5 flex max-w-[820px] items-center gap-3 rounded-lg border border-warning/30 bg-warning-soft/70 px-4 py-2.5 text-[13px]" onClick={(e) => e.stopPropagation()}>
              <FlaskConical className="h-4 w-4 shrink-0 text-warning" />
              <span className="flex-1 text-fg">
                Tables and fixed text are built from the issuer's files. <b>{draft.narrative_pending!.length} sub-heading(s) still need prose</b> and are shown as drafting briefs.
              </span>
              {isMock ? <Button size="xs" variant="secondary" onClick={() => openSettings()}>Connect model</Button>
                : <Button size="xs" variant="secondary" onClick={() => setEditing(JSON.parse(JSON.stringify(draft.blocks)))}>Write them</Button>}
            </div>
          )}
          {draft && !editing && draft.engine === "rules" && (
            <div className="mx-auto mt-5 flex max-w-[820px] items-center gap-3 rounded-lg border border-info/30 bg-info-soft/60 px-4 py-2.5 text-[13px]" onClick={(e) => e.stopPropagation()}>
              <FileText className="h-4 w-4 shrink-0 text-info" />
              <span className="flex-1 text-fg">Each risk factor comes from a red flag found in the issuer's files and cites its source. Risks marked <i>Standard risk</i> are template wording.</span>
            </div>
          )}
          <div className="mx-auto my-6 max-w-[820px] px-4">
            <article className="doc-paper min-h-[70vh] rounded-sm border border-border px-14 py-12 shadow-paper" onClick={(e) => e.stopPropagation()}>
              <div className="mb-1 font-sans text-2xs font-semibold uppercase tracking-[0.14em] text-fg-subtle">{sec?.part}</div>
              <h2 className="mb-6 border-b border-border pb-3 text-center text-[19px] font-semibold uppercase tracking-wide text-paper-fg">{sec?.title}</h2>
              {isRunningHere ? (
                <div className="space-y-3">
                  <div className="mb-4 flex items-center gap-2 font-sans text-[13px] text-primary"><Loader2 className="h-4 w-4 animate-spin" /> Drafting from routed facts…</div>
                  {[95, 88, 92, 60, 0, 90, 85, 70].map((w, i) => (w ? <Skeleton key={i} className="h-3.5" /> : <div key={i} className="h-4" />))}
                </div>
              ) : editing ? (
                <BlockEditor blocks={editing} onChange={setEditing} />
              ) : draft ? (
                draft.blocks.map((b, i) => (
                  <BlockView key={i} b={b} idx={i} facts={facts} selected={selected === i} onSelect={(j) => { setSelected(j); setActiveFact(null); }} onFact={(f) => setActiveFact(f)} />
                ))
              ) : sec ? (
                <EmptyState
                  icon={<Sparkles />}
                  title="Not drafted yet"
                  description={
                    <>
                      {WRITER_META[sec.writer].help}
                      {sec.subheads.length > 0 && <span className="mt-2 block">Sub-headings: {sec.subheads.join(" · ")}</span>}
                    </>
                  }
                  action={<Button variant="primary" icon={<Sparkles className="h-4 w-4" />} onClick={() => run([current])} disabled={drafting}>Draft this section</Button>}
                  className="font-sans"
                />
              ) : (
                <div className="space-y-3">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-3.5" />)}</div>
              )}
            </article>
            {row && draft && !editing && (
              <p className="mt-3 text-center font-sans text-2xs text-fg-subtle">
                Dotted underlines are figures traced to a source; click one to see where it came from. <span className="placeholder-chip">[●]</span> marks a missing input.
              </p>
            )}
          </div>
        </div>
      </div>

      {sec && <Inspector open={inspectorOpen} onClose={() => setInspectorOpen(false)} sec={sec} draft={editing ? null : draft} facts={facts} selected={selected} activeFact={activeFact} presentTypes={presentTypes} onOpenFact={openFact} onOpenSource={openSource} onJump={jump} />}

      <Dialog
        open={signing}
        onClose={() => setSigning(false)}
        title={`Sign off “${sec?.title ?? ""}”`}
        description="Confirms you have reviewed this section against the issuer's files. Redrafting or editing the section withdraws the sign-off."
        footer={
          <>
            <Button variant="ghost" onClick={() => setSigning(false)}>Cancel</Button>
            <Button variant="primary" icon={<ShieldCheck className="h-4 w-4" />} disabled={!reviewer.trim()}
              onClick={() => { try { localStorage.setItem("reviewer", reviewer.trim()); } catch { /* storage unavailable */ } doSignoff(true, reviewer, signNote); }}>
              Sign off
            </Button>
          </>
        }
      >
        <div className="space-y-4">
          {draft?.verification && (draft.verification.ungrounded.length > 0 || (draft.verification.narrative_pending ?? 0) > 0 || draft.verification.placeholders > 0) && (
            <div className="rounded-md border border-warning/30 bg-warning-soft/60 px-3 py-2 text-xs text-fg">
              Open items in this section: {draft.verification.ungrounded.length} figure(s) not found, {draft.verification.narrative_pending ?? 0} sub-heading(s) without prose,
              {" "}{draft.verification.placeholders} [●] placeholder(s). Sign off only if these are acceptable at this stage.
            </div>
          )}
          <Field label="Reviewer" required><Input autoFocus value={reviewer} onChange={(e) => setReviewer(e.target.value)} placeholder="Your name" /></Field>
          <Field label="Note" hint="Optional, e.g. “Tables checked against the CA certificate; prose pending.”">
            <Input value={signNote} onChange={(e) => setSignNote(e.target.value)} />
          </Field>
        </div>
      </Dialog>
    </div>
  );
}
