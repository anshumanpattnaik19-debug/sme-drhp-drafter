import type { ReactNode } from "react";

/** Minimal Markdown for assistant answers: headings, lists, quotes, bold/italic/code, [n] citations and [●]. */
export function Markdown({ text, onCite, citeTitle }: { text: string; onCite?: (n: number) => void; citeTitle?: (n: number) => string | undefined }) {
  const inline = (s: string, key: string): ReactNode[] =>
    // italics only at word boundaries, so file names like 04_Audited_FS.pdf stay as written
    s.split(/(\*\*[^*]+\*\*|(?<![A-Za-z0-9])_[^_\s][^_]*_(?![A-Za-z0-9])|(?<![A-Za-z0-9*])\*[^*\s][^*]*\*(?![A-Za-z0-9*])|`[^`]+`|\[\d+\]|\[●\])/g).map((tok, i) => {
      const k = `${key}-${i}`;
      if (!tok) return null;
      if (tok.startsWith("**") && tok.endsWith("**")) return <strong key={k} className="font-semibold text-fg">{inline(tok.slice(2, -2), k)}</strong>;
      if ((tok.startsWith("_") && tok.endsWith("_")) || (tok.startsWith("*") && tok.endsWith("*") && tok.length > 2)) return <em key={k}>{tok.slice(1, -1)}</em>;
      if (tok.startsWith("`")) return <code key={k} className="rounded bg-muted px-1 py-0.5 font-mono text-[0.85em]">{tok.slice(1, -1)}</code>;
      if (tok === "[●]") return <span key={k} className="placeholder-chip">[●]</span>;
      const m = tok.match(/^\[(\d+)\]$/);
      if (m) {
        const n = Number(m[1]);
        return (
          <button
            key={k}
            onClick={() => onCite?.(n)}
            title={citeTitle?.(n)}
            className="mx-0.5 inline-flex h-[18px] min-w-[18px] -translate-y-[1px] items-center justify-center rounded-md bg-primary-soft px-1 align-middle font-sans text-[10.5px] font-semibold text-primary transition-colors hover:bg-primary hover:text-primary-fg"
          >
            {n}
          </button>
        );
      }
      return tok;
    });

  const out: ReactNode[] = [];
  const lines = text.split("\n");
  let i = 0;
  while (i < lines.length) {
    const ln = lines[i];
    if (!ln.trim()) { i++; continue; }
    if (/^#{1,4}\s/.test(ln)) {
      out.push(<h4 key={i} className="mb-1 mt-4 font-sans text-[14px] font-semibold text-fg first:mt-0">{inline(ln.replace(/^#+\s/, ""), `h${i}`)}</h4>);
      i++;
      continue;
    }
    if (/^>\s?/.test(ln)) {
      const q: string[] = [];
      while (i < lines.length && /^>\s?/.test(lines[i])) q.push(lines[i++].replace(/^>\s?/, ""));
      out.push(
        <blockquote key={`q${i}`} className="my-2 border-l-2 border-primary/40 bg-subtle/60 py-1.5 pl-3 pr-2 text-[14px] text-fg-muted">
          {q.map((x, j) => <p key={j} className="my-0.5">{inline(x, `q${i}-${j}`)}</p>)}
        </blockquote>,
      );
      continue;
    }
    if (/^\s*[-*]\s/.test(ln)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*[-*]\s/.test(lines[i])) items.push(lines[i++].replace(/^\s*[-*]\s/, ""));
      out.push(<ul key={`u${i}`} className="my-2 list-disc space-y-1 pl-5 marker:text-fg-subtle">{items.map((x, j) => <li key={j}>{inline(x, `u${i}-${j}`)}</li>)}</ul>);
      continue;
    }
    if (/^\s*\d+\.\s/.test(ln)) {
      const items: string[] = [];
      while (i < lines.length && /^\s*\d+\.\s/.test(lines[i])) items.push(lines[i++].replace(/^\s*\d+\.\s/, ""));
      out.push(<ol key={`o${i}`} className="my-2 list-decimal space-y-1 pl-5 marker:text-fg-subtle">{items.map((x, j) => <li key={j}>{inline(x, `o${i}-${j}`)}</li>)}</ol>);
      continue;
    }
    const para: string[] = [];
    while (i < lines.length && lines[i].trim() && !/^(#{1,4}\s|>|\s*[-*]\s|\s*\d+\.\s)/.test(lines[i])) para.push(lines[i++]);
    out.push(<p key={`p${i}`} className="my-2 first:mt-0">{inline(para.join(" "), `p${i}`)}</p>);
  }
  return <>{out}</>;
}
