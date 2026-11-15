import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { ArrowRight, Building2, FileStack, FolderOpen, MoreHorizontal, Plus, Search, Trash2, Upload, Database, FileText, Download } from "lucide-react";
import { api } from "../lib/api";
import type { Project } from "../lib/types";
import { ago, BOARD_LABEL, num } from "../lib/utils";
import { Badge, Button, Card, Dialog, EmptyState, Field, Input, Menu, Progress, Segmented, Skeleton, useToast } from "../components/ui";

function NewProjectDialog({ open, onClose }: { open: boolean; onClose: () => void }) {
  const nav = useNavigate();
  const toast = useToast();
  const [name, setName] = useState("");
  const [board, setBoard] = useState<"bse_sme" | "nse_emerge">("bse_sme");
  const [lm, setLm] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => { if (open) { setName(""); setLm(""); setBoard("bse_sme"); } }, [open]);

  const create = async () => {
    if (!name.trim()) return;
    setBusy(true);
    try {
      const p = await api.createProject(name.trim(), board, lm.trim() ? { lead_manager: lm.trim() } : undefined);
      onClose();
      nav(`/p/${p.id}/documents`);
    } catch (e) {
      toast("error", "Could not create project", (e as Error).message);
    } finally {
      setBusy(false);
    }
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      title="New DRHP project"
      description="One project per issuer. You can change everything later under Offer details."
      footer={
        <>
          <Button variant="ghost" onClick={onClose}>Cancel</Button>
          <Button variant="primary" onClick={create} loading={busy} disabled={!name.trim()}>Create project</Button>
        </>
      }
    >
      <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); create(); }}>
        <Field label="Issuer company name" required hint="As it will appear on the cover page, e.g. “Ashtavira Flexipak Limited”.">
          <Input autoFocus value={name} onChange={(e) => setName(e.target.value)} placeholder="Company name" />
        </Field>
        <Field label="SME platform">
          <Segmented value={board} onChange={setBoard} options={[{ value: "bse_sme", label: "BSE SME" }, { value: "nse_emerge", label: "NSE Emerge" }]} />
        </Field>
        <Field label="Book Running Lead Manager" hint="Optional">
          <Input value={lm} onChange={(e) => setLm(e.target.value)} placeholder="Lead manager" />
        </Field>
      </form>
    </Dialog>
  );
}

const STEPS = [
  { icon: <Upload />, title: "Upload issuer files", body: "PDF, scanned PDF, Word, Excel and images. Each file is read, classified and indexed." },
  { icon: <Database />, title: "Check the facts", body: "Typed facts with file and page. Edit, add and mark them reviewed." },
  { icon: <FileText />, title: "Draft section by section", body: "Templates, code tables and the fine-tuned SLM, in SME section order." },
  { icon: <Download />, title: "Review and export", body: "Missing inputs, ungrounded figures and checklist gaps, then a .docx draft." },
];

export default function ProjectsPage() {
  const nav = useNavigate();
  const toast = useToast();
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [q, setQ] = useState("");
  const [creating, setCreating] = useState(false);
  const [confirm, setConfirm] = useState<Project | null>(null);

  const load = () => api.projects().then(setProjects).catch((e) => { setProjects([]); toast("error", "Could not load projects", e.message); });
  useEffect(() => { load(); }, []); // eslint-disable-line react-hooks/exhaustive-deps

  const del = async () => {
    if (!confirm) return;
    await api.deleteProject(confirm.id).catch((e) => toast("error", "Delete failed", e.message));
    setConfirm(null);
    load();
  };

  const shown = (projects ?? []).filter((p) => (p.offer.company_name || p.name).toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="h-full overflow-y-auto scroll-thin">
      <div className="mx-auto max-w-[1120px] px-8 py-8">
        <div className="mb-7 flex flex-wrap items-end justify-between gap-4">
          <div>
            <h1 className="text-2xl font-semibold tracking-tight text-fg">DRHP projects</h1>
            <p className="mt-1 text-[13px] text-fg-muted">Draft SME offer documents from the issuer's own files. Every figure keeps its source.</p>
          </div>
          <div className="flex items-center gap-2">
            {projects && projects.length > 0 && (
              <Input icon={<Search className="h-4 w-4" />} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search projects" className="w-56" />
            )}
            <Button variant="primary" icon={<Plus className="h-4 w-4" />} onClick={() => setCreating(true)}>New project</Button>
          </div>
        </div>

        {projects === null ? (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {[0, 1, 2].map((i) => <Skeleton key={i} className="h-44 rounded-lg" />)}
          </div>
        ) : projects.length === 0 ? (
          <Card className="overflow-hidden">
            <div className="grid gap-0 md:grid-cols-[1.1fr_1fr]">
              <div className="p-8">
                <Badge tone="primary">Getting started</Badge>
                <h2 className="mt-3 text-lg font-semibold tracking-tight">Create your first DRHP project</h2>
                <p className="mt-1.5 max-w-md text-[13px] leading-relaxed text-fg-muted">
                  Start with the issuer's name, then drop in the folder of documents the company handed to the lead manager.
                  The drafter reads every format, extracts typed facts and drafts each section with its sources.
                </p>
                <Button variant="primary" className="mt-6" icon={<Plus className="h-4 w-4" />} onClick={() => setCreating(true)}>New project</Button>
              </div>
              <div className="border-t border-border bg-subtle/60 p-6 md:border-l md:border-t-0">
                <ol className="space-y-4">
                  {STEPS.map((s, i) => (
                    <li key={s.title} className="flex gap-3">
                      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border bg-surface text-primary [&>svg]:h-4 [&>svg]:w-4">{s.icon}</span>
                      <div>
                        <div className="text-[13px] font-semibold text-fg"><span className="mr-1 text-fg-subtle tabular">{i + 1}.</span>{s.title}</div>
                        <div className="text-xs leading-relaxed text-fg-muted">{s.body}</div>
                      </div>
                    </li>
                  ))}
                </ol>
              </div>
            </div>
          </Card>
        ) : shown.length === 0 ? (
          <EmptyState icon={<Search />} title="No matching projects" description={`Nothing matches “${q}”.`} />
        ) : (
          <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
            {shown.map((p) => {
              const s = p.stats;
              return (
                <Card
                  key={p.id}
                  role="link"
                  tabIndex={0}
                  aria-label={`Open project ${p.offer.company_name || p.name}`}
                  className="group cursor-pointer p-5 transition-shadow hover:shadow-pop"
                  onClick={() => nav(`/p/${p.id}/overview`)}
                  onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); nav(`/p/${p.id}/overview`); } }}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary-soft text-primary"><Building2 className="h-4 w-4" /></div>
                    <Menu
                      trigger={<Button variant="ghost" size="icon-sm" aria-label="Project actions"><MoreHorizontal className="h-4 w-4" /></Button>}
                      items={[
                        { label: "Open", icon: <FolderOpen />, onClick: () => nav(`/p/${p.id}/overview`) },
                        "sep",
                        { label: "Delete project", icon: <Trash2 />, danger: true, onClick: () => setConfirm(p) },
                      ]}
                    />
                  </div>
                  <h3 className="mt-3 line-clamp-1 text-[15px] font-semibold tracking-tight text-fg">{p.offer.company_name || p.name}</h3>
                  <div className="mt-1 flex items-center gap-1.5">
                    <Badge tone="primary">{BOARD_LABEL[p.offer.board || "bse_sme"]}</Badge>
                    {p.offer.lead_manager && <span className="truncate text-xs text-fg-subtle">{p.offer.lead_manager}</span>}
                  </div>
                  <div className="mt-4 grid grid-cols-3 gap-2 border-t border-border pt-3 text-xs">
                    <div><div className="text-fg-subtle">Files</div><div className="mt-0.5 font-semibold tabular text-fg">{num(s.files)}</div></div>
                    <div><div className="text-fg-subtle">Facts</div><div className="mt-0.5 font-semibold tabular text-fg">{num(s.facts)}</div></div>
                    <div><div className="text-fg-subtle">Sections</div><div className="mt-0.5 font-semibold tabular text-fg">{s.drafted}/{s.sections}</div></div>
                  </div>
                  <Progress value={s.drafted / s.sections} className="mt-3" />
                  <div className="mt-3 flex items-center justify-between text-xs text-fg-subtle">
                    <span className="flex items-center gap-1"><FileStack className="h-3 w-3" /> Updated {ago(p.updated_at)}</span>
                    <ArrowRight className="h-3.5 w-3.5 opacity-0 transition-opacity group-hover:opacity-100" />
                  </div>
                </Card>
              );
            })}
          </div>
        )}
      </div>
      <NewProjectDialog open={creating} onClose={() => setCreating(false)} />
      <Dialog
        open={!!confirm}
        onClose={() => setConfirm(null)}
        title="Delete project?"
        description={`“${confirm?.offer.company_name || confirm?.name}” and all its uploaded files, facts and drafts will be removed from this machine. This cannot be undone.`}
        footer={<><Button variant="ghost" onClick={() => setConfirm(null)}>Cancel</Button><Button variant="danger" onClick={del}>Delete project</Button></>}
      >
        <span />
      </Dialog>
    </div>
  );
}
