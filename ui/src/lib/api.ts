import type {
  Draft, DraftBlock, Fact, Health, IssuerFile, Job, Meta, Offer, Project, Review, SectionDef, SectionRow, Settings, Block,
} from "./types";

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function req<T>(method: string, url: string, body?: unknown): Promise<T> {
  const init: RequestInit = { method, headers: {} };
  if (body instanceof FormData) init.body = body;
  else if (body !== undefined) {
    init.body = JSON.stringify(body);
    (init.headers as Record<string, string>)["Content-Type"] = "application/json";
  }
  let res: Response;
  try {
    res = await fetch(url, init);
  } catch {
    throw new ApiError(0, "Cannot reach the drafting service. Is it running on port 8765?");
  }
  if (!res.ok) {
    let msg = res.statusText;
    try {
      const j = await res.json();
      msg = typeof j.detail === "string" ? j.detail : JSON.stringify(j.detail);
    } catch { /* not json */ }
    throw new ApiError(res.status, msg);
  }
  return res.json() as Promise<T>;
}

const P = (pid: string) => `/api/projects/${pid}`;

export const api = {
  health: () => req<Health>("GET", "/api/health"),
  meta: () => req<Meta>("GET", "/api/meta"),
  settings: () => req<Settings>("GET", "/api/settings"),
  saveSettings: (s: Partial<Settings>) => req<Settings>("PUT", "/api/settings", s),
  testModel: (s: Partial<Settings>) =>
    req<{ reachable: boolean; models: string[]; latency_ms: number | null; error: string | null }>("POST", "/api/settings/test", s),

  projects: () => req<Project[]>("GET", "/api/projects"),
  createProject: (name: string, board: string, offer?: Offer) => req<Project>("POST", "/api/projects", { name, board, offer }),
  project: (pid: string) => req<Project & { files: IssuerFile[] }>("GET", P(pid)),
  patchProject: (pid: string, patch: { name?: string; offer?: Offer }) => req<Project>("PATCH", P(pid), patch),
  deleteProject: (pid: string) => req<{ ok: boolean }>("DELETE", P(pid)),

  upload: (pid: string, files: { file: File; path: string }[]) => {
    const fd = new FormData();
    files.forEach(({ file, path }) => {
      fd.append("files", file, file.name);
      fd.append("paths", path);
    });
    return req<{ added: IssuerFile[]; rejected: { name: string; reason: string }[] }>("POST", `${P(pid)}/files`, fd);
  },
  file: (pid: string, fid: string) => req<IssuerFile & { blocks: Block[]; facts: Fact[] }>("GET", `${P(pid)}/files/${fid}`),
  rawUrl: (pid: string, fid: string) => `${P(pid)}/files/${fid}/raw`,
  patchFile: (pid: string, fid: string, doc_type: string) => req<IssuerFile>("PATCH", `${P(pid)}/files/${fid}`, { doc_type }),
  deleteFile: (pid: string, fid: string) => req<{ ok: boolean }>("DELETE", `${P(pid)}/files/${fid}`),
  process: (pid: string, opts: { file_ids?: string[]; force?: boolean } = {}) => req<Job>("POST", `${P(pid)}/process`, opts),

  facts: (pid: string) => req<Fact[]>("GET", `${P(pid)}/facts`),
  addFact: (pid: string, f: Partial<Fact>) => req<Fact>("POST", `${P(pid)}/facts`, f),
  patchFact: (pid: string, id: string, patch: Partial<Fact>) => req<Fact>("PATCH", `${P(pid)}/facts/${id}`, patch),
  deleteFact: (pid: string, id: string) => req<{ ok: boolean }>("DELETE", `${P(pid)}/facts/${id}`),

  sections: (pid: string) => req<SectionRow[]>("GET", `${P(pid)}/sections`),
  section: (pid: string, key: string) => req<{ section: SectionDef; draft: Draft | null }>("GET", `${P(pid)}/sections/${key}`),
  draft: (pid: string, keys?: string[], skip_drafted = false) => req<Job>("POST", `${P(pid)}/draft`, { keys, skip_drafted }),
  saveSection: (pid: string, key: string, blocks: DraftBlock[]) => req<Draft>("PUT", `${P(pid)}/sections/${key}`, { blocks }),
  clearSection: (pid: string, key: string) => req<{ ok: boolean }>("DELETE", `${P(pid)}/sections/${key}`),
  signoff: (pid: string, key: string, reviewed: boolean, reviewer = "", note = "") =>
    req<Draft>("POST", `${P(pid)}/sections/${key}/signoff`, { reviewed, reviewer, note }),
  autofill: (pid: string, overwrite = false) =>
    req<{ filled: Record<string, string>; offer: Offer; offer_sources: Record<string, unknown> }>("POST", `${P(pid)}/offer/autofill`, { overwrite }),

  job: (id: string) => req<Job>("GET", `/api/jobs/${id}`),
  jobs: (pid: string) => req<Job[]>("GET", `${P(pid)}/jobs`),
  cancelJob: (id: string) => req<Job>("POST", `/api/jobs/${id}/cancel`),

  review: (pid: string) => req<Review>("GET", `${P(pid)}/review`),
  exportUrl: (pid: string, include_review: boolean, include_sources: boolean) =>
    `${P(pid)}/export.docx?include_review=${include_review}&include_sources=${include_sources}`,
};
