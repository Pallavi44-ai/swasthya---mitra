"use client";
import { useEffect, useRef, useState } from "react";
import { api, ApiError } from "@/lib/api";
import type { Challenge } from "@/lib/types";
import { Banner } from "./ui";

const mmss = (s: number) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, "0")}`;

/** Enter the 6-digit code. Shows where it was sent, time left, attempts left, and a safe "send again" button. */
export function CodeStep({ ch: initial, onSubmit, submitLabel = "Confirm", busyLabel = "Checking…", extra }: {
  ch: Challenge; onSubmit: (code: string, challengeId: string) => Promise<void>; submitLabel?: string; busyLabel?: string; extra?: React.ReactNode;
}) {
  const [ch, setCh] = useState(initial);
  const [code, setCode] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [left, setLeft] = useState<number | null>(null);
  const [busy, setBusy] = useState(false);
  const [info, setInfo] = useState<string | null>(null);
  const [expires, setExpires] = useState(initial.expires_in);
  const [wait, setWait] = useState(initial.resend_in);
  const input = useRef<HTMLInputElement>(null);

  useEffect(() => { setCh(initial); setExpires(initial.expires_in); setWait(initial.resend_in); }, [initial]);
  useEffect(() => { input.current?.focus(); }, []);
  useEffect(() => {
    const t = setInterval(() => { setExpires((x) => Math.max(0, x - 1)); setWait((x) => Math.max(0, x - 1)); }, 1000);
    return () => clearInterval(t);
  }, []);

  async function submit(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null); setInfo(null);
    try { await onSubmit(code, ch.challenge_id); }
    catch (er) {
      const d = er instanceof ApiError ? (er.detail as { attempts_left?: number; code?: string } | undefined) : undefined;
      setErr(er instanceof Error ? er.message : "Something went wrong.");
      setLeft(typeof d?.attempts_left === "number" ? d.attempts_left : null);
      if (d?.code === "locked" || d?.code === "expired") setExpires(0);
      setCode(""); input.current?.focus();
    } finally { setBusy(false); }
  }

  async function resend() {
    setErr(null); setInfo(null); setLeft(null);
    try {
      const st = await api<Challenge>("/auth/mfa/send", { body: { challenge_id: ch.challenge_id } });
      setCh({ ...ch, ...st }); setExpires(st.expires_in); setWait(st.resend_in); setCode(""); setInfo("A new code has been sent. The old code no longer works."); input.current?.focus();
    } catch (er) {
      const d = er instanceof ApiError ? (er.detail as { retry_after?: number } | undefined) : undefined;
      if (d?.retry_after) setWait(d.retry_after);
      setErr(er instanceof Error ? er.message : "Could not send a new code.");
    }
  }

  const dest = ch.destination_masked;
  return (
    <form onSubmit={submit} className="panel space-y-5" noValidate>
      <p className="text-lg">We sent a 6-digit code {ch.channel === "sms" ? "by text message to" : "by email to"} <strong>{dest}</strong>. Type it below.</p>
      {info && <Banner tone="ok">{info}</Banner>}
      {err && <Banner tone="error">{err}{left !== null && left > 0 ? ` You have ${left} ${left === 1 ? "try" : "tries"} left.` : ""}</Banner>}
      <div>
        <label htmlFor="otp" className="label !text-base">6-digit code</label>
        <input id="otp" ref={input} className="field !min-h-[72px] text-center text-4xl font-bold tracking-[0.5em]" inputMode="numeric" pattern="[0-9]*" autoComplete="one-time-code"
          maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, "").slice(0, 6))} aria-describedby="otp-help" />
        <p id="otp-help" className="mt-2 text-muted">{expires > 0 ? `This code works for ${mmss(expires)} more.` : "This code has run out. Please ask for a new one."}</p>
      </div>
      <button className="btn-primary w-full" disabled={busy || code.length !== 6 || expires === 0}>{busy ? busyLabel : submitLabel}</button>
      <div className="border-t border-line pt-4">
        <button type="button" className="btn-quiet w-full" onClick={resend} disabled={wait > 0 || ch.sends_left <= 0}>
          {wait > 0 ? `Send a new code in ${wait}s` : "Send me a new code"}
        </button>
        <p className="mt-2 text-sm text-muted">Didn’t get it? Check your spam folder. Never tell anyone this code – we will never ask for it.</p>
      </div>
      {extra}
    </form>
  );
}
