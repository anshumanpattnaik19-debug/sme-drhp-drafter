import type { Writer } from "../lib/types";
import { Badge, type Tone } from "./ui";

export const WRITER_META: Record<Writer, { label: string; short: string; tone: Tone; help: string }> = {
  slm_core: { label: "SLM · core", short: "SLM", tone: "primary", help: "Drafted by the fine-tuned model from routed facts; evaluated section." },
  slm_ext: { label: "SLM · extended", short: "SLM+", tone: "info", help: "Drafted by the fine-tuned model; reported qualitatively." },
  template: { label: "Template", short: "TPL", tone: "neutral", help: "Precedent boilerplate with fields filled from offer details and facts." },
  code: { label: "Code tables", short: "CODE", tone: "success", help: "Tables built by code from parsed figures." },
  inserted: { label: "Inserted", short: "INS", tone: "outline", help: "Issuer document inserted as provided." },
};

export function WriterBadge({ writer, short }: { writer: Writer; short?: boolean }) {
  const m = WRITER_META[writer];
  return <Badge tone={m.tone}>{short ? m.short : m.label}</Badge>;
}

export function EngineBadge({ engine, model }: { engine: string | null | undefined; model?: string | null }) {
  if (!engine) return null;
  if (engine === "mock") return <Badge tone="warning">Mock writer</Badge>;
  if (engine === "brief") return <Badge tone="warning">Prose pending · briefs</Badge>;
  if (engine === "rules") return <Badge tone="info">From red flags</Badge>;
  if (engine === "model") return <Badge tone="success">{model || "Fine-tuned SLM"}</Badge>;
  if (engine === "user") return <Badge tone="primary">Edited by you</Badge>;
  return null;
}

export function SignOffBadge({ review }: { review?: { status: string; by?: string; at?: string } }) {
  if (review?.status === "reviewed")
    return <Badge tone="success">Signed off{review.by ? ` · ${review.by}` : ""}</Badge>;
  return <Badge tone="outline">Not signed off</Badge>;
}
