"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import type { Challenge } from "@/lib/types";
import { AuthShell } from "@/components/AuthShell";
import { CodeStep } from "@/components/CodeStep";
import { Banner, Field, errMsg } from "@/components/ui";

/** Recovery = code sent to the registered email/phone, then a new password. The server answers identically
 *  whether or not the email has an account, so this page never says "no such account". */
export default function Forgot() {
  const router = useRouter();
  const [email, setEmail] = useState(""); const [ch, setCh] = useState<Challenge | null>(null);
  const [pw, setPw] = useState(""); const [pw2, setPw2] = useState(""); const [err, setErr] = useState<string | null>(null); const [busy, setBusy] = useState(false);

  async function start(e: React.FormEvent) {
    e.preventDefault(); setBusy(true); setErr(null);
    try { setCh(await api<Challenge>("/auth/forgot-password", { body: { email } })); } catch (er) { setErr(errMsg(er)); } finally { setBusy(false); }
  }

  if (!ch) return (
    <AuthShell title="Forgot your password?" intro="Type your email address. If we have an account for it, we will send a code to your registered email or phone."
      footer={<p><Link href="/login" className="font-bold text-brand underline">← Back to log in</Link></p>}>
      <form onSubmit={start} className="panel space-y-5">
        {err && <Banner tone="error">{err}</Banner>}
        <Field label="Email address" htmlFor="email"><input id="email" type="email" required autoComplete="email" className="field" value={email} onChange={(e) => setEmail(e.target.value)} /></Field>
        <button className="btn-primary w-full" disabled={busy}>{busy ? "Please wait…" : "Send me a code"}</button>
      </form>
    </AuthShell>
  );

  const mismatch = pw2.length > 0 && pw !== pw2;
  return (
    <AuthShell title="Choose a new password" intro="Enter the code we sent, then your new password." footer={<button type="button" className="font-bold text-brand underline" onClick={() => setCh(null)}>← Start again</button>}>
      <div className="space-y-5">
        <div className="panel space-y-5">
          <Field label="New password" htmlFor="np" hint="At least 8 characters, with a letter and a number."><input id="np" type="password" minLength={8} maxLength={72} autoComplete="new-password" className="field" value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
          <Field label="Type the new password again" htmlFor="np2" error={mismatch ? "The two passwords are not the same." : null}><input id="np2" type="password" autoComplete="new-password" className="field" value={pw2} onChange={(e) => setPw2(e.target.value)} /></Field>
        </div>
        <Banner tone="info">{ch.message ?? "If an account exists, we have sent a code."}</Banner>
        <CodeStep ch={{ ...ch, destination_masked: ch.destination_masked }} submitLabel="Change my password"
          onSubmit={async (code, id) => {
            if (pw.length < 8 || mismatch || pw !== pw2) throw new Error("Please type the same new password twice (at least 8 characters).");
            await api("/auth/reset-password", { body: { challenge_id: id, code, new_password: pw } });
            router.replace("/login?reset=1");
          }} />
      </div>
    </AuthShell>
  );
}
