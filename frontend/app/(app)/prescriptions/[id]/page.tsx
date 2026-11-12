"use client";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { speak } from "@/lib/speech";
import { STATUS_INFO, confidenceTone, flagText, warningText } from "@/lib/rxText";
import type { Explain, Prescription, RxItem } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Banner, Field, PageHeader, Spinner, errMsg, useToast } from "@/components/ui";

type Draft = { medicine_name: string; strength: string; form: string; dosage_instruction: string; frequency_text: string; duration_text: string };
const toDraft = (i: RxItem): Draft => ({ medicine_name: i.medicine_name ?? "", strength: i.strength ?? "", form: i.form ?? "", dosage_instruction: i.dosage_instruction ?? "", frequency_text: i.frequency_text ?? "", duration_text: i.duration_text ?? "" });

export default function PrescriptionReview() {
  const { id } = useParams<{ id: string }>();
  const router = useRouter();
  const { lang } = usePrefs();
  const toast = useToast();
  const [rx, setRx] = useState<Prescription | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [include, setInclude] = useState<Record<string, boolean>>({});
  const [ack, setAck] = useState(false);
  const [adding, setAdding] = useState(false);
  const [warnings, setWarnings] = useState<string[]>([]);

  const load = useCallback(async () => {
    try {
      const p = await api<Prescription>(`/prescriptions/${id}`);
      setRx(p);
      setInclude((prev) => Object.fromEntries(p.items.map((i) => [i.id, prev[i.id] ?? Boolean(i.medicine_name && i.dosage_instruction && i.verification_status !== "unclear")])));
    } catch (e) { setError(errMsg(e)); }
  }, [id]);
  useEffect(() => { void load(); }, [load]);

  async function confirm() {
    if (!rx) return;
    try {
      const ids = rx.items.filter((i) => include[i.id]).map((i) => i.id);
      const r = await api<{ prescription: Prescription; allergy_warnings: string[] }>(`/prescriptions/${rx.id}/confirm`, { body: { item_ids: ids, acknowledged: ack } });
      setRx(r.prescription); setWarnings(r.allergy_warnings); toast("Prescription confirmed. You can now set reminders.");
    } catch (e) { toast(errMsg(e), "error"); }
  }
  async function remove() {
    if (!confirmWindow("Delete this prescription and any reminders made from it?")) return;
    try { await api(`/prescriptions/${id}`, { method: "DELETE" }); toast("Prescription deleted."); router.replace("/prescriptions"); } catch (e) { toast(errMsg(e), "error"); }
  }

  if (error) return <Banner tone="error" title="Could not open this prescription">{error} <Link className="underline" href="/prescriptions">Back to prescriptions</Link></Banner>;
  if (!rx) return <Spinner />;
  const editable = rx.status === "extracted" || rx.status === "failed";
  const chosen = rx.items.filter((i) => include[i.id]).length;

  return (
    <div className="space-y-6">
      <Link href="/prescriptions" className="font-bold text-brand underline">← All prescriptions</Link>
      <PageHeader title={rx.status === "confirmed" ? "Confirmed prescription" : "Check what I found"}
        intro={rx.status === "confirmed" ? "These details are locked so reminders cannot change by accident." : "I can make mistakes, especially with handwriting. Compare each line with your paper prescription, fix anything wrong, then confirm."} />

      {rx.warnings.length > 0 && <Banner tone="warn" title="Notes about this photo"><ul className="list-disc pl-5">{rx.warnings.map((w) => <li key={w}>{warningText(w)}</li>)}</ul></Banner>}
      {rx.message && <Banner tone="error" title="Nothing could be read">{rx.message}</Banner>}
      {(rx.doctor_name || rx.prescribed_date) && <p className="text-muted">{rx.doctor_name} {rx.prescribed_date && `· ${rx.prescribed_date}`}</p>}
      {rx.ai_warnings && rx.ai_warnings.length > 0 && <Banner tone="warn" title="The reader also noticed"><ul className="list-disc pl-5">{rx.ai_warnings.map((w) => <li key={w}>{w}</li>)}</ul></Banner>}
      <Legend />
      {(rx.patient || rx.prescriber || rx.diagnosis) && (
        <section className="panel" aria-labelledby="found-h">
          <h2 id="found-h" className="text-lg font-bold">Also written on the prescription</h2>
          <dl className="mt-2 grid gap-x-6 gap-y-1 sm:grid-cols-[auto_1fr]">
            {rx.patient && <><dt className="font-bold">Patient</dt><dd>{Object.values(rx.patient).join(" · ")}</dd></>}
            {rx.prescriber && <><dt className="font-bold">Prescribed by</dt><dd>{Object.values(rx.prescriber).join(" · ")}</dd></>}
            {rx.diagnosis && <><dt className="font-bold">Diagnosis</dt><dd>{rx.diagnosis}</dd></>}
          </dl>
          <p className="mt-2 text-sm text-muted">Copied as written. Please check it against your paper.</p>
        </section>)}
      {rx.full_transcription && <details className="panel"><summary className="cursor-pointer font-bold text-brand">Show everything I could read on the page</summary><p className="mt-3 whitespace-pre-line">{rx.full_transcription}</p></details>}
      {rx.has_image && <details><summary className="cursor-pointer font-bold text-brand">Show my photo</summary>{/* eslint-disable-next-line @next/next/no-img-element */}<img src={`/api/prescriptions/${rx.id}/image`} alt="Your prescription photo" className="mt-3 max-h-96 rounded-xl border border-line" /></details>}
      {warnings.map((w) => <Banner key={w} tone="error" title="Allergy check">{w}</Banner>)}

      <ul className="space-y-4">
        {rx.items.map((it) => <ItemCard key={it.id} rxId={rx.id} item={it} editable={editable} lang={lang} included={!!include[it.id]} onInclude={(v) => setInclude((s) => ({ ...s, [it.id]: v }))} onChanged={load} />)}
      </ul>

      {editable && (adding ? <AddForm rxId={rx.id} onDone={() => { setAdding(false); void load(); }} /> : <button className="btn-quiet" onClick={() => setAdding(true)}>+ Add a medicine by hand</button>)}

      {editable && rx.items.length > 0 && (
        <section className="panel space-y-4 border-2 border-brand">
          <h2 className="text-xl font-bold">Confirm</h2>
          <p>{chosen} medicine{chosen === 1 ? "" : "s"} selected. Only confirmed medicines can be used for reminders.</p>
          <label className="flex cursor-pointer items-start gap-3"><input type="checkbox" className="mt-1 h-7 w-7 shrink-0 accent-[var(--brand)]" checked={ack} onChange={(e) => setAck(e.target.checked)} />
            <span className="font-bold">I have checked these details against my paper prescription.</span></label>
          <button className="btn-primary w-full sm:w-auto" disabled={!ack || chosen === 0} onClick={confirm}><Icon name="check" /> Confirm {chosen} medicine{chosen === 1 ? "" : "s"}</button>
        </section>)}

      {rx.status === "confirmed" && <Link href="/reminders" className="btn-primary"><Icon name="bell" /> Set reminder times</Link>}
      <div className="pt-4"><button className="font-bold text-sos underline" onClick={remove}>Delete this prescription</button></div>
    </div>
  );
}
const confirmWindow = (m: string) => typeof window !== "undefined" && window.confirm(m);

function ItemCard({ rxId, item, editable, lang, included, onInclude, onChanged }: { rxId: string; item: RxItem; editable: boolean; lang: "en" | "hi" | "kn" | "te"; included: boolean; onInclude: (v: boolean) => void; onChanged: () => void }) {
  const toast = useToast();
  const [d, setD] = useState<Draft>(toDraft(item));
  const [dirty, setDirty] = useState(false);
  const [ex, setEx] = useState<Explain | null>(null);
  const set = (k: keyof Draft, v: string) => { setD((s) => ({ ...s, [k]: v })); setDirty(true); };
  useEffect(() => { setD(toDraft(item)); setDirty(false); }, [item]);

  async function save() {
    try { await api(`/prescriptions/${rxId}/items/${item.id}`, { method: "PUT", body: d }); toast("Saved."); setDirty(false); onChanged(); } catch (e) { toast(errMsg(e), "error"); }
  }
  async function del() { try { await api(`/prescriptions/${rxId}/items/${item.id}`, { method: "DELETE" }); onChanged(); } catch (e) { toast(errMsg(e), "error"); } }
  async function explain() { try { const e = await api<Explain>(`/prescriptions/${rxId}/items/${item.id}/explain?lang=${lang}`); setEx(e); if (e.parsed) speak(`${item.medicine_name}. ${e.lines.join(". ")}`, lang); } catch (e) { toast(errMsg(e), "error"); } }

  const p = `${item.id}`;
  return (
    <li className={`rounded-2xl border-2 bg-surface p-5 ${included ? "border-brand" : "border-line"}`}>
      <div className="flex flex-wrap items-center gap-3">
        {editable && <label className="flex items-center gap-2 font-bold"><input type="checkbox" className="h-7 w-7 accent-[var(--brand)]" checked={included} onChange={(e) => onInclude(e.target.checked)} /> Include</label>}
        <StatusBadge status={item.verification_status ?? "check"} />
        <span className={`rounded-full px-3 py-1 text-sm font-bold ${confidenceTone(item.confidence_label)}`}>{item.edited_by_user ? "Checked by you" : `Reader’s confidence ${Math.round(item.confidence * 100)}%`}</span>
        {item.user_confirmed && <span className="rounded-full bg-ok-tint px-3 py-1 text-sm font-bold text-ok">Confirmed</span>}
      </div>
      {!item.edited_by_user && <p className="mt-2 text-sm text-muted">{STATUS_INFO[item.verification_status ?? "check"].help} The reader’s confidence is not proof that it is right.</p>}
      {item.raw_text && <p className="mt-3 rounded-xl bg-brand-tint p-3"><span className="font-bold">As written: </span>“{item.raw_text}”</p>}
      {item.uncertainty_note && <p className="mt-2 font-bold text-saffron-ink">Not sure about: {item.uncertainty_note}</p>}
      {item.additional_instructions && <p className="mt-2"><span className="font-bold">Also written: </span>{item.additional_instructions}</p>}
      {!item.edited_by_user && item.flags.filter((f) => !(f === "model_uncertainty_note" && item.uncertainty_note)).length > 0 && <ul className="mt-3 list-disc space-y-0.5 pl-6 text-saffron-ink">{item.flags.filter((f) => !(f === "model_uncertainty_note" && item.uncertainty_note)).map((f) => <li key={f}>{flagText(f)}</li>)}</ul>}
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <Field label="Medicine name" htmlFor={`n${p}`}><input id={`n${p}`} className="field" value={d.medicine_name} disabled={!editable} onChange={(e) => set("medicine_name", e.target.value)} /></Field>
        <Field label="Strength" htmlFor={`s${p}`}><input id={`s${p}`} className="field" value={d.strength} disabled={!editable} placeholder="e.g. 500mg" onChange={(e) => set("strength", e.target.value)} /></Field>
        <Field label="Instructions, exactly as written" htmlFor={`i${p}`} hint="For example: 1-0-1 after food"><input id={`i${p}`} className="field" value={d.dosage_instruction} disabled={!editable} onChange={(e) => set("dosage_instruction", e.target.value)} /></Field>
        <Field label="How long" htmlFor={`d${p}`}><input id={`d${p}`} className="field" value={d.duration_text} disabled={!editable} placeholder="e.g. 30 days" onChange={(e) => set("duration_text", e.target.value)} /></Field>
      </div>
      <div className="mt-4 flex flex-wrap gap-3">
        {item.dosage_instruction && <button className="btn-quiet" onClick={explain}><Icon name="speaker" className="h-5 w-5" /> Explain in simple words</button>}
        {editable && dirty && <button className="btn-primary" onClick={save}>Save changes</button>}
        {editable && <button className="btn-quiet text-sos" onClick={del}>Remove</button>}
      </div>
      {ex && (<div className="mt-4 rounded-xl bg-brand-tint p-4">{ex.parsed ? <><p className="font-bold">You wrote: “{ex.original}”</p><ul className="mt-1 list-disc pl-6">{ex.lines.map((l) => <li key={l}>{l}</li>)}</ul></> : <p>I could not turn “{ex.original}” into simple words. Please ask your doctor or pharmacist.</p>}
        <p className="mt-2 text-sm text-muted">This only restates what is written. It does not decide your dose.</p></div>)}
    </li>
  );
}

function StatusBadge({ status }: { status: "clear" | "check" | "unclear" }) {
  const i = STATUS_INFO[status];
  return <span className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1 text-sm font-bold ${i.cls}`}><Icon name={i.icon} className="h-4 w-4" /> {i.label}</span>;
}

function Legend() {
  return (
    <details className="panel">
      <summary className="cursor-pointer font-bold text-brand">What do Clear, Check and Unclear mean?</summary>
      <ul className="mt-3 space-y-2">
        {(["clear", "check", "unclear"] as const).map((k) => <li key={k} className="flex flex-wrap items-center gap-3"><StatusBadge status={k} /><span>{STATUS_INFO[k].help}</span></li>)}
      </ul>
      <p className="mt-3 text-sm text-muted">Nothing is used for reminders until you check every medicine and confirm.</p>
    </details>
  );
}

function AddForm({ rxId, onDone }: { rxId: string; onDone: () => void }) {
  const toast = useToast();
  const [d, setD] = useState({ medicine_name: "", strength: "", dosage_instruction: "", duration_text: "" });
  async function add(e: React.FormEvent) { e.preventDefault(); try { await api(`/prescriptions/${rxId}/items`, { body: d }); toast("Medicine added."); onDone(); } catch (er) { toast(errMsg(er), "error"); } }
  return (
    <form onSubmit={add} className="panel space-y-4">
      <h2 className="text-xl font-bold">Add a medicine</h2>
      <p className="text-muted">Type it exactly as written on your prescription.</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <Field label="Medicine name" htmlFor="an"><input id="an" required minLength={2} className="field" value={d.medicine_name} onChange={(e) => setD({ ...d, medicine_name: e.target.value })} /></Field>
        <Field label="Strength" htmlFor="as"><input id="as" className="field" value={d.strength} onChange={(e) => setD({ ...d, strength: e.target.value })} /></Field>
        <Field label="Instructions" htmlFor="ai"><input id="ai" required className="field" value={d.dosage_instruction} onChange={(e) => setD({ ...d, dosage_instruction: e.target.value })} /></Field>
        <Field label="How long" htmlFor="ad"><input id="ad" className="field" value={d.duration_text} onChange={(e) => setD({ ...d, duration_text: e.target.value })} /></Field>
      </div>
      <div className="flex gap-3"><button className="btn-primary">Add medicine</button><button type="button" className="btn-quiet" onClick={onDone}>Cancel</button></div>
    </form>
  );
}
