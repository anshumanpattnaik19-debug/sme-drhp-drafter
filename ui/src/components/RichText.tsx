import type { ReactNode } from "react";
import type { Fact } from "../lib/types";

const esc = (s: string) => s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");

/** Renders **bold**, [●] placeholders, and underlines the values of cited facts. */
export function RichText({ text, facts = [], onFact }: { text: string; facts?: Fact[]; onFact?: (f: Fact) => void }) {
  const values = facts
    .map((f) => ({ f, v: f.value.trim() }))
    .filter((x) => x.v.length >= 2 && x.v.length < 120)
    .sort((a, b) => b.v.length - a.v.length);
  const byVal = new Map(values.map((x) => [x.v, x.f]));
  const factRx = values.length ? new RegExp(`(${values.map((x) => esc(x.v)).join("|")})`, "g") : null;

  const renderPlain = (s: string, key: string): ReactNode[] => {
    if (!factRx) return [s];
    return s.split(factRx).map((part, i) => {
      const f = byVal.get(part);
      if (!f) return part;
      return (
        <span
          key={`${key}-${i}`}
          onClick={(e) => { e.stopPropagation(); onFact?.(f); }}
          className="cursor-pointer rounded-sm underline decoration-primary/50 decoration-dotted decoration-2 underline-offset-[3px] hover:bg-primary-soft hover:decoration-primary"
          title={`${f.label} · ${f.file_name} · ${f.loc}`}
        >
          {part}
        </span>
      );
    });
  };

  const out: ReactNode[] = [];
  text.split(/(\*\*[^*]+\*\*|\[●\])/g).forEach((tok, i) => {
    if (!tok) return;
    if (tok === "[●]") out.push(<span key={i} className="placeholder-chip">[●]</span>);
    else if (tok.startsWith("**") && tok.endsWith("**")) out.push(<strong key={i} className="font-semibold">{renderPlain(tok.slice(2, -2), `b${i}`)}</strong>);
    else out.push(...renderPlain(tok, `t${i}`));
  });
  return <>{out}</>;
}
