import { useEffect, useState } from "react";
import { Bot, CheckCircle2, FlaskConical, ScanText, XCircle } from "lucide-react";
import { api } from "../lib/api";
import { useApp } from "../lib/state";
import type { Settings } from "../lib/types";
import { cn } from "../lib/utils";
import { Badge, Button, Dialog, Field, Input, Switch, useToast } from "./ui";

function EngineCard({ active, onClick, icon, title, body }: { active: boolean; onClick: () => void; icon: React.ReactNode; title: string; body: string }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={cn(
        "flex flex-1 items-start gap-3 rounded-lg border p-3.5 text-left transition-colors",
        active ? "border-primary bg-primary-soft/60 ring-1 ring-primary" : "border-border hover:border-border-strong hover:bg-subtle",
      )}
    >
      <span className={cn("mt-0.5 [&>svg]:h-4 [&>svg]:w-4", active ? "text-primary" : "text-fg-subtle")}>{icon}</span>
      <span>
        <span className="block text-[13px] font-semibold text-fg">{title}</span>
        <span className="mt-0.5 block text-xs leading-relaxed text-fg-muted">{body}</span>
      </span>
    </button>
  );
}

export function SettingsDialog() {
  const { settingsOpen, openSettings, health, refreshHealth } = useApp();
  const toast = useToast();
  const [s, setS] = useState<Settings | null>(null);
  const [saving, setSaving] = useState(false);
  const [testing, setTesting] = useState(false);
  const [test, setTest] = useState<{ reachable: boolean; models: string[]; latency_ms: number | null; error: string | null } | null>(null);

  useEffect(() => {
    if (settingsOpen) {
      setTest(null);
      api.settings().then(setS).catch((e) => toast("error", "Could not load settings", e.message));
    }
  }, [settingsOpen, toast]);

  const set = <K extends keyof Settings>(k: K, v: Settings[K]) => setS((x) => (x ? { ...x, [k]: v } : x));

  const save = async () => {
    if (!s) return;
    setSaving(true);
    try {
      await api.saveSettings(s);
      refreshHealth();
      toast("success", "Settings saved");
      openSettings(false);
    } catch (e) {
      toast("error", "Could not save settings", (e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const runTest = async () => {
    if (!s) return;
    setTesting(true);
    try {
      setTest(await api.testModel(s));
    } finally {
      setTesting(false);
    }
  };

  return (
    <Dialog
      open={settingsOpen}
      onClose={() => openSettings(false)}
      title="Settings"
      description="Drafting engine and document reading. Settings apply to all projects on this machine."
      width="max-w-2xl"
      footer={
        <>
          <Button variant="ghost" onClick={() => openSettings(false)}>Cancel</Button>
          <Button variant="primary" onClick={save} loading={saving} disabled={!s}>Save settings</Button>
        </>
      }
    >
      {!s ? (
        <div className="h-64" />
      ) : (
        <div className="space-y-6">
          <section>
            <h4 className="mb-2.5 text-xs font-semibold uppercase tracking-wider text-fg-subtle">Drafting engine</h4>
            <div className="flex gap-3">
              <EngineCard
                active={!s.use_model}
                onClick={() => set("use_model", false)}
                icon={<FlaskConical />}
                title="Offline mock writer"
                body="Runs on this laptop with no GPU. Composes grounded sentences from routed facts to exercise the pipeline. Not representative of model quality."
              />
              <EngineCard
                active={s.use_model}
                onClick={() => set("use_model", true)}
                icon={<Bot />}
                title="Fine-tuned SLM endpoint"
                body="An OpenAI-compatible server (vLLM) serving the fine-tuned Qwen2.5-7B adapter. SLM sections are drafted by the model."
              />
            </div>
            <div className={cn("mt-4 grid grid-cols-2 gap-4 transition-opacity", !s.use_model && "pointer-events-none opacity-50")}>
              <Field label="Endpoint URL" className="col-span-2" hint="Base URL of the OpenAI-compatible API, e.g. http://localhost:8000/v1">
                <Input value={s.model_url} onChange={(e) => set("model_url", e.target.value)} placeholder="http://localhost:8000/v1" />
              </Field>
              <Field label="Model name">
                <Input value={s.model_name} onChange={(e) => set("model_name", e.target.value)} />
              </Field>
              <Field label="API key" hint={s.api_key_set ? "A key is stored. Leave blank to keep it." : "Optional. Local vLLM needs none."}>
                <Input type="password" value={s.api_key} onChange={(e) => set("api_key", e.target.value)} placeholder={s.api_key_set ? "••••••••" : ""} autoComplete="off" />
              </Field>
              <Field label={<>Temperature <span className="font-normal text-fg-subtle tabular">{s.temperature.toFixed(2)}</span></>}>
                <input type="range" min={0} max={1} step={0.05} value={s.temperature} onChange={(e) => set("temperature", Number(e.target.value))} className="w-full accent-[rgb(var(--primary))]" />
              </Field>
              <Field label="Max tokens per section">
                <Input type="number" min={256} max={8192} value={s.max_tokens} onChange={(e) => set("max_tokens", Number(e.target.value))} />
              </Field>
              <div className="col-span-2 flex items-center gap-3">
                <Button size="sm" onClick={runTest} loading={testing}>Test connection</Button>
                {test && (test.reachable ? (
                  <span className="flex items-center gap-1.5 text-xs text-success">
                    <CheckCircle2 className="h-3.5 w-3.5" /> Reachable · {test.latency_ms} ms · {test.models.length ? test.models.join(", ") : "no models listed"}
                  </span>
                ) : (
                  <span className="flex min-w-0 items-center gap-1.5 text-xs text-danger">
                    <XCircle className="h-3.5 w-3.5 shrink-0" /> <span className="truncate">{test.error}</span>
                  </span>
                ))}
              </div>
            </div>
          </section>

          <section className="border-t border-border pt-5">
            <h4 className="mb-2.5 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-fg-subtle">
              Document reading
              {health && (health.ocr_available ? <Badge tone="success">OCR installed</Badge> : <Badge tone="warning">OCR not installed</Badge>)}
            </h4>
            <div className="flex items-start justify-between gap-6 rounded-lg border border-border p-3.5">
              <div className="flex gap-3">
                <ScanText className="mt-0.5 h-4 w-4 text-fg-subtle" />
                <div>
                  <div className="text-[13px] font-semibold text-fg">OCR for scanned PDFs and images</div>
                  <div className="mt-0.5 text-xs leading-relaxed text-fg-muted">
                    Runs RapidOCR on the CPU, about 15–30 seconds per page. Without OCR, scanned pages are listed in the review pack as unread.
                  </div>
                </div>
              </div>
              <Switch checked={s.ocr_enabled} onChange={(v) => set("ocr_enabled", v)} label="OCR" />
            </div>
            <Field label="OCR page limit per file" className="mt-4 max-w-xs" hint="Pages beyond the limit are skipped and flagged. Raise it for the final run.">
              <Input type="number" min={1} max={500} value={s.ocr_page_limit} onChange={(e) => set("ocr_page_limit", Number(e.target.value))} disabled={!s.ocr_enabled} />
            </Field>
            <div className="mt-4 rounded-lg border border-border p-3.5">
              <div className="text-[13px] font-semibold text-fg">Reading pages with a vision model</div>
              <div className="mt-0.5 text-xs leading-relaxed text-fg-muted">
                When a vision model is set, each scanned page is sent to it for transcription, which is more accurate than
                RapidOCR on tables and stamps. Use a local OpenAI-compatible server (for example vLLM serving Qwen2.5-VL).
                Leave the address empty to use RapidOCR only, which runs fully offline.
              </div>
              <div className="mt-3 grid gap-3 sm:grid-cols-2">
                <Field label="Server address">
                  <Input value={s.ocr_model_url ?? ""} placeholder="http://127.0.0.1:8000/v1" onChange={(e) => set("ocr_model_url", e.target.value)} disabled={!s.ocr_enabled} />
                </Field>
                <Field label="Model name">
                  <Input value={s.ocr_model_name ?? ""} placeholder="qwen2.5-vl-7b-instruct" onChange={(e) => set("ocr_model_name", e.target.value)} disabled={!s.ocr_enabled} />
                </Field>
              </div>
            </div>
          </section>
        </div>
      )}
    </Dialog>
  );
}
