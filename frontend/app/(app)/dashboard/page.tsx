"use client";
import Link from "next/link";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";
import { t } from "@/lib/i18n";
import type { Adherence, Contact, Dose, TimelineEvent } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Banner, Empty, Spinner, errMsg, useToast } from "@/components/ui";

export default function Dashboard() {
  const { user } = useAuth();
  const { lang } = usePrefs();
  const toast = useToast();
  const [doses, setDoses] = useState<Dose[] | null>(null);
  const [adh, setAdh] = useState<Adherence | null>(null);
  const [contacts, setContacts] = useState<Contact[] | null>(null);
  const [events, setEvents] = useState<TimelineEvent[] | null>(null);
  const [error, setError] = useState<string | null>(null);

  const load = () => Promise.all([
    api<{ doses: Dose[] }>("/reminders/today").then((r) => setDoses(r.doses)),
    api<Adherence>("/reminders/adherence?days=7").then(setAdh),
    api<Contact[]>("/contacts").then(setContacts),
    api<TimelineEvent[]>("/timeline?limit=4").then(setEvents),
  ]).catch((e) => setError(errMsg(e)));
  useEffect(() => { void load(); }, []);

  async function mark(d: Dose, status: "taken" | "skipped") {
    try { await api(`/reminders/doses/${d.id}`, { body: { status } }); toast(status === "taken" ? `${d.medicine_name}: ${t("taken", lang)}` : `${d.medicine_name}: ${t("skip", lang)}`); await load(); }
    catch (e) { toast(errMsg(e), "error"); }
  }

  return (
    <div className="space-y-8">
      <section className="grid gap-6 rounded-2xl bg-brand p-6 text-white sm:grid-cols-[1fr_auto] sm:items-center sm:p-8">
        <div>
          <h1 className="text-3xl font-bold">{t("namaste", lang)}, {user?.full_name.split(" ")[0]}</h1>
          <p className="mt-2 max-w-md text-lg opacity-95">{lang === "en" ? "Ask a health question by speaking or typing. I will explain in simple words." : t("typeHere", lang)}</p>
        </div>
        <Link href="/chat?voice=1" className="group relative mx-auto grid h-36 w-36 place-items-center rounded-full bg-white text-brand sm:mx-0" aria-label={t("tapSpeak", lang)}>
          <span className="orb-ring absolute inset-0 rounded-full bg-white" aria-hidden />
          <span className="relative flex flex-col items-center gap-1 font-bold"><Icon name="mic" className="h-12 w-12" /><span className="px-2 text-center text-sm leading-tight">{t("tapSpeak", lang)}</span></span>
        </Link>
      </section>

      {error && <Banner tone="error" title="Could not load everything">{error}</Banner>}

      <section aria-labelledby="meds-h">
        <div className="mb-3 flex items-end justify-between"><h2 id="meds-h" className="text-xl font-bold">{t("todayMeds", lang)}</h2><Link className="font-bold text-brand underline" href="/reminders">{t("reminders", lang)}</Link></div>
        {doses === null ? <Spinner /> : doses.length === 0 ? (
          <Empty title="No medicines scheduled today" action={<Link href="/prescriptions" className="btn-primary"><Icon name="camera" /> Scan a prescription</Link>}>
            Scan a prescription, confirm the medicines, then set reminder times. Reminders are only created from details you have confirmed.
          </Empty>
        ) : (
          <ol className="divide-y divide-line rounded-2xl border border-line bg-surface">
            {doses.map((d) => (
              <li key={d.id} className="flex flex-wrap items-center gap-4 p-4">
                <span className={`w-24 text-3xl font-bold tabular-nums ${d.status === "pending" ? "text-saffron-ink" : "text-muted"}`}>{d.local_time}</span>
                <div className="min-w-[12rem] flex-1"><p className="text-lg font-bold">{d.medicine_name} {d.strength}</p><p className="text-muted">{d.dosage_instruction}</p></div>
                {d.status === "pending" ? (
                  <div className="flex gap-2"><button className="btn-primary" onClick={() => mark(d, "taken")}>{t("taken", lang)}</button><button className="btn-quiet" onClick={() => mark(d, "skipped")}>{t("skip", lang)}</button></div>
                ) : <span className={`rounded-full px-4 py-1 font-bold ${d.status === "taken" ? "bg-ok-tint text-ok" : "bg-saffron-tint text-saffron-ink"}`}>{d.status}</span>}
              </li>
            ))}
          </ol>
        )}
      </section>

      <div className="grid gap-6 md:grid-cols-2">
        <section className="panel" aria-labelledby="adh-h">
          <h2 id="adh-h" className="text-xl font-bold">Last 7 days</h2>
          {!adh ? <Spinner /> : adh.percent === null ? <p className="mt-2 text-muted">No doses have come due yet.</p> : (
            <>
              <p className="mt-2 text-3xl font-bold text-brand">{adh.percent}% <span className="text-base font-normal text-muted">of doses taken</span></p>
              <div className="mt-4 flex h-20 items-end gap-2" role="img" aria-label={`Doses taken per day: ${adh.days.map((d) => d.taken).join(", ")}`}>
                {adh.days.map((d) => { const tot = d.taken + d.skipped + d.missed; return (
                  <div key={d.date} className="flex flex-1 flex-col items-center gap-1">
                    <div className="flex w-full flex-1 items-end rounded bg-brand-tint"><div className="w-full rounded bg-brand" style={{ height: tot ? `${(100 * d.taken) / tot}%` : 0 }} /></div>
                    <span className="text-xs text-muted">{new Date(d.date).toLocaleDateString("en-IN", { weekday: "narrow" })}</span>
                  </div>); })}
              </div>
            </>
          )}
        </section>

        <section className="panel space-y-3" aria-labelledby="next-h">
          <h2 id="next-h" className="text-xl font-bold">Set up</h2>
          {contacts && contacts.length === 0 && <Banner tone="warn" title="Add an emergency contact">So the emergency screen can call or message someone for you. <Link className="font-bold underline" href="/profile">Add contact</Link></Banner>}
          <Link href="/prescriptions" className="btn-quiet w-full justify-start"><Icon name="camera" /> Scan a prescription</Link>
          <Link href="/profile" className="btn-quiet w-full justify-start"><Icon name="heart" /> Allergies and conditions</Link>
          <Link href="/privacy" className="btn-quiet w-full justify-start"><Icon name="shield" /> What I may use (consent)</Link>
        </section>
      </div>

      <section aria-labelledby="tl-h">
        <h2 id="tl-h" className="mb-3 text-xl font-bold">Recent health timeline</h2>
        {events === null ? <Spinner /> : events.length === 0 ? <p className="text-muted">Nothing yet. Records, confirmed prescriptions and emergency alerts appear here.</p> : (
          <ul className="space-y-2">{events.map((e) => (
            <li key={e.id} className="flex items-center gap-3 rounded-xl border border-line bg-surface p-3">
              <span className={`h-3 w-3 shrink-0 rounded-full ${e.kind === "emergency" ? "bg-sos" : e.kind === "prescription" ? "bg-saffron" : "bg-brand"}`} aria-hidden />
              <div className="min-w-0 flex-1"><p className="font-bold">{e.title}</p>{e.subtitle && <p className="truncate text-sm text-muted">{e.subtitle}</p>}</div>
              <time className="text-sm text-muted" dateTime={e.at}>{new Date(e.at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</time>
            </li>))}</ul>
        )}
      </section>
    </div>
  );
}
