import { useEffect, useMemo, useState } from "react";
import { Info, Lock, Save, Sparkles, Undo2 } from "lucide-react";
import { api } from "../lib/api";
import { useProject } from "../lib/state";
import type { Fact, Offer } from "../lib/types";
import { cn, factDisplay } from "../lib/utils";
import { Page } from "../components/ProjectShell";
import { Badge, Button, Card, CardHeader, Field, Input, PageHeader, Segmented, Textarea, Tooltip, useToast } from "../components/ui";

type FieldDef = { key: keyof Offer & string; label: string; hint?: string; find?: string[]; types?: string[]; wide?: boolean; multiline?: boolean; placeholder?: string };

const GROUPS: { title: string; description: string; fields: FieldDef[] }[] = [
  {
    title: "Issuer",
    description: "Appears on the cover page, in General Information and in Definitions.",
    fields: [
      { key: "company_name", label: "Company name", find: ["name of the company", "company name", "name of company"], wide: true },
      { key: "registered_office", label: "Registered office", find: ["registered office"], wide: true, multiline: true },
      { key: "company_secretary", label: "Company Secretary and Compliance Officer", find: ["company secretary"] },
      { key: "statutory_auditor", label: "Statutory and peer review auditor", find: ["statutory auditor", "peer review", "auditor"] },
    ],
  },
  {
    title: "The offer",
    description: "Share counts only. Price, price band, issue size in ₹ and offer dates stay [●] at DRHP stage.",
    fields: [
      { key: "fresh_issue_shares", label: "Fresh issue (equity shares)", find: ["fresh issue"], types: ["count", "amount", "short_text"], placeholder: "e.g. 35,00,000" },
      { key: "ofs_shares", label: "Offer for sale (equity shares)", find: ["offer for sale", "ofs"], types: ["count", "amount", "short_text"], placeholder: "0 if none" },
      { key: "face_value", label: "Face value per share (₹)", find: ["face value"], placeholder: "e.g. 10" },
      { key: "pre_issue_shares", label: "Equity shares before the offer", find: ["pre-issue", "pre issue", "pre-offer", "existing equity", "paid-up"], types: ["count", "amount"] },
      { key: "post_issue_shares", label: "Equity shares after the offer", find: ["post-issue", "post issue", "post-offer"], types: ["count", "amount"] },
      { key: "selling_shareholder", label: "Selling shareholder(s)", find: ["selling shareholder"], wide: true },
    ],
  },
  {
    title: "Intermediaries",
    description: "Appointed by the Board. Used in General Information, the cover page and Material Contracts.",
    fields: [
      { key: "lead_manager", label: "Book Running Lead Manager", find: ["lead manager", "brlm"] },
      { key: "registrar", label: "Registrar to the offer", find: ["registrar to the", "rta"] },
      { key: "market_maker", label: "Market maker", find: ["market maker"] },
      { key: "legal_counsel", label: "Legal counsel to the offer", find: ["legal counsel", "legal advisor"] },
    ],
  },
  {
    title: "Authority for the offer",
    description: "Dates of the approving resolutions (Other Regulatory and Statutory Disclosures).",
    fields: [
      { key: "board_resolution_date", label: "Board resolution approving the offer", find: ["board"], types: ["date"], placeholder: "e.g. 28 August 2026" },
      { key: "shareholder_resolution_date", label: "Shareholders' special resolution", find: ["egm", "general meeting", "special resolution", "shareholders"], types: ["date"], placeholder: "e.g. 25 September 2026" },
    ],
  },
];

function suggestions(facts: Fact[], def: FieldDef, current: string | undefined) {
  if (!def.find) return [];
  const seen = new Set<string>();
  const out: Fact[] = [];
  const pref = (f: Fact) => (f.doc_type === "offer_note" ? 0 : f.doc_type === "board_resolution" || f.doc_type === "people_profiles" ? 1 : 2);
  const hits = facts
    .filter((f) => def.find!.some((k) => f.label.toLowerCase().includes(k)) && (!def.types || def.types.includes(f.type)) && f.value.length < 160)
    .sort((a, b) => pref(a) - pref(b));
  for (const f of hits) {
    const v = factDisplay(f).replace(/^₹ /, "");
    if (seen.has(v) || v === current) continue;
    seen.add(v);
    out.push(f);
    if (out.length >= 3) break;
  }
  return out;
}

export default function OfferPage() {
  const { project, refresh, version } = useProject();
  const toast = useToast();
  const [form, setForm] = useState<Offer>({});
  const [facts, setFacts] = useState<Fact[]>([]);
  const [saving, setSaving] = useState(false);
  const [platformNote, setPlatformNote] = useState<{ title: string; detail: string; suggest: string } | null>(null);
  const pid = project?.id ?? "";

  useEffect(() => { if (project) setForm(project.offer || {}); }, [project?.id]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (pid) api.facts(pid).then(setFacts).catch(() => {}); }, [pid, version]);
  // the files may name a different listing platform from the one chosen when the project was created
  useEffect(() => {
    if (!pid) return;
    api.review(pid)
      .then((r) => {
        const i = (r.issues as unknown as { field?: string; title: string; detail: string; suggest: string }[]).find((x) => x.field === "platform");
        setPlatformNote(i ? { title: i.title, detail: i.detail, suggest: i.suggest } : null);
      })
      .catch(() => {});
  }, [pid, version, project?.offer?.board]);

  const dirty = useMemo(() => JSON.stringify(form) !== JSON.stringify(project?.offer || {}), [form, project?.offer]);
  const set = (k: string, v: string) => setForm((f) => ({ ...f, [k]: v }));
  const filled = GROUPS.flatMap((g) => g.fields).filter((f) => (form[f.key] || "").trim()).length;
  const total = GROUPS.flatMap((g) => g.fields).length;

  const save = async () => {
    setSaving(true);
    try {
      await api.patchProject(pid, { offer: form, name: form.company_name || undefined });
      await refresh();
      toast("success", "Offer details saved", "Redraft affected sections to pick up the changes.");
    } catch (e) {
      toast("error", "Could not save", (e as Error).message);
    } finally {
      setSaving(false);
    }
  };

  const fillAll = async () => {
    // the service reads the issuer's schedules (note on the proposed issue, intermediaries, KMP list) and fills empty fields
    try {
      const res = await api.autofill(pid);
      await refresh();
      setForm(res.offer);
      const n = Object.keys(res.filled).length;
      toast(n ? "success" : "info", n ? `Filled ${n} empty field(s) from the documents` : "Nothing new found in the documents for the empty fields",
            n ? "Each value shows the file it came from. Check them before drafting." : undefined);
    } catch (e) {
      toast("error", "Could not read the documents", (e as Error).message);
    }
  };
  const sources = project?.offer_sources || {};

  return (
    <Page className="pb-28">
      <PageHeader
        eyebrow="Step 2 · Inputs"
        title="Offer details"
        description="Board-approved terms and parties that the issuer files may not state in one place. Values here take precedence over extracted facts."
        actions={
          <>
            <Badge tone={filled === total ? "success" : "neutral"}>{filled} of {total} filled</Badge>
            <Button icon={<Sparkles className="h-4 w-4" />} onClick={fillAll} disabled={!project?.stats.processed}>Fill empty fields from documents</Button>
          </>
        }
      />

      {platformNote && (
        <div role="alert" className="mb-5 flex flex-wrap items-start justify-between gap-3 rounded-lg border border-warning/40 bg-warning-soft/70 px-4 py-3 text-[13px] text-fg">
          <div className="min-w-0">
            <div className="font-medium">{platformNote.title}</div>
            <div className="text-fg-muted">{platformNote.detail}</div>
          </div>
          <Button size="sm" onClick={() => set("board", platformNote.suggest)}>Switch platform</Button>
        </div>
      )}

      <div className="mb-5 flex items-start gap-3 rounded-lg border border-info/25 bg-info-soft/60 px-4 py-3 text-[13px] text-fg">
        <Lock className="mt-0.5 h-4 w-4 shrink-0 text-info" />
        <div>
          <span className="font-medium">DRHP-stage fields are locked to [●].</span>{" "}
          <span className="text-fg-muted">Offer price, price band, issue size in rupees, lot size, and bid/offer dates are not entered at this stage. The verifier flags any that appear in a draft.</span>
        </div>
      </div>

      <div className="space-y-5">
        <Card>
          <CardHeader title="Platform" description="SME platform the offer will be listed on (SEBI ICDR Regulations, Chapter IX)." />
          <div className="flex flex-wrap items-center gap-6 px-5 py-4">
            <Segmented
              value={(form.board as "bse_sme" | "nse_emerge") || "bse_sme"}
              onChange={(v) => set("board", v)}
              options={[{ value: "bse_sme", label: "BSE SME" }, { value: "nse_emerge", label: "NSE Emerge" }]}
            />
            <Segmented
              value={(form.issue_type as "fresh" | "ofs" | "fresh_ofs") || "fresh"}
              onChange={(v) => set("issue_type", v)}
              options={[{ value: "fresh", label: "Fresh issue" }, { value: "fresh_ofs", label: "Fresh issue + OFS" }, { value: "ofs", label: "Offer for sale" }]}
            />
          </div>
        </Card>

        {GROUPS.map((g) => (
          <Card key={g.title}>
            <CardHeader title={g.title} description={g.description} />
            <div className="grid grid-cols-1 gap-x-6 gap-y-5 px-5 py-5 md:grid-cols-2">
              {g.fields.map((def) => {
                const sug = suggestions(facts, def, form[def.key]);
                const changed = (form[def.key] || "") !== ((project?.offer || {})[def.key] || "");
                return (
                  <Field
                    key={def.key}
                    label={def.label}
                    className={cn(def.wide && "md:col-span-2")}
                    aside={changed ? <Badge tone="primary">Edited</Badge> : sources[def.key] && form[def.key] === (project?.offer || {})[def.key] ? (
                      <Tooltip content={`${sources[def.key]!.loc}${sources[def.key]!.snippet ? ` · ${sources[def.key]!.snippet!.slice(0, 120)}` : ""}`}>
                        <Badge tone="success">From {sources[def.key]!.file_name}</Badge>
                      </Tooltip>
                    ) : null}
                    hint={
                      sug.length > 0 && (
                        <span className="mt-1.5 flex flex-wrap items-center gap-1.5">
                          <span className="text-fg-subtle">From documents:</span>
                          {sug.map((s) => (
                            <Tooltip key={s.id} content={`${s.label} · ${s.file_name} · ${s.loc}`}>
                              <button
                                type="button"
                                onClick={(e) => { e.preventDefault(); set(def.key, factDisplay(s).replace(/^₹ /, "")); }}
                                className="max-w-[280px] truncate rounded-md border border-border bg-subtle px-2 py-0.5 text-2xs font-medium text-fg-muted transition-colors hover:border-primary hover:text-primary"
                              >
                                {factDisplay(s)}
                              </button>
                            </Tooltip>
                          ))}
                        </span>
                      )
                    }
                  >
                    {def.multiline ? (
                      <Textarea rows={2} value={form[def.key] || ""} placeholder={def.placeholder ?? "[●]"} onChange={(e) => set(def.key, e.target.value)} />
                    ) : (
                      <Input value={form[def.key] || ""} placeholder={def.placeholder ?? "[●]"} onChange={(e) => set(def.key, e.target.value)} />
                    )}
                  </Field>
                );
              })}
            </div>
          </Card>
        ))}
      </div>

      <div className={cn("fixed bottom-0 left-60 right-0 z-20 border-t border-border bg-surface/95 backdrop-blur transition-transform", dirty ? "translate-y-0" : "translate-y-full")}>
        <div className="mx-auto flex max-w-[1240px] items-center justify-between px-8 py-3 pr-44">
          <span className="flex items-center gap-2 text-[13px] text-fg-muted"><Info className="h-4 w-4" /> You have unsaved changes.</span>
          <div className="flex gap-2">
            <Button variant="ghost" icon={<Undo2 className="h-4 w-4" />} onClick={() => setForm(project?.offer || {})}>Discard</Button>
            <Button variant="primary" icon={<Save className="h-4 w-4" />} onClick={save} loading={saving}>Save offer details</Button>
          </div>
        </div>
      </div>
    </Page>
  );
}
