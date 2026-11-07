"use client";
import Link from "next/link";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { t } from "@/lib/i18n";
import type { Adherence, Dose, Eligible, Explain, Reminder } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Banner, Empty, PageHeader, Spinner, errMsg, useToast } from "@/components/ui";

export default function Reminders() {
  const { lang } = usePrefs();
  const toast = useToast();
  const [doses, setDoses] = useState<Dose[] | null>(null);
  const [eligible, setEligible] = useState<Eligible[] | null>(null);
  const [reminders, setReminders] = useState<Reminder[] | null>(null);
  const [adh, setAdh] = useState<Adherence | null>(null);
  const [perm, setPerm] = useState<string>("unsupported");

  const load = useCallback(async () => {
    try {
      const [d, e, r, a] = await Promise.all([api<{ doses: Dose[] }>("/reminders/today"), api<Eligible[]>("/reminders/eligible"), api<Reminder[]>("/reminders"), api<Adherence>("/reminders/adherence?days=7")]);
      setDoses(d.doses); setEligible(e); setReminders(r); setAdh(a);
    } catch (er) { toast(errMsg(er), "error"); }
  }, [toast]);
  useEffect(() => { void load(); if ("Notification" in window) setPerm(Notification.permission); }, [load]);

  async function mark(d: Dose, status: "taken" | "skipped") { try { await api(`/reminders/doses/${d.id}`, { body: { status } }); toast(`${d.medicine_name}: ${status === "taken" ? t("taken", lang) : t("skip", lang)}`); void load(); } catch (e) { toast(errMsg(e), "error"); } }
  async function askPerm() { setPerm(await Notification.requestPermission()); }
  async function toggle(r: Reminder) { try { await api(`/reminders/${r.id}`, { method: "PATCH", body: { active: !r.active } }); void load(); } catch (e) { toast(errMsg(e), "error"); } }
  async function del(r: Reminder) { if (!window.confirm(`Delete the reminder for ${r.medicine_name}?`)) return; try { await api(`/reminders/${r.id}`, { method: "DELETE" }); toast("Reminder deleted."); void load(); } catch (e) { toast(errMsg(e), "error"); } }

  return (
    <div className="space-y-8">
      <PageHeader title={t("reminders", lang)} intro="Reminders are made only from medicines you have confirmed. The instructions shown are copied from your confirmed prescription and cannot be changed here." />
      <Banner tone="info" title="How alerts work">Alerts appear on screen and are spoken aloud while Swasthya Mitra is open in your browser. Background notifications when the app is closed are not available yet.
        {perm === "default" && <button className="btn-quiet mt-3" onClick={askPerm}><Icon name="bell" /> Allow browser notifications</button>}
        {perm === "denied" && <p className="mt-2 font-bold">Browser notifications are blocked. You can allow them in your browser's site settings.</p>}</Banner>

      <section aria-labelledby="t-h"><h2 id="t-h" className="mb-3 text-xl font-bold">{t("todayMeds", lang)}</h2>
        {doses === null ? <Spinner /> : doses.length === 0 ? <Empty title="Nothing due today" /> : (
          <ol className="divide-y divide-line rounded-2xl border border-line bg-surface">{doses.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-4 p-4"><span className="w-24 text-3xl font-bold tabular-nums">{d.local_time}</span>
              <div className="min-w-[10rem] flex-1"><p className="text-lg font-bold">{d.medicine_name} {d.strength}</p><p className="text-muted">{d.dosage_instruction}</p></div>
              {d.status === "pending" || d.status === "missed" ? <div className="flex gap-2"><button className="btn-primary" onClick={() => mark(d, "taken")}>{t("taken", lang)}</button><button className="btn-quiet" onClick={() => mark(d, "skipped")}>{t("skip", lang)}</button></div> : <span className={`rounded-full px-4 py-1 font-bold ${d.status === "taken" ? "bg-ok-tint text-ok" : "bg-saffron-tint text-saffron-ink"}`}>{d.status}</span>}
              {d.status === "missed" && <span className="w-full font-bold text-sos">Missed. You can still mark it if you took it.</span>}
            </li>))}</ol>)}
      </section>

      <section aria-labelledby="new-h"><h2 id="new-h" className="mb-3 text-xl font-bold">Set up a reminder</h2>
        {eligible === null ? <Spinner /> : eligible.length === 0 ? (
          <Empty title="No confirmed medicines waiting" action={<Link href="/prescriptions" className="btn-primary">Go to prescriptions</Link>}>Scan a prescription and confirm the medicines first. Then they will appear here.</Empty>
        ) : <ul className="space-y-4">{eligible.map((e) => <CreateCard key={e.prescription_item_id} e={e} lang={lang} onCreated={load} />)}</ul>}
      </section>

      <section aria-labelledby="mine-h"><h2 id="mine-h" className="mb-3 text-xl font-bold">My reminders</h2>
        {reminders === null ? <Spinner /> : reminders.length === 0 ? <p className="text-muted">None yet.</p> : (
          <ul className="space-y-3">{reminders.map((r) => (
            <li key={r.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-surface p-4">
              <div className="min-w-[12rem] flex-1"><p className="font-bold">{r.medicine_name} {r.strength}</p><p className="text-muted">{r.dosage_instruction} · {r.times.join(", ")}{r.end_date ? ` · until ${r.end_date}` : ""}</p></div>
              <span className={`rounded-full px-3 py-1 text-sm font-bold ${r.active ? "bg-ok-tint text-ok" : "bg-line text-muted"}`}>{r.active ? "On" : "Paused"}</span>
              <button className="btn-quiet !min-h-[44px]" onClick={() => toggle(r)}>{r.active ? "Pause" : "Resume"}</button>
              <button className="btn-quiet !min-h-[44px] text-sos" onClick={() => del(r)}>Delete</button>
            </li>))}</ul>)}
      </section>

      {adh && adh.percent !== null && <section className="panel"><h2 className="text-xl font-bold">Last 7 days</h2><p className="mt-2 text-lg"><b className="text-brand">{adh.percent}%</b> taken · {adh.taken} taken, {adh.skipped} skipped, {adh.missed} missed</p></section>}
    </div>
  );
}

function CreateCard({ e, lang, onCreated }: { e: Eligible; lang: "en" | "hi" | "kn" | "te"; onCreated: () => void }) {
  const toast = useToast();
  const [times, setTimes] = useState<string[]>([]);
  const [ex, setEx] = useState<Explain | null>(null);
  const [end, setEnd] = useState("");
  useEffect(() => { api<Explain>(`/prescriptions/${e.prescription_id}/items/${e.prescription_item_id}/explain?lang=${lang}`).then((x) => { setEx(x); setTimes((cur) => (cur.length ? cur : x.suggested_times)); }).catch(() => {}); }, [e, lang]);
  async function create() {
    try { await api("/reminders", { body: { prescription_item_id: e.prescription_item_id, times, end_date: end || null } }); toast(`Reminder set for ${e.medicine_name}.`); onCreated(); } catch (er) { toast(errMsg(er), "error"); }
  }
  return (
    <li className="panel space-y-4">
      <div><p className="text-lg font-bold">{e.medicine_name} {e.strength}</p><p className="text-muted">Prescription says: {e.dosage_instruction}{e.duration_text ? ` · ${e.duration_text}` : ""}</p></div>
      {ex?.parsed && <ul className="list-disc pl-6">{ex.lines.map((l) => <li key={l}>{l}</li>)}</ul>}
      {ex?.as_needed ? <Banner tone="info">This medicine is “only when needed”, so no fixed times are suggested.</Banner> : times.length === 0 && <p className="text-muted">Choose the times you want to be reminded.</p>}
      <div>
        <p className="label">Reminder times (change them to suit your day)</p>
        <div className="flex flex-wrap items-center gap-3">
          {times.map((tm, i) => (<span key={i} className="flex items-center gap-1"><label className="sr-only" htmlFor={`tm${e.prescription_item_id}${i}`}>Time {i + 1}</label>
            <input id={`tm${e.prescription_item_id}${i}`} type="time" className="field !w-auto" value={tm} onChange={(ev) => setTimes(times.map((x, j) => (j === i ? ev.target.value : x)))} />
            <button className="btn-quiet !min-h-[48px] !px-3" aria-label={`Remove time ${tm}`} onClick={() => setTimes(times.filter((_, j) => j !== i))}>✕</button></span>))}
          {times.length < 6 && <button className="btn-quiet" onClick={() => setTimes([...times, "09:00"])}>+ Add time</button>}
        </div>
        <p className="mt-2 text-sm text-muted">These clock times are only suggestions from the written instruction. You choose them.</p>
      </div>
      <div className="max-w-xs"><label className="label" htmlFor={`end${e.prescription_item_id}`}>Last day (optional)</label><input id={`end${e.prescription_item_id}`} type="date" className="field" value={end} onChange={(ev) => setEnd(ev.target.value)} /></div>
      <button className="btn-primary" disabled={times.length === 0} onClick={create}><Icon name="bell" /> Start reminders</button>
    </li>
  );
}
