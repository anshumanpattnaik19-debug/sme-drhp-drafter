import type { Job } from "./types";

export interface ChatSource {
  n: number;
  kind: "fact" | "passage" | "table" | "section" | "review";
  file_id?: string | null;
  file_name: string;
  loc: string;
  label: string;
  value?: string;
  period?: string;
  quote?: string;
  text?: string;
  section?: string;
}

export interface ChatStep {
  id: number;
  label: string;
  detail: string;
  status: "running" | "done" | "warn";
}

export interface ChatAction {
  kind: "draft" | "autofill";
  label: string;
  section?: string | null;
  job?: Job;
  filled?: Record<string, string>;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  sources?: ChatSource[];
  steps?: ChatStep[];
  actions?: ChatAction[];
  engine?: string | null;
  retrieval?: string | null;
  model?: string | null;
  created_at?: string;
  streaming?: boolean;
  error?: string;
}

export type ChatEvent =
  | { type: "start"; id: string; user_id: string }
  | { type: "meta"; engine: string; sources: ChatSource[]; retrieval?: string; model?: string }
  | ({ type: "step" } & ChatStep)
  | { type: "delta"; text: string }
  | { type: "action"; action: ChatAction }
  | { type: "done" };

export async function chatHistory(pid: string): Promise<ChatMessage[]> {
  const r = await fetch(`/api/projects/${pid}/chat`);
  if (!r.ok) return [];
  return (await r.json()).messages as ChatMessage[];
}

export async function clearChat(pid: string) {
  await fetch(`/api/projects/${pid}/chat`, { method: "DELETE" });
}

/** POST a message and call onEvent for every NDJSON event as it streams in. */
export async function streamChat(pid: string, message: string, onEvent: (e: ChatEvent) => void, signal?: AbortSignal) {
  const res = await fetch(`/api/projects/${pid}/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
    signal,
  });
  if (!res.ok || !res.body) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail; } catch { /* not json */ }
    throw new Error(msg || "The assistant did not respond.");
  }
  const reader = res.body.getReader();
  const dec = new TextDecoder();
  let buf = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buf += dec.decode(value, { stream: true });
    let i: number;
    while ((i = buf.indexOf("\n")) >= 0) {
      const line = buf.slice(0, i).trim();
      buf = buf.slice(i + 1);
      if (line) {
        try { onEvent(JSON.parse(line) as ChatEvent); } catch { /* ignore a partial line */ }
      }
    }
  }
}
