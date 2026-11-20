import { createContext, useCallback, useContext, useEffect, useRef, useState, type ReactNode } from "react";
import { api } from "./api";
import type { Health, IssuerFile, Job, Meta, Project } from "./types";
import { useToast } from "../components/ui";

/* ---------------- App ---------------- */

interface AppState {
  meta: Meta | null;
  health: Health | null;
  healthChecked: boolean;      // false until the first answer or failure: the header says "Checking" rather than "offline"
  refreshHealth: () => void;
  settingsOpen: boolean;
  openSettings: (open?: boolean) => void;
  theme: "light" | "dark";
  toggleTheme: () => void;
}

const AppCtx = createContext<AppState>(null as unknown as AppState);

export function AppProvider({ children }: { children: ReactNode }) {
  const [meta, setMeta] = useState<Meta | null>(null);
  const [health, setHealth] = useState<Health | null>(null);
  const [healthChecked, setHealthChecked] = useState(false);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [theme, setTheme] = useState<"light" | "dark">(() => (document.documentElement.classList.contains("dark") ? "dark" : "light"));

  const refreshHealth = useCallback(() => {
    api.health().then(setHealth).catch(() => setHealth(null)).finally(() => setHealthChecked(true));
  }, []);

  useEffect(() => {
    api.meta().then(setMeta).catch(() => {});
    refreshHealth();
    const t = setInterval(refreshHealth, 30000);
    return () => clearInterval(t);
  }, [refreshHealth]);

  const toggleTheme = useCallback(() => {
    setTheme((t) => {
      const next = t === "dark" ? "light" : "dark";
      document.documentElement.classList.toggle("dark", next === "dark");
      try { localStorage.setItem("theme", next); } catch { /* storage unavailable */ }
      return next;
    });
  }, []);

  return (
    <AppCtx.Provider value={{ meta, health, healthChecked, refreshHealth, settingsOpen, openSettings: (o = true) => setSettingsOpen(o), theme, toggleTheme }}>
      {children}
    </AppCtx.Provider>
  );
}

export const useApp = () => useContext(AppCtx);

/* ---------------- Project ---------------- */

interface ProjectState {
  project: (Project & { files: IssuerFile[] }) | null;
  error: string | null;
  refresh: () => Promise<void>;
  job: Job | null;
  startJob: (j: Job) => void;
  cancelJob: () => void;
  /** increments whenever a job finishes, so pages can refetch derived data */
  version: number;
  bump: () => void;
}

const ProjectCtx = createContext<ProjectState>(null as unknown as ProjectState);

export function ProjectProvider({ pid, children }: { pid: string; children: ReactNode }) {
  const toast = useToast();
  const [project, setProject] = useState<ProjectState["project"]>(null);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<Job | null>(null);
  const [version, setVersion] = useState(0);
  const timer = useRef<number | null>(null);

  const refresh = useCallback(async () => {
    try {
      setProject(await api.project(pid));
      setError(null);
    } catch (e) {
      setError((e as Error).message);
    }
  }, [pid]);

  const poll = useCallback(
    (id: string) => {
      let ticks = 0;
      const step = async () => {
        try {
          const j = await api.job(id);
          setJob(j);
          if (j.status === "running") {
            ticks++;
            if (j.kind === "process" || ticks % 3 === 0) refresh();
            if (j.kind === "draft") setVersion((v) => v + 1);
            timer.current = window.setTimeout(step, 900);
          } else {
            await refresh();
            setVersion((v) => v + 1);
            const errs = j.errors.length;
            if (j.status === "cancelled") toast("info", "Job cancelled", `${j.done} of ${j.total} completed`);
            else if (j.status === "failed") toast("error", "Job failed", j.message);
            else if (errs) toast("error", `${j.label}: finished with ${errs} error(s)`, j.errors[0]?.error);
            else toast("success", j.kind === "process" ? "Documents processed" : "Drafting complete", `${j.done} of ${j.total} done`);
            window.setTimeout(() => setJob((cur) => (cur && cur.id === j.id ? null : cur)), 2500);
          }
        } catch {
          timer.current = window.setTimeout(step, 2000);
        }
      };
      step();
    },
    [refresh, toast],
  );

  const startJob = useCallback((j: Job) => {
    if (timer.current) clearTimeout(timer.current);
    setJob(j);
    poll(j.id);
  }, [poll]);

  const cancelJob = useCallback(() => {
    if (job) api.cancelJob(job.id).catch(() => {});
  }, [job]);

  useEffect(() => {
    setProject(null);
    refresh();
    api.jobs(pid).then((js) => {
      const running = js.find((j) => j.status === "running");
      if (running) startJob(running);
    }).catch(() => {});
    return () => { if (timer.current) clearTimeout(timer.current); };
  }, [pid, refresh, startJob]);

  return (
    <ProjectCtx.Provider value={{ project, error, refresh, job, startJob, cancelJob, version, bump: () => setVersion((v) => v + 1) }}>
      {children}
    </ProjectCtx.Provider>
  );
}

export const useProject = () => useContext(ProjectCtx);
