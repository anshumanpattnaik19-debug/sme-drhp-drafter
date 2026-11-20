import { useEffect, useState, type ReactNode } from "react";
import { Link, NavLink, useLocation, useParams } from "react-router-dom";
import {
  ArrowLeft, ClipboardCheck, Database, Download, FileStack, FileText, LayoutDashboard, Loader2, PenLine, Sparkles, X,
} from "lucide-react";
import { AssistantChat } from "./Assistant";
import { api } from "../lib/api";
import { useProject } from "../lib/state";
import { BOARD_LABEL, cn, num } from "../lib/utils";
import { Badge, Button, EmptyState, Progress, Skeleton } from "./ui";

function JobCard() {
  const { job, cancelJob } = useProject();
  if (!job) return null;
  const running = job.status === "running";
  const frac = job.total ? job.done / job.total : 0;
  return (
    <div className="m-3 rounded-lg border border-border bg-surface p-3 shadow-card animate-slide-up">
      <div className="flex items-center gap-2">
        {running ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" /> : <span className="h-2 w-2 rounded-full bg-success" />}
        <span className="flex-1 truncate text-xs font-semibold text-fg">{job.label}</span>
        {running && !job.message.startsWith("Cancelling") && (
          <Button size="sm" variant="secondary" className="h-6 px-2 text-2xs text-danger" icon={<X className="h-3 w-3" />} onClick={cancelJob} aria-label="Cancel this run">
            Cancel
          </Button>
        )}
      </div>
      <Progress value={running ? Math.max(frac, 0.03) : 1} className="mt-2.5" tone={running ? "primary" : "success"} />
      <div className="mt-2 flex items-center justify-between gap-2 text-2xs text-fg-subtle">
        <span className="truncate">{job.message}</span>
        <span className="shrink-0 tabular">{job.done}/{job.total}</span>
      </div>
    </div>
  );
}

export function ProjectShell({ children }: { children: ReactNode }) {
  const { pid = "" } = useParams();
  const { project, error, version } = useProject();
  const [high, setHigh] = useState<number | null>(null);
  const [panel, setPanel] = useState(false);
  const onAssistantPage = useLocation().pathname.endsWith("/assistant");
  useEffect(() => {
    const h = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "j") { e.preventDefault(); setPanel((p) => !p); }
      if (e.key === "Escape") setPanel(false);
    };
    window.addEventListener("keydown", h);
    return () => window.removeEventListener("keydown", h);
  }, []);

  useEffect(() => {
    if (!project) return;
    api.review(pid).then((r) => setHigh(r.summary.high)).catch(() => {});
  }, [pid, version, project?.stats.drafted, project?.stats.processed]); // eslint-disable-line react-hooks/exhaustive-deps

  if (error && !project) {
    return (
      <EmptyState
        className="h-full"
        icon={<FileText />}
        title="Project not available"
        description={error}
        action={<Link to="/projects"><Button>Back to projects</Button></Link>}
      />
    );
  }

  const s = project?.stats;
  const nav: { to: string; label: string; icon: ReactNode; count?: ReactNode; tone?: "danger" }[] = [
    { to: "overview", label: "Overview", icon: <LayoutDashboard /> },
    { to: "assistant", label: "Assistant", icon: <Sparkles /> },
    { to: "documents", label: "Documents", icon: <FileStack />, count: s ? num(s.files) : undefined },
    { to: "offer", label: "Offer details", icon: <PenLine /> },
    { to: "facts", label: "Facts", icon: <Database />, count: s ? num(s.facts) : undefined },
    { to: "draft", label: "Draft", icon: <FileText />, count: s ? `${s.drafted}/${s.sections}` : undefined },
    { to: "review", label: "Review", icon: <ClipboardCheck />, count: high ? high : undefined, tone: high ? "danger" : undefined },
    { to: "export", label: "Export", icon: <Download /> },
  ];

  return (
    <div className="flex h-full flex-col md:flex-row">
      <aside aria-label="Project" className="flex shrink-0 flex-col border-b border-border bg-subtle/50 md:w-60 md:border-b-0 md:border-r">
        <div className="hidden border-b border-border px-4 py-4 md:block">
          <Link to="/projects" className="mb-3 inline-flex items-center gap-1 text-xs text-fg-subtle hover:text-fg">
            <ArrowLeft className="h-3 w-3" /> All projects
          </Link>
          {project ? (
            <>
              <div className="line-clamp-2 text-sm font-semibold leading-snug text-fg" title={project.offer.company_name || project.name}>
                {project.offer.company_name || project.name}
              </div>
              <div className="mt-1.5 flex items-center gap-1.5">
                <Badge tone="primary">{BOARD_LABEL[project.offer.board || "bse_sme"]}</Badge>
                <Badge tone="outline">DRHP stage</Badge>
              </div>
            </>
          ) : (
            <div className="space-y-2">
              <Skeleton className="h-4 w-40" />
              <Skeleton className="h-4 w-24" />
            </div>
          )}
        </div>
        <nav aria-label="Project sections" className="flex gap-0.5 overflow-x-auto p-2 scroll-thin md:flex-1 md:block md:space-y-0.5 md:overflow-y-auto md:overflow-x-visible">
          {nav.map((n) => (
            <NavLink
              key={n.to}
              to={n.to}
              className={({ isActive }) =>
                cn(
                  "group flex shrink-0 items-center gap-2.5 rounded-md px-2.5 py-1.5 text-[13px] font-medium transition-colors [&>svg]:h-4 [&>svg]:w-4",
                  isActive ? "bg-surface text-fg shadow-card ring-1 ring-border" : "text-fg-muted hover:bg-muted hover:text-fg",
                )
              }
            >
              {n.icon}
              <span className="flex-1">{n.label}</span>
              {n.count !== undefined && (
                <span className={cn("rounded px-1.5 text-2xs tabular", n.tone === "danger" ? "bg-danger-soft font-semibold text-danger" : "text-fg-subtle")}>
                  {n.count}
                </span>
              )}
            </NavLink>
          ))}
        </nav>
        <div className="hidden md:block"><JobCard /></div>
        <div className="hidden border-t border-border px-4 py-3 text-2xs leading-relaxed text-fg-subtle md:block">
          First draft for the BRLM and legal counsel. Not for filing.
        </div>
      </aside>
      <main id="main" tabIndex={-1} className="min-h-0 min-w-0 flex-1 overflow-y-auto scroll-thin outline-none">{children}</main>
      {panel && !onAssistantPage && (
        // an overlay, not a column: the three-pane Draft page keeps its width
        <aside className="fixed bottom-0 right-0 top-14 z-40 flex w-[min(460px,100vw)] flex-col border-l border-border bg-surface shadow-pop animate-slide-in-right">
          <AssistantChat variant="panel" onClose={() => setPanel(false)} />
        </aside>
      )}
      {!panel && !onAssistantPage && project && (
        <button
          onClick={() => setPanel(true)}
          title="Ask the assistant (Ctrl+J)"
          className="fixed bottom-5 right-5 z-30 flex items-center gap-2 rounded-full bg-gradient-to-br from-primary to-[rgb(120_92_255)] py-2.5 pl-3 pr-4 text-[13px] font-semibold text-white shadow-pop transition-transform hover:-translate-y-0.5"
        >
          <Sparkles className="h-4 w-4" /> Ask
          <kbd className="rounded bg-white/20 px-1.5 py-0.5 font-mono text-[10px] font-medium">Ctrl J</kbd>
        </button>
      )}
    </div>
  );
}

export function Page({ children, className }: { children: ReactNode; className?: string }) {
  return <div className={cn("mx-auto w-full max-w-[1240px] px-8 pb-24 pt-7", className)}>{children}</div>;
}
