"use client";
import { useCallback, useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { HealthRecord, TimelineEvent } from "@/lib/types";
import { Empty, Field, PageHeader, Spinner, errMsg, useToast } from "@/components/ui";

const TYPES: [string, string][] = [["visit", "Doctor visit"], ["lab_report", "Lab report"], ["vaccination", "Vaccination"], ["vitals", "Vitals (BP, sugar…)"], ["condition", "Condition"], ["note", "Note"]];
const label = (t: string) => TYPES.find(([k]) => k === t)?.[1] ?? t;
const today = () => new Date().toISOString().slice(0, 10);
const KIND_DOT: Record<string, string> = { emergency: "bg-sos", prescription: "bg-saffron", record: "bg-brand", profile: "bg-brand" };

export default function Records() {
  const toast = useToast();
  const [tab, setTab] = useState<"list" | "timeline">("list");
  const [records, setRecords] = useState<HealthRecord[] | null>(null);
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [form, setForm] = useState({ record_type: "visit", title: "", record_date: today(), details: "" });
  const [err, setErr] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);

  const load = useCallback(() => {
    api<HealthRecord[]>("/records").then(setRecords).catch((e) => toast(errMsg(e), "error"));
    api<TimelineEvent[]>("/timeline?limit=100").then(setEvents).catch(() => setEvents([]));
  }, [toast]);
  useEffect(() => { load(); }, [load]);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setErr(null);
    try {
      const body = { ...form, details: form.details || null };
      if (editing) await api(`/records/${editing}`, { method: "PUT", body }); else await api("/records", { body });
      toast(editing ? "Record updated." : "Record added."); setEditing(null); setForm({ record_type: "visit", title: "", record_date: today(), details: "" }); load();
    } catch (er) { setErr(errMsg(er)); }
  }
  async function del(r: HealthRecord) { if (!window.confirm(`Delete “${r.title}”?`)) return; try { await api(`/records/${r.id}`, { method: "DELETE" }); toast("Record deleted."); load(); } catch (e) { toast(errMsg(e), "error"); } }

  return (
    <div className="space-y-8">
      <PageHeader title="Health records" intro="Keep visits, reports and readings in one place. Records are stored encrypted and only you can see them." />
      <form onSubmit={submit} className="panel space-y-4">
        <h2 className="text-xl font-bold">{editing ? "Edit record" : "Add a record"}</h2>
        {err && <p role="alert" className="font-bold text-sos">{err}</p>}
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Type" htmlFor="rt"><select id="rt" className="field" value={form.record_type} onChange={(e) => setForm({ ...form, record_type: e.target.value })}>{TYPES.map(([k, v]) => <option key={k} value={k}>{v}</option>)}</select></Field>
          <Field label="Title" htmlFor="ti"><input id="ti" required className="field" maxLength={200} value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></Field>
          <Field label="Date" htmlFor="rd"><input id="rd" type="date" required max={today()} className="field" value={form.record_date} onChange={(e) => setForm({ ...form, record_date: e.target.value })} /></Field>
        </div>
        <Field label="Details" htmlFor="de"><textarea id="de" rows={3} className="field" maxLength={5000} value={form.details} onChange={(e) => setForm({ ...form, details: e.target.value })} /></Field>
        <div className="flex gap-3"><button className="btn-primary">{editing ? "Save changes" : "Add record"}</button>{editing && <button type="button" className="btn-quiet" onClick={() => { setEditing(null); setForm({ record_type: "visit", title: "", record_date: today(), details: "" }); }}>Cancel</button>}</div>
      </form>

      <div role="tablist" aria-label="View" className="flex gap-2">
        {(["list", "timeline"] as const).map((k) => <button key={k} role="tab" aria-selected={tab === k} onClick={() => setTab(k)} className={`btn ${tab === k ? "bg-brand text-white" : "border-2 border-line bg-surface"}`}>{k === "list" ? "Records" : "Health timeline"}</button>)}
      </div>

      {tab === "list" ? (records === null ? <Spinner /> : records.length === 0 ? <Empty title="No records yet">Add your first record above.</Empty> : (
        <ul className="space-y-3">{records.map((r) => (
          <li key={r.id} className="rounded-2xl border border-line bg-surface p-4">
            <div className="flex flex-wrap items-start gap-3"><div className="min-w-[12rem] flex-1"><p className="font-bold">{r.title}</p><p className="text-sm text-muted">{label(r.record_type)} · {new Date(r.record_date).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}</p></div>
              <button className="btn-quiet !min-h-[44px]" onClick={() => { setEditing(r.id); setForm({ record_type: r.record_type, title: r.title, record_date: r.record_date, details: r.details ?? "" }); window.scrollTo({ top: 0, behavior: "smooth" }); }}>Edit</button>
              <button className="btn-quiet !min-h-[44px] text-sos" onClick={() => del(r)}>Delete</button></div>
            {r.details && <p className="mt-2 whitespace-pre-line">{r.details}</p>}
          </li>))}</ul>
      )) : (events === null ? <Spinner /> : events.length === 0 ? <Empty title="Your timeline is empty">Records, confirmed prescriptions and emergency alerts will appear here.</Empty> : (
        <ol className="relative ml-3 space-y-5 border-l-4 border-line pl-6">{events.map((e) => (
          <li key={e.kind + e.id} className="relative"><span className={`absolute -left-[34px] top-1.5 h-4 w-4 rounded-full ring-4 ring-ground ${KIND_DOT[e.kind]}`} aria-hidden />
            <time className="text-sm text-muted" dateTime={e.at}>{new Date(e.at).toLocaleDateString("en-IN", { day: "numeric", month: "long", year: "numeric" })}</time>
            <p className="font-bold">{e.title}</p>{e.subtitle && <p className="text-muted">{e.subtitle}</p>}</li>))}</ol>))}
    </div>
  );
}
