"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Challenge, ConsentKey } from "@/lib/types";
import { AuthShell } from "@/components/AuthShell";
import { CodeStep } from "@/components/CodeStep";
import { Banner, Field, errMsg } from "@/components/ui";

const CONSENTS: { key: ConsentKey; title: string; text: string }[] = [
  { key: "ai_processing", title: "Use the AI service", text: "Send my questions, voice and prescription photos to Google Gemini for AI answers. If off, only local tools are used." },
  { key: "store_chat_history", title: "Save my conversations", text: "Keep my chats (encrypted) so I can read them later." },
  { key: "health_data_personalisation", title: "Personalise with my health details", text: "Use my profile, allergies and confirmed medicines to tailor answers." },
  { key: "store_prescription_images", title: "Keep my prescription photos", text: "Store photos (encrypted). If off, photos are deleted after reading." },
  { key: "emergency_sharing", title: "Share my location in an emergency", text: "Add my location to the alert message I send to my contacts." },
];
const LANGS = [["en", "English"], ["hi", "हिन्दी"], ["kn", "ಕನ್ನಡ"], ["te", "తెలుగు"]];

export default function Register() {
  const router = useRouter(); const { refresh } = useAuth();
  const [f, setF] = useState({ full_name: "", email: "", password: "", phone: "", preferred_language: "en", mfa_channel: "email" as "email" | "sms" });
  const [consents, setConsents] = useState<Record<string, boolean>>({});  // all OFF until the person ticks them
  const [ack, setAck] = useState(false); const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);
  const [ch, setCh] = useState<Challenge | null>(null);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try {
      const body = { ...f, phone: f.phone.trim() || null, accepted_disclaimer: ack, consents };
      setCh(await api<Challenge>("/auth/register", { body }));
      window.scrollTo(0, 0);
    } catch (er) { setErr(errMsg(er)); } finally { setBusy(false); }
  }

  if (ch) return (
    <AuthShell title={ch.channel === "sms" ? "Check your messages" : "Check your email"} intro="One last step: confirm it is really you."
      footer={<button type="button" className="font-bold text-brand underline" onClick={() => setCh(null)}>← Change my details</button>}>
      <CodeStep ch={ch} submitLabel="Confirm and create my account"
        onSubmit={async (code, id) => { await api("/auth/register/verify", { body: { challenge_id: id, code } }); await refresh(); router.replace("/dashboard"); }} />
    </AuthShell>
  );

  const set = (k: string, v: string) => setF({ ...f, [k]: v });
  return (
    <AuthShell title="Create your account" intro="It takes about two minutes. We will send a code to confirm your email or phone."
      footer={<p>Already registered? <Link href="/login" className="font-bold text-brand underline">Log in</Link></p>}>
      <form onSubmit={submit} className="space-y-6">
        {err && <Banner tone="error">{err}</Banner>}
        <section className="panel space-y-5">
          <Field label="Your name" htmlFor="n"><input id="n" required autoComplete="name" className="field" value={f.full_name} onChange={(e) => set("full_name", e.target.value)} /></Field>
          <Field label="Email address" htmlFor="e"><input id="e" type="email" required autoComplete="email" className="field" value={f.email} onChange={(e) => set("email", e.target.value)} /></Field>
          <Field label="Choose a password" htmlFor="p" hint="At least 8 characters, with a letter and a number. Easy to remember, hard to guess – for example three words and a number.">
            <input id="p" type="password" required minLength={8} maxLength={72} autoComplete="new-password" className="field" value={f.password} onChange={(e) => set("password", e.target.value)} />
          </Field>
          <Field label="Language" htmlFor="l">
            <select id="l" className="field" value={f.preferred_language} onChange={(e) => set("preferred_language", e.target.value)}>{LANGS.map(([v, n]) => <option key={v} value={v}>{n}</option>)}</select>
          </Field>
        </section>

        <fieldset className="panel space-y-3">
          <legend className="px-1 text-lg font-bold">Where should we send your login codes?</legend>
          {([["email", "My email address"], ["sms", "My mobile phone (text message)"]] as const).map(([v, label]) => (
            <label key={v} className="flex min-h-[52px] cursor-pointer items-center gap-3 rounded-xl border-2 border-line p-3 has-[:checked]:border-brand">
              <input type="radio" name="ch" className="h-7 w-7 accent-[var(--brand)]" checked={f.mfa_channel === v} onChange={() => set("mfa_channel", v)} /> <span className="text-lg">{label}</span>
            </label>))}
          <Field label={f.mfa_channel === "sms" ? "Mobile number" : "Mobile number (optional)"} htmlFor="ph" hint="With country code, for example +919876543210">
            <input id="ph" type="tel" autoComplete="tel" required={f.mfa_channel === "sms"} className="field" value={f.phone} onChange={(e) => set("phone", e.target.value)} />
          </Field>
        </fieldset>

        <fieldset className="panel space-y-3">
          <legend className="px-1 text-lg font-bold">Your choices about your data</legend>
          <p className="text-muted">Everything is off until you tick it. You can change this any time under Privacy.</p>
          {CONSENTS.map((c) => (
            <label key={c.key} className="flex cursor-pointer gap-3">
              <input type="checkbox" className="mt-1 h-7 w-7 shrink-0 accent-[var(--brand)]" checked={!!consents[c.key]} onChange={(e) => setConsents({ ...consents, [c.key]: e.target.checked })} />
              <span><strong>{c.title}.</strong> <span className="text-muted">{c.text}</span></span>
            </label>))}
        </fieldset>

        <label className="panel flex cursor-pointer gap-3">
          <input type="checkbox" required className="mt-1 h-7 w-7 shrink-0 accent-[var(--brand)]" checked={ack} onChange={(e) => setAck(e.target.checked)} />
          <span className="text-lg"><strong>Required:</strong> I understand Swasthya Mitra does not replace a doctor. In an emergency I will call 108.</span>
        </label>
        <button className="btn-primary w-full" disabled={busy || !ack}>{busy ? "Sending code…" : "Continue – send me a code"}</button>
      </form>
    </AuthShell>
  );
}
