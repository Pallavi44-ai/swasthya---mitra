"use client";
import { useCallback, useEffect, useState } from "react";
import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Challenge, SecurityOverview } from "@/lib/types";
import { biometricSupported, createPasskey, passkeyErrorText } from "@/lib/webauthn";
import { CodeStep } from "@/components/CodeStep";
import { Banner, Field, PageHeader, Spinner, errMsg, useToast } from "@/components/ui";

const when = (iso: string) => new Date(iso).toLocaleString();
const ACTION: Record<string, string> = { login_success: "Logged in", login_failed: "Wrong password entered", mfa_failed: "Wrong code entered", password_change: "Password changed", password_reset: "Password reset", logout_all: "Signed out of all devices" };
const device = (ua: string | null) => (!ua ? "Unknown device" : /Android/i.test(ua) ? "Android phone/tablet" : /iPhone|iPad/i.test(ua) ? "iPhone/iPad" : /Windows/i.test(ua) ? "Windows computer" : /Mac/i.test(ua) ? "Mac" : /Linux/i.test(ua) ? "Linux computer" : "Browser");

export default function Security() {
  const toast = useToast(); const { logout, refresh } = useAuth();
  const [o, setO] = useState<SecurityOverview | null>(null); const [err, setErr] = useState<string | null>(null);
  const [bio, setBio] = useState(false);
  const [pw, setPw] = useState("");                       // current password for sensitive actions
  const [phone, setPhone] = useState(""); const [phoneCh, setPhoneCh] = useState<Challenge | null>(null);
  const [cur, setCur] = useState(""); const [next, setNext] = useState("");
  const load = useCallback(async () => { try { setO(await api<SecurityOverview>("/account/security")); } catch (e) { setErr(errMsg(e)); } }, []);
  useEffect(() => { void load(); setBio(biometricSupported()); }, [load]);

  const run = async (fn: () => Promise<void>, ok?: string) => { setErr(null); try { await fn(); if (ok) toast(ok); await load(); } catch (e) { setErr(e instanceof ApiError ? e.message : passkeyErrorText(e)); window.scrollTo(0, 0); } };

  if (!o) return err ? <Banner tone="error">{err}</Banner> : <Spinner />;
  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader title="Sign-in security" intro="Every login needs your password and a second proof. These settings control that second step." />
      {err && <Banner tone="error">{err}</Banner>}

      <section className="panel space-y-4">
        <h2 className="text-xl font-bold">Where your login codes go</h2>
        <p>Email: <strong>{o.email}</strong> {o.email_verified ? "✓ confirmed" : "(not confirmed)"}</p>
        <p>Mobile: <strong>{o.phone_masked ?? "none added"}</strong> {o.phone_masked && (o.phone_verified ? "✓ confirmed" : "(not confirmed)")}</p>
        <Field label="Your password (needed to change these settings)" htmlFor="sp"><input id="sp" type="password" autoComplete="current-password" className="field" value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
        <div className="flex flex-wrap gap-3">
          {(["email", "sms"] as const).map((c) => (
            <button key={c} className={o.mfa_channel === c ? "btn-primary" : "btn-quiet"} aria-pressed={o.mfa_channel === c} disabled={c === "sms" && !o.phone_verified}
              onClick={() => run(async () => { await api("/account/security/channel", { method: "PUT", body: { channel: c, password: pw } }); }, "Saved")}>
              {c === "email" ? "Send codes to my email" : "Send codes to my mobile"}
            </button>))}
        </div>
        {o.sms_available ? (phoneCh ? (
          <CodeStep ch={phoneCh} submitLabel="Confirm my mobile number" onSubmit={async (code, id) => { await api("/account/security/phone/verify", { body: { challenge_id: id, code } }); setPhoneCh(null); setPhone(""); toast("Mobile number confirmed"); await load(); }} />
        ) : (
          <form className="space-y-3" onSubmit={(e) => { e.preventDefault(); void run(async () => { setPhoneCh(await api<Challenge>("/account/security/phone", { body: { phone, password: pw } })); }); }}>
            <Field label={o.phone_masked ? "Change mobile number" : "Add a mobile number"} htmlFor="ph" hint="With country code, e.g. +919876543210. We will text a code to confirm it."><input id="ph" type="tel" className="field" value={phone} onChange={(e) => setPhone(e.target.value)} /></Field>
            <button className="btn-quiet" disabled={!phone || !pw}>Send a confirmation code</button>
          </form>
        )) : <Banner tone="info">Text-message codes are not switched on for this server. Codes go to your email.</Banner>}
      </section>

      <section className="panel space-y-4">
        <h2 className="text-xl font-bold">Fingerprint or face sign-in</h2>
        <p className="text-muted">Optional. After your password, you can confirm with your phone or computer’s fingerprint, face or screen lock instead of waiting for a code. Your fingerprint never leaves your device.</p>
        {!bio && <Banner tone="warn">This browser or device does not support it (it needs a secure address and a device with fingerprint, face or screen lock). Codes still work.</Banner>}
        <ul className="divide-y divide-line">
          {o.passkeys.map((p) => (
            <li key={p.id} className="flex items-center justify-between gap-3 py-3"><span><strong>{p.name}</strong><br /><span className="text-sm text-muted">Added {when(p.created_at)}{p.last_used_at ? ` · last used ${when(p.last_used_at)}` : ""}</span></span>
              <button className="btn-quiet" onClick={() => run(async () => { await api(`/account/security/passkeys/${p.id}`, { method: "DELETE" }); }, "Removed")}>Remove</button></li>))}
          {!o.passkeys.length && <li className="py-3 text-muted">No fingerprint/face sign-in set up.</li>}
        </ul>
        <button className="btn-primary" disabled={!bio || !pw} onClick={() => run(async () => {
          const st = await api<{ challenge_id: string; options: Record<string, unknown> }>("/auth/webauthn/register/options", { body: { password: pw } });
          const credential = await createPasskey(st.options);
          await api("/auth/webauthn/register/verify", { body: { challenge_id: st.challenge_id, credential, name: device(navigator.userAgent) } });
        }, "Fingerprint/face sign-in added")}>Set up fingerprint or face on this device</button>
        {!pw && bio && <p className="text-sm text-muted">Type your password in the box above first.</p>}
      </section>

      <section className="panel space-y-4">
        <h2 className="text-xl font-bold">Change my password</h2>
        <form className="space-y-4" onSubmit={(e) => { e.preventDefault(); void run(async () => { await api("/auth/change-password", { body: { current_password: cur, new_password: next } }); setCur(""); setNext(""); }, "Password changed. Other devices were signed out."); }}>
          <Field label="Current password" htmlFor="cp"><input id="cp" type="password" autoComplete="current-password" className="field" value={cur} onChange={(e) => setCur(e.target.value)} /></Field>
          <Field label="New password" htmlFor="npw" hint="At least 8 characters, with a letter and a number."><input id="npw" type="password" minLength={8} autoComplete="new-password" className="field" value={next} onChange={(e) => setNext(e.target.value)} /></Field>
          <button className="btn-quiet" disabled={!cur || next.length < 8}>Change password</button>
        </form>
      </section>

      <section className="panel space-y-4">
        <h2 className="text-xl font-bold">Devices signed in</h2>
        <p className="text-muted">You are signed out automatically after {o.session_idle_minutes} minutes without use.</p>
        <ul className="divide-y divide-line">
          {o.sessions.map((s) => (
            <li key={s.id} className="flex items-center justify-between gap-3 py-3">
              <span><strong>{device(s.device)}</strong>{s.current && <span className="ml-2 rounded-full bg-brand-tint px-2 py-0.5 text-sm font-bold">This device</span>}<br /><span className="text-sm text-muted">Signed in {when(s.created_at)} · last active {when(s.last_seen_at)}</span></span>
              {!s.current && <button className="btn-quiet" onClick={() => run(async () => { await api(`/account/security/sessions/${s.id}`, { method: "DELETE" }); }, "Device signed out")}>Sign out</button>}
            </li>))}
        </ul>
        <button className="btn-quiet" onClick={async () => { await api("/auth/logout-all", { method: "POST" }); await refresh().catch(() => undefined); await logout().catch(() => undefined); }}>Sign out of all devices</button>
      </section>

      <section className="panel space-y-2">
        <h2 className="text-xl font-bold">Recent sign-in activity</h2>
        <ul className="divide-y divide-line">{o.recent_activity.map((a, i) => <li key={i} className="flex justify-between gap-3 py-2"><span>{ACTION[a.action] ?? a.action}</span><span className="text-muted">{when(a.at)}</span></li>)}
          {!o.recent_activity.length && <li className="py-2 text-muted">Nothing yet.</li>}</ul>
        <p className="text-sm text-muted">If you see something you do not recognise, change your password and sign out of all devices.</p>
      </section>
    </div>
  );
}
