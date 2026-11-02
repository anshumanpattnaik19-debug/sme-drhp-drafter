import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Download, FileText, FlaskConical, MessageSquareText, ShieldCheck } from "lucide-react";
import { api } from "../lib/api";
import { useProject } from "../lib/state";
import type { Review, SectionRow } from "../lib/types";
import { cn } from "../lib/utils";
import { Page } from "../components/ProjectShell";
import { Button, Card, CardHeader, PageHeader, Switch, useToast } from "../components/ui";

function Check({ ok, warn, children }: { ok: boolean; warn?: boolean; children: React.ReactNode }) {
  return (
    <li className="flex items-start gap-2.5 text-[13px]">
      {ok ? <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-success" /> : <AlertTriangle className={cn("mt-0.5 h-4 w-4 shrink-0", warn ? "text-warning" : "text-danger")} />}
      <span className="text-fg">{children}</span>
    </li>
  );
}

export default function ExportPage() {
  const { project, version } = useProject();
  const nav = useNavigate();
  const toast = useToast();
  const [sections, setSections] = useState<SectionRow[] | null>(null);
  const [rv, setRv] = useState<Review | null>(null);
  const [withReview, setWithReview] = useState(true);
  const [withSources, setWithSources] = useState(true);
  const [busy, setBusy] = useState(false);
  const pid = project?.id ?? "";

  useEffect(() => {
    if (!pid) return;
    api.sections(pid).then(setSections).catch(() => {});
    api.review(pid).then(setRv).catch(() => {});
  }, [pid, version]);

  const drafted = sections?.filter((s) => s.status === "drafted") ?? [];
  const pending = drafted.reduce((a, s) => a + (s.narrative_pending || 0), 0);
  const signed = drafted.filter((s) => s.review?.status === "reviewed").length;
  const ungrounded = drafted.reduce((a, s) => a + (s.ungrounded || 0), 0);

  const doExport = async () => {
    setBusy(true);
    try {
      const url = api.exportUrl(pid, withReview, withSources);
      const res = await fetch(url);
      if (!res.ok) throw new Error((await res.json()).detail);
      const blob = await res.blob();
      const name = (res.headers.get("content-disposition")?.match(/filename\*?=(?:UTF-8'')?"?([^";]+)/)?.[1]) || "DRHP_draft.docx";
      const obj = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = obj; a.download = decodeURIComponent(name); a.click();
      setTimeout(() => URL.revokeObjectURL(obj), 4000);
      toast("success", "Draft exported", decodeURIComponent(name));
    } catch (e) {
      toast("error", "Export failed", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Page>
      <PageHeader eyebrow="Step 6 · Output" title="Export" description="A .docx in SME section order with a cover page, table of contents, DRAFT header on every page and, optionally, source comments and the review pack." />
      <div className="grid gap-5 lg:grid-cols-[1fr_360px]">
        <Card>
          <CardHeader title="Draft Red Herring Prospectus (.docx)" description={project?.offer.company_name || project?.name} />
          <div className="space-y-4 px-5 py-5">
            <label className="flex items-start justify-between gap-6 rounded-lg border border-border p-4">
              <span className="flex gap-3">
                <MessageSquareText className="mt-0.5 h-4 w-4 text-fg-subtle" />
                <span>
                  <span className="block text-[13px] font-semibold text-fg">Source comments</span>
                  <span className="mt-0.5 block text-xs text-fg-muted">Each paragraph that cites facts gets a Word comment listing the file and location of every figure.</span>
                </span>
              </span>
              <Switch checked={withSources} onChange={setWithSources} label="Source comments" />
            </label>
            <label className="flex items-start justify-between gap-6 rounded-lg border border-border p-4">
              <span className="flex gap-3">
                <ShieldCheck className="mt-0.5 h-4 w-4 text-fg-subtle" />
                <span>
                  <span className="block text-[13px] font-semibold text-fg">Review pack annexure</span>
                  <span className="mt-0.5 block text-xs text-fg-muted">Appends the open issues (missing inputs, ungrounded figures, checklist gaps, mismatches) as a table at the end.</span>
                </span>
              </span>
              <Switch checked={withReview} onChange={setWithReview} label="Review pack" />
            </label>
            <div className="flex items-center justify-between rounded-lg bg-subtle px-4 py-3">
              <div className="flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-lg bg-info-soft text-info"><FileText className="h-5 w-5" /></span>
                <div>
                  <div className="text-[13px] font-semibold text-fg">{drafted.length} of {sections?.length ?? 35} sections</div>
                  <div className="text-xs text-fg-muted">Sections not yet drafted are exported as [●].</div>
                </div>
              </div>
              <Button variant="primary" size="lg" icon={<Download className="h-4 w-4" />} onClick={doExport} loading={busy} disabled={!drafted.length}>Download .docx</Button>
            </div>
          </div>
        </Card>

        <Card>
          <CardHeader title="Pre-export checks" />
          <ul className="space-y-3 px-5 py-4">
            <Check ok={!!sections && drafted.length === sections.length} warn>{drafted.length === (sections?.length ?? 0) ? "All sections drafted" : `${(sections?.length ?? 0) - drafted.length} section(s) not drafted`}</Check>
            <Check ok={ungrounded === 0}>{ungrounded === 0 ? "Every figure traced to an input" : `${ungrounded} figure(s) not found in the inputs`}</Check>
            <Check ok={(rv?.summary.by_kind.drhp_stage ?? 0) === 0}>{(rv?.summary.by_kind.drhp_stage ?? 0) === 0 ? "No price, price band or dates at DRHP stage" : "Price or dates appear in the draft"}</Check>
            <Check ok={(rv?.summary.by_kind.missing_input ?? 0) === 0} warn>{(rv?.summary.by_kind.missing_input ?? 0) === 0 ? "No missing inputs" : `${rv?.summary.by_kind.missing_input} missing input(s)`}</Check>
            <Check ok={pending === 0} warn>
              {pending === 0 ? "All narrative sub-headings have prose" : <span className="inline-flex items-center gap-1"><FlaskConical className="h-3.5 w-3.5" /> {pending} sub-heading(s) exported as drafting briefs</span>}
            </Check>
            <Check ok={!!sections && signed === sections.length} warn>
              {signed} of {sections?.length ?? 35} sections signed off by the reviewer
            </Check>
          </ul>
          <div className="border-t border-border px-5 py-3">
            <Button variant="ghost" size="sm" onClick={() => nav(`/p/${pid}/review`)}>Open review pack</Button>
          </div>
        </Card>
      </div>
      <p className="mt-6 max-w-3xl text-xs leading-relaxed text-fg-subtle">
        The export is a first draft for the Book Running Lead Manager and legal counsel. It is not a filing-ready document. Restated financial statements, the auditor's report
        and legal opinions are inserted as provided by the issuer; nothing is filled in for [●] items.
      </p>
    </Page>
  );
}
