import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, CheckCircle2, Circle, ClipboardCheck, Database, Download, FileStack, FileText, PenLine, Sparkles } from "lucide-react";
import { api } from "../lib/api";
import { useApp, useProject } from "../lib/state";
import type { Review, SectionRow } from "../lib/types";
import { cn, num } from "../lib/utils";
import { Page } from "../components/ProjectShell";
import { WRITER_META } from "../components/WriterBadge";
import { Badge, Button, Card, CardHeader, PageHeader, Progress, Stat } from "../components/ui";

export default function OverviewPage() {
  const { project, version } = useProject();
  const { meta } = useApp();
  const nav = useNavigate();
  const [sections, setSections] = useState<SectionRow[] | null>(null);
  const [rv, setRv] = useState<Review | null>(null);
  const pid = project?.id ?? "";

  useEffect(() => {
    if (!pid) return;
    api.sections(pid).then(setSections).catch(() => {});
    api.review(pid).then(setRv).catch(() => {});
  }, [pid, version]);

  const s = project?.stats;
  const offer = project?.offer || {};
  const offerFilled = ["registered_office", "lead_manager", "registrar", "face_value", "fresh_issue_shares", "board_resolution_date"].filter((k) => (offer[k] || "").trim()).length;

  const steps = [
    { key: "documents", icon: <FileStack />, title: "Upload and read issuer files", done: !!s && s.files > 0 && s.pending === 0, detail: s ? `${s.processed} of ${s.files} files read · ${num(s.pages)} pages` : "" },
    { key: "offer", icon: <PenLine />, title: "Complete offer details", done: offerFilled >= 5, detail: `${offerFilled} of 6 key fields filled` },
    { key: "facts", icon: <Database />, title: "Check the extracted facts", done: !!s && s.reviewed_facts > 0, detail: s ? `${num(s.reviewed_facts)} of ${num(s.facts)} facts reviewed` : "" },
    { key: "draft", icon: <FileText />, title: "Draft the sections", done: !!s && s.drafted === s.sections, detail: s ? `${s.drafted} of ${s.sections} sections drafted` : "" },
    { key: "review", icon: <ClipboardCheck />, title: "Resolve issues and sign off sections", done: !!rv && rv.summary.high === 0 && rv.summary.sections_signed_off === rv.summary.sections_total,
      detail: rv ? `${rv.summary.high} high, ${rv.summary.medium} medium open · ${rv.summary.sections_signed_off} of ${rv.summary.sections_total} signed off` : "" },
    { key: "export", icon: <Download />, title: "Export the draft", done: false, detail: "Word .docx with sources and review pack" },
  ];
  const next = steps.find((x) => !x.done) ?? steps[steps.length - 1];

  const coverage = useMemo(() => {
    const cats = meta?.categories.filter((c) => c !== "Other") ?? [];
    return cats.map((c) => {
      const files = (project?.files ?? []).filter((f) => f.category === c);
      return { cat: c, files: files.length, read: files.filter((f) => f.status === "processed").length };
    });
  }, [meta, project?.files]);

  const byWriter = useMemo(() => {
    const m: Record<string, { total: number; done: number }> = {};
    (sections ?? []).forEach((x) => { m[x.writer] ??= { total: 0, done: 0 }; m[x.writer].total++; if (x.status === "drafted") m[x.writer].done++; });
    return m;
  }, [sections]);

  const missing = (rv?.issues ?? []).filter((i) => i.kind === "missing_input");

  return (
    <Page>
      <PageHeader
        eyebrow="Overview"
        title={offer.company_name || project?.name || "…"}
        description="Progress of this DRHP draft from the issuer's files to a reviewed .docx."
        actions={<Button variant="primary" icon={<ArrowRight className="h-4 w-4" />} onClick={() => nav(`/p/${pid}/${next.key}`)}>Next: {next.title}</Button>}
      />

      <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
        <Stat label="Files read" value={s ? `${s.processed}/${s.files}` : "–"} sub={s ? `${num(s.pages)} pages` : ""} icon={<FileStack />} />
        <Stat label="Facts extracted" value={s ? num(s.facts) : "–"} sub={s ? `${num(s.reviewed_facts)} reviewed` : ""} icon={<Database />} />
        <Stat label="Sections drafted" value={s ? `${s.drafted}/${s.sections}` : "–"} sub="SME section order" icon={<FileText />} />
        <Stat label="High-severity issues" value={rv ? rv.summary.high : "–"} tone={rv?.summary.high ? "danger" : rv ? "success" : undefined} sub={rv ? `${rv.summary.placeholders} placeholders [●]` : ""} icon={<ClipboardCheck />} />
      </div>

      <div className="mt-5 grid gap-5 lg:grid-cols-[1.25fr_1fr]">
        <Card>
          <CardHeader title="Workflow" description="Each step can be revisited; drafts pick up changes when redrafted." />
          <ol className="divide-y divide-border">
            {steps.map((st, i) => (
              <li key={st.key}>
                <button onClick={() => nav(`/p/${pid}/${st.key}`)} className={cn("group flex w-full items-center gap-4 px-5 py-3.5 text-left transition-colors hover:bg-subtle/60", st.key === next.key && "bg-primary-soft/30")}>
                  <span className={cn("flex h-8 w-8 shrink-0 items-center justify-center rounded-full border [&>svg]:h-4 [&>svg]:w-4", st.done ? "border-success/30 bg-success-soft text-success" : st.key === next.key ? "border-primary/40 bg-primary-soft text-primary" : "border-border bg-subtle text-fg-subtle")}>
                    {st.done ? <CheckCircle2 /> : st.icon}
                  </span>
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center gap-2 text-[13px] font-semibold text-fg">
                      <span className="text-fg-subtle tabular">{i + 1}.</span> {st.title}
                      {st.key === next.key && <Badge tone="primary">Next</Badge>}
                    </div>
                    <div className="mt-0.5 text-xs text-fg-muted">{st.detail}</div>
                  </div>
                  <ArrowRight className="h-4 w-4 text-fg-subtle opacity-0 transition-opacity group-hover:opacity-100" />
                </button>
              </li>
            ))}
          </ol>
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader title="Inputs by category" description="Files the issuer has provided, by folder type." />
            <div className="space-y-3 px-5 py-4">
              {coverage.map((c) => (
                <div key={c.cat} className="flex items-center gap-3 text-[13px]">
                  {c.files ? <CheckCircle2 className="h-4 w-4 shrink-0 text-success" /> : <Circle className="h-4 w-4 shrink-0 text-border-strong" />}
                  <span className="w-36 shrink-0 text-fg">{c.cat}</span>
                  <Progress value={c.files ? c.read / c.files : 0} tone={c.files && c.read === c.files ? "success" : "primary"} className="flex-1" />
                  <span className="w-12 shrink-0 text-right text-xs tabular text-fg-muted">{c.read}/{c.files}</span>
                </div>
              ))}
              {missing.length > 0 && (
                <div className="mt-2 rounded-md border border-danger/20 bg-danger-soft/50 px-3 py-2 text-xs">
                  <div className="font-semibold text-danger">{missing.length} section(s) lack an input file</div>
                  <div className="mt-0.5 line-clamp-3 text-fg-muted">{missing.map((m) => m.title.replace("Missing input for ", "")).join(" · ")}</div>
                </div>
              )}
            </div>
          </Card>
          <Card>
            <CardHeader title="Who writes the document" description="Share of the 35 SME sections by writer." actions={<Button size="sm" variant="ghost" icon={<Sparkles className="h-3.5 w-3.5" />} onClick={() => nav(`/p/${pid}/draft`)}>Open draft</Button>} />
            <div className="space-y-3 px-5 py-4">
              {(Object.keys(WRITER_META) as (keyof typeof WRITER_META)[]).map((w) => {
                const x = byWriter[w] ?? { total: 0, done: 0 };
                return (
                  <div key={w} className="flex items-center gap-3 text-[13px]">
                    <span className="w-32 shrink-0 text-fg">{WRITER_META[w].label}</span>
                    <Progress value={x.total ? x.done / x.total : 0} className="flex-1" />
                    <span className="w-12 shrink-0 text-right text-xs tabular text-fg-muted">{x.done}/{x.total}</span>
                  </div>
                );
              })}
            </div>
          </Card>
        </div>
      </div>
    </Page>
  );
}
