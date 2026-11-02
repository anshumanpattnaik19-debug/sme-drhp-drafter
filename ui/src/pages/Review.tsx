import { useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertOctagon, AlertTriangle, ArrowRight, CheckCircle2, FileSearch, Hash, ListChecks, ScanText, Scale, ShieldAlert, FileX2, Link2Off, PenLine, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";
import { useProject } from "../lib/state";
import type { Issue, Review } from "../lib/types";
import { cn } from "../lib/utils";
import { Page } from "../components/ProjectShell";
import { Badge, Button, Card, EmptyState, PageHeader, Segmented, Skeleton, Stat, Tabs } from "../components/ui";

const KIND: Record<Issue["kind"], { label: string; icon: JSX.Element }> = {
  missing_input: { label: "Missing inputs", icon: <FileX2 /> },
  ungrounded: { label: "Figures not found", icon: <Hash /> },
  weak: { label: "Weakly traced figures", icon: <Link2Off /> },
  narrative: { label: "Prose pending", icon: <PenLine /> },
  checklist: { label: "Checklist gaps", icon: <ListChecks /> },
  inconsistency: { label: "Inconsistencies", icon: <Scale /> },
  drhp_stage: { label: "DRHP-stage", icon: <ShieldAlert /> },
  disclosure: { label: "Disclosure flags", icon: <FileSearch /> },
  ocr: { label: "Unread pages", icon: <ScanText /> },
  ingest: { label: "Unreadable files", icon: <AlertOctagon /> },
};

export default function ReviewPage() {
  const { project, version } = useProject();
  const nav = useNavigate();
  const [rv, setRv] = useState<Review | null>(null);
  const [kind, setKind] = useState<string>("all");
  const [sev, setSev] = useState<"all" | "high" | "medium" | "low">("all");
  const pid = project?.id ?? "";

  useEffect(() => { if (pid) api.review(pid).then(setRv).catch(() => {}); }, [pid, version]);

  const kinds = useMemo(() => Object.entries(rv?.summary.by_kind ?? {}).filter(([, n]) => n > 0), [rv]);
  const shown = (rv?.issues ?? []).filter((i) => (kind === "all" || i.kind === kind) && (sev === "all" || i.severity === sev));

  const act = (i: Issue) => {
    if (i.section) return nav(`/p/${pid}/draft/${i.section}`);
    if (i.file_id) return nav(`/p/${pid}/documents?file=${i.file_id}`);
    if (i.fact_ids?.length) return nav(`/p/${pid}/facts`);
  };
  const actLabel = (i: Issue) => (i.kind === "missing_input" ? "Upload" : i.section ? "Open section" : i.file_id ? "Open file" : i.fact_ids?.length ? "View facts" : null);

  const s = rv?.summary;
  const signedOff = s?.sections_signed_off ?? 0;

  return (
    <Page>
      <PageHeader
        eyebrow="Step 5 · Review pack"
        title="Review"
        description="What the lead manager and counsel need to resolve before this draft can go further: missing inputs, figures not traced to a file, checklist gaps and cross-file mismatches."
      />
      {!rv || !s ? (
        <div className="grid grid-cols-4 gap-4">{[0, 1, 2, 3].map((i) => <Skeleton key={i} className="h-24 rounded-lg" />)}</div>
      ) : (
        <>
          <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
            <Stat label="High-severity issues" value={s.high} tone={s.high ? "danger" : "success"} icon={<AlertOctagon />} sub="Block a review-ready draft" />
            <Stat label="Medium issues" value={s.medium} tone={s.medium ? "warning" : "success"} icon={<AlertTriangle />} sub="To resolve or note" />
            <Stat label="Placeholders [●]" value={s.placeholders} icon={<Hash />} sub="Inputs still to be provided" />
            <Stat label="Signed off by reviewer" value={`${signedOff}/${s.sections_total}`} tone={signedOff === s.sections_total ? "success" : undefined} icon={<ShieldCheck />}
              sub={`${s.sections_drafted} drafted · ${s.narrative_pending ?? 0} sub-headings need prose`} />
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3">
            <Tabs
              value={kind}
              onChange={setKind}
              className="flex-1"
              tabs={[{ value: "all", label: "All", count: rv.issues.length }, ...kinds.map(([k, n]) => ({ value: k, label: KIND[k as Issue["kind"]].label, count: n }))]}
            />
            <Segmented size="sm" value={sev} onChange={setSev} options={[{ value: "all", label: "All severities" }, { value: "high", label: "High" }, { value: "medium", label: "Medium" }, { value: "low", label: "To confirm" }]} />
          </div>

          <Card className="mt-3 divide-y divide-border overflow-hidden">
            {shown.length === 0 ? (
              <EmptyState icon={<CheckCircle2 />} title={rv.issues.length ? "Nothing in this view" : "No open issues"} description={rv.issues.length ? "Change the filter to see other issues." : "Everything checked out. Export the draft for the BRLM's review."} />
            ) : (
              shown.slice(0, 300).map((i) => {
                const k = KIND[i.kind];
                const label = actLabel(i);
                return (
                  <div key={i.id} className="group flex items-start gap-3 px-5 py-3 hover:bg-subtle/50">
                    <span className={cn("mt-0.5 flex h-7 w-7 shrink-0 items-center justify-center rounded-md [&>svg]:h-3.5 [&>svg]:w-3.5", i.severity === "high" ? "bg-danger-soft text-danger" : i.severity === "medium" ? "bg-warning-soft text-warning" : "bg-muted text-fg-muted")}>{k.icon}</span>
                    <div className="min-w-0 flex-1">
                      <div className="flex flex-wrap items-center gap-2">
                        <span className="text-[13px] font-medium text-fg">{i.title}</span>
                        <Badge tone={i.severity === "high" ? "danger" : i.severity === "medium" ? "warning" : "neutral"}>{i.severity === "low" ? "to confirm" : i.severity}</Badge>
                        <span className="text-2xs text-fg-subtle">{k.label}</span>
                      </div>
                      {i.detail && <p className="mt-0.5 line-clamp-2 text-xs text-fg-muted">{i.detail}</p>}
                    </div>
                    {label && (
                      <Button size="sm" variant="ghost" className="shrink-0 opacity-60 group-hover:opacity-100" onClick={() => (i.kind === "missing_input" ? nav(`/p/${pid}/documents`) : act(i))}>
                        {label} <ArrowRight className="h-3.5 w-3.5" />
                      </Button>
                    )}
                  </div>
                );
              })
            )}
          </Card>
          {shown.length > 300 && <p className="mt-2 text-center text-xs text-fg-subtle">Showing 300 of {shown.length}. Narrow the filter to see the rest.</p>}
        </>
      )}
    </Page>
  );
}
