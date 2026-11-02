import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate } from "react-router-dom";
import {
  AlertTriangle, ArrowUp, Check, ChevronRight, Copy, Database, FileSpreadsheet, FileText, Loader2, RotateCcw, Search,
  ShieldCheck, Sparkles, Square, SquarePen, X, ClipboardList, Table2,
} from "lucide-react";
import { useApp, useProject } from "../lib/state";
import { chatHistory, clearChat, streamChat, type ChatMessage, type ChatSource } from "../lib/chat";
import { cn } from "../lib/utils";
import { Markdown } from "./Markdown";
import { Button, Tooltip, useToast } from "./ui";

const SUGGESTIONS = [
  { icon: <ClipboardList />, title: "What's still missing", prompt: "What's still missing from the issuer?" },
  { icon: <AlertTriangle />, title: "Main risk factors", prompt: "What are the main risk factors?" },
  { icon: <FileSpreadsheet />, title: "Look up a figure", prompt: "What is the revenue from operations for FY 2025-26?" },
  { icon: <FileText />, title: "Summarise a section", prompt: "Summarise the Objects of the Offer" },
];

export function AssistantMark({ size = "md" }: { size?: "sm" | "md" | "lg" }) {
  return (
    <span className={cn("flex shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-primary to-[rgb(120_92_255)] text-white shadow-sm",
      size === "sm" && "h-6 w-6 [&>svg]:h-3.5 [&>svg]:w-3.5", size === "md" && "h-7 w-7 [&>svg]:h-4 [&>svg]:w-4", size === "lg" && "h-11 w-11 [&>svg]:h-6 [&>svg]:w-6")}>
      <Sparkles />
    </span>
  );
}

function greeting() {
  const h = new Date().getHours();
  return h < 12 ? "Good morning" : h < 17 ? "Good afternoon" : "Good evening";
}

function SourceIcon({ kind }: { kind: ChatSource["kind"] }) {
  if (kind === "fact") return <Database className="h-3 w-3" />;
  if (kind === "table") return <Table2 className="h-3 w-3" />;
  if (kind === "section") return <FileText className="h-3 w-3" />;
  return <Search className="h-3 w-3" />;
}

function Steps({ m }: { m: ChatMessage }) {
  const [open, setOpen] = useState(false);
  const steps = m.steps || [];
  if (!steps.length) return null;
  const last = steps[steps.length - 1];
  const live = m.streaming && !m.content;
  const warn = steps.some((s) => s.status === "warn");
  return (
    <div className="mb-2 font-sans">
      <button onClick={() => setOpen((o) => !o)} className="group inline-flex items-center gap-1.5 rounded-md py-0.5 text-[12.5px] text-fg-muted hover:text-fg">
        {live ? <Loader2 className="h-3.5 w-3.5 animate-spin text-primary" /> : warn ? <AlertTriangle className="h-3.5 w-3.5 text-warning" /> : <ShieldCheck className="h-3.5 w-3.5 text-success" />}
        <span className={cn(live && "animate-pulse")}>
          {live ? last.label : `Researched · ${steps.length} step${steps.length > 1 ? "s" : ""}${m.sources?.length ? ` · ${m.sources.length} source${m.sources.length > 1 ? "s" : ""}` : ""}`}
        </span>
        <ChevronRight className={cn("h-3.5 w-3.5 transition-transform", open && "rotate-90")} />
      </button>
      {open && (
        <ol className="ml-1.5 mt-1.5 space-y-1.5 border-l border-border pl-4 animate-fade-in">
          {steps.map((s) => (
            <li key={s.id} className="relative text-[12.5px]">
              <span className={cn("absolute -left-[21px] top-1 flex h-2.5 w-2.5 items-center justify-center rounded-full ring-2 ring-surface",
                s.status === "warn" ? "bg-warning" : s.status === "running" ? "bg-primary" : "bg-success")} />
              <div className="font-medium text-fg">{s.label}</div>
              {s.detail && <div className="text-fg-subtle">{s.detail}</div>}
            </li>
          ))}
          {m.retrieval && <li className="text-2xs text-fg-subtle">Retrieval: {m.retrieval}{m.engine === "model" && m.model ? ` · answer by ${m.model}` : m.engine === "offline" ? " · offline answer (no model connected)" : ""}</li>}
        </ol>
      )}
    </div>
  );
}

function Sources({ sources, active, onOpen }: { sources: ChatSource[]; active: number | null; onOpen: (s: ChatSource) => void }) {
  const [all, setAll] = useState(false);
  if (!sources.length) return null;
  const shown = all ? sources : sources.slice(0, 4);
  return (
    <div className="mt-3 font-sans">
      <div className="mb-1.5 text-2xs font-semibold uppercase tracking-wider text-fg-subtle">Sources</div>
      <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
        {shown.map((s) => (
          <button key={s.n} id={`src-${s.n}`} onClick={() => onOpen(s)}
            className={cn("flex min-w-0 items-start gap-2 rounded-lg border px-2.5 py-2 text-left transition-colors",
              active === s.n ? "border-primary bg-primary-soft/50" : "border-border bg-surface hover:border-border-strong hover:bg-subtle/60")}>
            <span className="mt-px flex h-[18px] min-w-[18px] items-center justify-center rounded-md bg-primary-soft px-1 text-[10.5px] font-semibold text-primary">{s.n}</span>
            <span className="min-w-0 flex-1">
              <span className="flex items-center gap-1 truncate text-[12px] font-medium text-fg"><SourceIcon kind={s.kind} /> <span className="truncate">{s.file_name}</span></span>
              <span className="block truncate font-mono text-[10.5px] text-fg-subtle">{s.loc}</span>
              <span className="mt-0.5 line-clamp-2 text-[11.5px] text-fg-muted">
                {s.kind === "fact" ? `${s.label}${s.period ? ` (${s.period})` : ""}: ${s.value}` : s.quote || s.text}
              </span>
            </span>
          </button>
        ))}
      </div>
      {sources.length > 4 && (
        <button onClick={() => setAll((a) => !a)} className="mt-1.5 text-[12px] font-medium text-primary hover:underline">
          {all ? "Show fewer" : `Show all ${sources.length} sources`}
        </button>
      )}
    </div>
  );
}

function AssistantMessage({ m, onRetry, onOpenSource, onAction }: {
  m: ChatMessage; onRetry?: () => void; onOpenSource: (s: ChatSource) => void; onAction: (a: NonNullable<ChatMessage["actions"]>[number]) => void;
}) {
  const [active, setActive] = useState<number | null>(null);
  const [copied, setCopied] = useState(false);
  const cite = (n: number) => {
    setActive(n);
    document.getElementById(`src-${n}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" });
  };
  const title = (n: number) => {
    const s = m.sources?.find((x) => x.n === n);
    return s ? `${s.file_name} · ${s.loc}` : undefined;
  };
  return (
    <div className="group flex gap-3 animate-slide-up">
      <AssistantMark size="sm" />
      <div className="min-w-0 flex-1 pt-0.5">
        <Steps m={m} />
        {m.content ? (
          <div className="font-serif text-[15.5px] leading-[1.7] text-fg">
            <Markdown text={m.content} onCite={cite} citeTitle={title} />
            {m.streaming && <span className="ml-0.5 inline-block h-4 w-1.5 translate-y-0.5 animate-pulse rounded-sm bg-primary" />}
          </div>
        ) : m.streaming && !(m.steps || []).length ? (
          <div className="flex items-center gap-2 font-sans text-[13px] text-fg-muted"><Loader2 className="h-3.5 w-3.5 animate-spin" /> Thinking…</div>
        ) : null}
        {m.error && <div className="mt-2 rounded-md border border-danger/30 bg-danger-soft/50 px-3 py-2 font-sans text-[13px] text-danger">{m.error}</div>}
        {(m.actions || []).length > 0 && (
          <div className="mt-3 flex flex-wrap gap-2 font-sans">
            {m.actions!.map((a, i) => (
              <Button key={i} size="sm" variant="soft" icon={a.kind === "draft" ? <FileText className="h-3.5 w-3.5" /> : <SquarePen className="h-3.5 w-3.5" />} onClick={() => onAction(a)}>
                {a.label}
              </Button>
            ))}
          </div>
        )}
        {!m.streaming && <Sources sources={m.sources || []} active={active} onOpen={onOpenSource} />}
        {!m.streaming && m.content && (
          <div className="mt-2 flex items-center gap-0.5 font-sans opacity-0 transition-opacity group-hover:opacity-100">
            <Tooltip content={copied ? "Copied" : "Copy"}>
              <Button size="icon-sm" variant="ghost" aria-label="Copy answer" onClick={() => { navigator.clipboard?.writeText(m.content); setCopied(true); setTimeout(() => setCopied(false), 1500); }}>
                {copied ? <Check className="h-3.5 w-3.5 text-success" /> : <Copy className="h-3.5 w-3.5" />}
              </Button>
            </Tooltip>
            {onRetry && (
              <Tooltip content="Ask again">
                <Button size="icon-sm" variant="ghost" aria-label="Ask again" onClick={onRetry}><RotateCcw className="h-3.5 w-3.5" /></Button>
              </Tooltip>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

function Composer({ onSend, onStop, busy, compact, engine, autoFocus }: { onSend: (t: string) => void; onStop: () => void; busy: boolean; compact?: boolean; engine: string; autoFocus?: boolean }) {
  const [v, setV] = useState("");
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (el) { el.style.height = "auto"; el.style.height = `${Math.min(el.scrollHeight, compact ? 140 : 200)}px`; }
  }, [v, compact]);
  const send = () => {
    const t = v.trim();
    if (!t || busy) return;
    onSend(t);
    setV("");
  };
  return (
    <div className="rounded-2xl border border-border-strong bg-surface shadow-[0_2px_12px_-4px_rgb(15_23_42/0.12)] transition-shadow focus-within:border-primary/50 focus-within:shadow-[0_4px_20px_-6px_rgb(47_79_216/0.25)]">
      <textarea
        ref={ref}
        rows={1}
        value={v}
        autoFocus={autoFocus}
        onChange={(e) => setV(e.target.value)}
        onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send(); } }}
        placeholder="Ask about the issuer's files, or say “draft Our Business”…"
        className={cn("block w-full resize-none bg-transparent px-4 pt-3.5 text-fg placeholder:text-fg-subtle focus:outline-none", compact ? "text-[14px]" : "text-[15px]")}
      />
      <div className="flex items-center justify-between gap-2 px-3 pb-2.5 pt-1.5">
        <span className="inline-flex items-center gap-1.5 rounded-md bg-subtle px-2 py-1 text-2xs font-medium text-fg-muted">
          <Search className="h-3 w-3" /> {engine}
        </span>
        {busy ? (
          <button onClick={onStop} aria-label="Stop" className="flex h-8 w-8 items-center justify-center rounded-full bg-fg text-bg transition-opacity hover:opacity-80">
            <Square className="h-3 w-3 fill-current" />
          </button>
        ) : (
          <button onClick={send} disabled={!v.trim()} aria-label="Send" className="flex h-8 w-8 items-center justify-center rounded-full bg-primary text-primary-fg transition-all hover:bg-primary/90 disabled:bg-muted disabled:text-fg-subtle">
            <ArrowUp className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}

export function AssistantChat({ variant = "page", onClose }: { variant?: "page" | "panel"; onClose?: () => void }) {
  const { project, startJob, refresh } = useProject();
  const { health } = useApp();
  const nav = useNavigate();
  const toast = useToast();
  const pid = project?.id ?? "";
  const [msgs, setMsgs] = useState<ChatMessage[] | null>(null);
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const stick = useRef(true);
  const compact = variant === "panel";

  useEffect(() => { if (pid) chatHistory(pid).then(setMsgs).catch(() => setMsgs([])); }, [pid]);
  useEffect(() => {
    const el = scroller.current;
    if (el && stick.current) el.scrollTop = el.scrollHeight;
  }, [msgs]);

  const engine = health?.use_model ? `${health.model_name} · agentic RAG` : "Offline · agentic RAG over issuer files";

  const send = useCallback(async (text: string) => {
    if (!pid) return;
    stick.current = true;
    const user: ChatMessage = { id: `tmp-u-${Date.now()}`, role: "user", content: text };
    const asst: ChatMessage = { id: `tmp-a-${Date.now()}`, role: "assistant", content: "", steps: [], sources: [], actions: [], streaming: true };
    setMsgs((m) => [...(m || []), user, asst]);
    setBusy(true);
    const ctl = new AbortController();
    abort.current = ctl;
    const upd = (f: (a: ChatMessage) => ChatMessage) => setMsgs((ms) => (ms || []).map((x) => (x.id === asst.id ? f(x) : x)));
    try {
      await streamChat(pid, text, (e) => {
        if (e.type === "delta") upd((a) => ({ ...a, content: a.content + e.text }));
        else if (e.type === "step") upd((a) => ({ ...a, steps: [...(a.steps || []), { id: e.id, label: e.label, detail: e.detail, status: e.status }] }));
        else if (e.type === "meta") upd((a) => ({ ...a, sources: e.sources, engine: e.engine, retrieval: e.retrieval, model: e.model }));
        else if (e.type === "action") {
          upd((a) => ({ ...a, actions: [...(a.actions || []), e.action] }));
          if (e.action.kind === "draft" && e.action.job) startJob(e.action.job);
          if (e.action.kind === "autofill") refresh();
        }
      }, ctl.signal);
      upd((a) => ({ ...a, streaming: false }));
    } catch (err) {
      const aborted = (err as Error).name === "AbortError";
      upd((a) => ({ ...a, streaming: false, error: aborted ? undefined : (err as Error).message, content: a.content + (aborted ? "\n\n_Stopped._" : "") }));
    } finally {
      setBusy(false);
      abort.current = null;
    }
  }, [pid, startJob, refresh]);

  const newChat = async () => {
    abort.current?.abort();
    await clearChat(pid);
    setMsgs([]);
  };

  const openSource = (s: ChatSource) => {
    if (s.kind === "section" && s.section) return nav(`/p/${pid}/draft/${s.section}`);
    if (s.kind === "review") return nav(`/p/${pid}/review`);
    if (s.file_id) nav(`/p/${pid}/documents?file=${s.file_id}&tab=text&loc=${encodeURIComponent(s.loc.split(/,| \(| –/)[0])}`);
    else toast("info", s.file_name, s.loc);
  };
  const onAction = (a: NonNullable<ChatMessage["actions"]>[number]) => {
    if (a.kind === "draft") nav(`/p/${pid}/draft${a.section ? `/${a.section}` : ""}`);
    else nav(`/p/${pid}/offer`);
  };

  const empty = msgs !== null && msgs.length === 0;
  const company = project?.offer.company_name || project?.name || "the issuer";

  return (
    <div className={cn("flex h-full min-h-0 flex-col", variant === "page" ? "bg-bg" : "bg-surface")}>
      <div className={cn("flex shrink-0 items-center justify-between gap-3 border-b border-border", compact ? "px-4 py-2.5" : "px-6 py-3")}>
        <div className="flex min-w-0 items-center gap-2.5">
          <AssistantMark size="sm" />
          <div className="min-w-0">
            <div className="text-[13.5px] font-semibold text-fg">DRHP Assistant</div>
            <div className="truncate text-2xs text-fg-subtle">Agentic retrieval over {company}'s files, draft and review pack</div>
          </div>
        </div>
        <div className="flex items-center gap-1">
          {!empty && <Button size="sm" variant="ghost" icon={<SquarePen className="h-3.5 w-3.5" />} onClick={newChat}>New chat</Button>}
          {onClose && <Button size="icon-sm" variant="ghost" onClick={onClose} aria-label="Close assistant"><X className="h-4 w-4" /></Button>}
        </div>
      </div>

      <div ref={scroller} className="min-h-0 flex-1 overflow-y-auto scroll-thin"
        onScroll={(e) => { const el = e.currentTarget; stick.current = el.scrollHeight - el.scrollTop - el.clientHeight < 80; }}>
        <div className={cn("mx-auto w-full", compact ? "px-4 py-5" : "max-w-[760px] px-6 py-8")}>
          {msgs === null ? (
            <div className="flex justify-center py-20"><Loader2 className="h-5 w-5 animate-spin text-fg-subtle" /></div>
          ) : empty ? (
            <div className={cn("flex flex-col items-center text-center", compact ? "pt-6" : "pt-[10vh]")}>
              <AssistantMark size="lg" />
              <h1 className={cn("mt-5 font-serif font-semibold tracking-tight text-fg", compact ? "text-[22px]" : "text-[30px]")}>
                {greeting()}. How can I help with the {company} DRHP?
              </h1>
              <p className="mt-2 max-w-md text-[13px] text-fg-muted">
                I plan each question, search the issuer's passages, schedules and facts, check the draft and the review pack, and cite every source.
              </p>
              <div className={cn("mt-7 grid w-full gap-2.5", compact ? "grid-cols-1" : "grid-cols-2")}>
                {SUGGESTIONS.map((s) => (
                  <button key={s.title} onClick={() => send(s.prompt)}
                    className="group flex items-start gap-3 rounded-xl border border-border bg-surface px-4 py-3 text-left shadow-card transition-all hover:-translate-y-px hover:border-border-strong hover:shadow-pop">
                    <span className="mt-0.5 text-primary [&>svg]:h-4 [&>svg]:w-4">{s.icon}</span>
                    <span>
                      <span className="block text-[13px] font-semibold text-fg">{s.title}</span>
                      <span className="block text-[12px] text-fg-muted">{s.prompt}</span>
                    </span>
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-7">
              {msgs.map((m, i) =>
                m.role === "user" ? (
                  <div key={m.id} className="flex justify-end animate-slide-up">
                    <div className="max-w-[85%] whitespace-pre-wrap rounded-2xl rounded-br-md bg-muted px-4 py-2.5 text-[14.5px] leading-relaxed text-fg">{m.content}</div>
                  </div>
                ) : (
                  <AssistantMessage key={m.id} m={m} onOpenSource={openSource} onAction={onAction}
                    onRetry={!busy && i === msgs.length - 1 && msgs[i - 1]?.role === "user" ? () => send(msgs[i - 1].content) : undefined} />
                ),
              )}
            </div>
          )}
        </div>
      </div>

      <div className={cn("shrink-0", compact ? "px-3 pb-3" : "px-6 pb-5")}>
        <div className={cn("mx-auto", !compact && "max-w-[760px]")}>
          <Composer onSend={send} onStop={() => abort.current?.abort()} busy={busy} compact={compact} engine={engine} autoFocus={variant === "panel"} />
          <p className="mt-2 text-center text-2xs text-fg-subtle">Answers come from the issuer's files and can be wrong or incomplete. Check the cited sources.</p>
        </div>
      </div>
    </div>
  );
}
