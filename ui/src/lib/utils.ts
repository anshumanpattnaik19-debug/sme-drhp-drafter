import { clsx, type ClassValue } from "clsx";

export const cn = (...c: ClassValue[]) => clsx(c);

export function bytes(n: number) {
  if (n < 1024) return `${n} B`;
  if (n < 1024 ** 2) return `${(n / 1024).toFixed(0)} KB`;
  return `${(n / 1024 ** 2).toFixed(1)} MB`;
}

export function num(n: number | null | undefined) {
  if (n === null || n === undefined) return "–";
  return n.toLocaleString("en-IN");
}

export function pct(x: number | null | undefined, dp = 0) {
  if (x === null || x === undefined) return "–";
  return `${(x * 100).toFixed(dp)}%`;
}

export function ago(iso: string | null | undefined) {
  if (!iso) return "–";
  const d = new Date(iso);
  const s = (Date.now() - d.getTime()) / 1000;
  if (s < 45) return "just now";
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  if (s < 86400 * 7) return `${Math.round(s / 86400)} d ago`;
  return d.toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" });
}

export const BOARD_LABEL: Record<string, string> = { bse_sme: "BSE SME", nse_emerge: "NSE Emerge" };

export const FORMAT_LABEL: Record<string, string> = {
  pdf: "Digital PDF",
  pdf_scanned: "Scanned PDF",
  pdf_mixed: "Mixed PDF",
  docx: "Word",
  xlsx: "Excel",
  image: "Image",
  text: "Text",
};

export const FACT_TYPE_LABEL: Record<string, string> = {
  amount: "Amount",
  percent: "Percent",
  date: "Date",
  count: "Count",
  person: "Person",
  entity: "Entity",
  place: "Place",
  identifier: "Identifier",
  short_text: "Text",
};

export function factDisplay(f: { value: string; unit: string; type: string }) {
  const u = f.unit || "";
  if (u.startsWith("₹")) return u === "₹" ? `₹ ${f.value}` : `₹ ${f.value} ${u.slice(2)}`;
  if (u === "%") return `${f.value}%`;
  if (f.type === "identifier") return f.value;
  return u ? `${f.value} ${u}` : f.value;
}

export function download(url: string) {
  const a = document.createElement("a");
  a.href = url;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
}
