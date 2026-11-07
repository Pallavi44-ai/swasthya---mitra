"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { speak } from "@/lib/speech";
import { t } from "@/lib/i18n";
import type { EmergencyInfo } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Banner, Spinner, errMsg } from "@/components/ui";
import Link from "next/link";

interface Share { message: string; location_included: boolean; contacts: { id: string; name: string; phone: string; sms_href: string; whatsapp_href: string; tel_href: string }[] }

export default function Emergency() {
  const { lang } = usePrefs();
  const [info, setInfo] = useState<EmergencyInfo | null>(null);
  const [share, setShare] = useState<Share | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [locBusy, setLocBusy] = useState(false);

  useEffect(() => {
    api<EmergencyInfo>("/emergency").then(setInfo).catch((e) => setErr(errMsg(e)));
    api("/emergency/open", { method: "POST" }).catch(() => {});
  }, []);
  useEffect(() => { speak(t("emergencyHead", lang) + " " + t("call108", lang), lang); }, [lang]);

  async function prepare(withLocation: boolean) {
    setErr(null);
    const send = async (lat?: number, lon?: number) => { try { setShare(await api<Share>("/emergency/share-message", { body: { latitude: lat ?? null, longitude: lon ?? null } })); } catch (e) { setErr(errMsg(e)); } };
    if (withLocation && "geolocation" in navigator) {
      setLocBusy(true);
      navigator.geolocation.getCurrentPosition((p) => { setLocBusy(false); void send(p.coords.latitude, p.coords.longitude); },
        () => { setLocBusy(false); setErr("I could not get your location. The message will be prepared without it."); void send(); }, { timeout: 10000, maximumAge: 60000 });
    } else await send();
  }

  if (!info) return err ? <Banner tone="error">{err}</Banner> : <Spinner />;
  const helpline = info.numbers.find((n) => n.kind === "helpline");
  return (
    <div className="space-y-8">
      <section className="rounded-2xl bg-sos p-6 text-white sm:p-8">
        <h1 className="text-3xl font-bold">{t("emergencyHead", lang)}</h1>
        <a href="tel:108" className="mt-5 flex min-h-[88px] items-center justify-center gap-4 rounded-2xl bg-white text-3xl font-bold text-sos hover:bg-sos-tint sm:text-4xl"><Icon name="phone" className="h-10 w-10" /> {t("call108", lang)}</a>
        <p className="mt-4 text-lg">Free ambulance and emergency service in India. Stay on the line and follow the operator's instructions.</p>
      </section>
      {err && <Banner tone="warn">{err}</Banner>}

      <section aria-labelledby="c-h" className="space-y-3">
        <h2 id="c-h" className="text-xl font-bold">Call someone you trust</h2>
        {info.contacts.length === 0 ? <Banner tone="warn" title="No emergency contacts saved">Add one so you can reach them quickly. <Link href="/profile" className="font-bold underline">Add a contact</Link></Banner> : (
          <ul className="grid gap-3 sm:grid-cols-2">{info.contacts.map((c) => (
            <li key={c.id}><a href={`tel:${c.phone}`} className="flex min-h-[72px] items-center gap-4 rounded-2xl border-2 border-line bg-surface p-4 hover:border-brand"><Icon name="phone" className="h-8 w-8 text-brand" /><span><span className="block text-lg font-bold">{c.name}{c.is_primary && " ★"}</span><span className="text-muted">{c.phone}</span></span></a></li>))}</ul>)}
      </section>

      {info.contacts.length > 0 && (
        <section aria-labelledby="s-h" className="panel space-y-4">
          <h2 id="s-h" className="text-xl font-bold">Send an alert message</h2>
          <p className="text-muted">I prepare the message. Your own phone sends it when you tap a button below. Nothing is sent from our server.</p>
          {!share ? (
            <div className="flex flex-wrap gap-3">
              <button className="btn-primary" disabled={locBusy || !info.location_sharing_allowed} onClick={() => prepare(true)}><Icon name="alert" className="h-5 w-5" /> {locBusy ? "Finding location…" : "Prepare message with my location"}</button>
              <button className="btn-quiet" onClick={() => prepare(false)}>Prepare without location</button>
            </div>) : (
            <div className="space-y-3">
              <p className="rounded-xl bg-brand-tint p-4 font-bold">{share.message}</p>
              {!share.location_included && <p className="text-sm text-muted">Location is not included.</p>}
              <ul className="space-y-2">{share.contacts.map((c) => <li key={c.id} className="flex flex-wrap items-center gap-2"><span className="w-28 font-bold">{c.name}</span><a className="btn-quiet !min-h-[48px]" href={c.sms_href}>Text</a><a className="btn-quiet !min-h-[48px]" href={c.whatsapp_href} target="_blank" rel="noreferrer">WhatsApp</a></li>)}</ul>
            </div>)}
          {!info.location_sharing_allowed && <p className="text-sm text-muted">Sharing location is off. Turn it on in <Link href="/privacy" className="font-bold underline">Privacy</Link>.</p>}
        </section>)}

      {helpline && <section className="panel"><h2 className="text-xl font-bold">Feeling very low or unsafe?</h2><p className="mt-1 text-muted">Talking to someone helps. {helpline.label}.</p><a href={`tel:${helpline.number}`} className="btn-quiet mt-3"><Icon name="phone" /> Call {helpline.number}</a></section>}
      <p className="text-sm text-muted">Swasthya Mitra is not a doctor and cannot send help by itself. In an emergency always call 108.</p>
    </div>
  );
}
