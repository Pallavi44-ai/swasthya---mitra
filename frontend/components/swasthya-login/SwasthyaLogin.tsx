"use client";
/**
 * Swasthya Mitra AI – standalone login screen (UI only).
 * Needs only React + Next.js. No UI libraries, no external images, no secrets.
 *
 * >>> API INTEGRATION POINT: pass `onSignIn` (see props). Nothing is sent anywhere until you do. <<<
 */
import Link from "next/link";
import { useEffect, useId, useRef, useState, type FormEvent } from "react";
import { LoginIllustration } from "./LoginIllustration";
import styles from "./login.module.css";
import type { Challenge } from "@/lib/types";

export interface SignInValues { email: string; password: string; remember: boolean }
/** What your handler returns. Show a message with ok:false; ok:true lets the parent navigate. */
export type SignInResult =
  | { ok: true }
  | { ok: "challenge"; challenge: Challenge; signup?: boolean }
  | { ok: false; message: string; field?: "email" | "password" };

export interface SwasthyaLoginProps {
  onSignIn?: (values: SignInValues) => Promise<SignInResult>;
  onSuccess?: () => void;
  onChallenge?: (challenge: Challenge, signup?: boolean) => void;
  registerHref?: string;
  forgotPasswordHref?: string;
}

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/;
const REMEMBER_KEY = "sm_login_email"; // stores the EMAIL ONLY, never the password

const safeStore = {
  get: () => { try { return window.localStorage.getItem(REMEMBER_KEY) ?? ""; } catch { return ""; } },
  set: (v: string) => { try { window.localStorage.setItem(REMEMBER_KEY, v); } catch { /* storage blocked – fine */ } },
  clear: () => { try { window.localStorage.removeItem(REMEMBER_KEY); } catch { /* ignore */ } },
};

export default function SwasthyaLogin({
  onSignIn,
  onSuccess,
  onChallenge,
  registerHref = "/register",
  forgotPasswordHref = "/forgot-password",
}: SwasthyaLoginProps) {
  const uid = useId();
  const ids = { email: `${uid}-email`, pw: `${uid}-pw`, emailErr: `${uid}-email-err`, pwErr: `${uid}-pw-err`, form: `${uid}-form-err` };
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [show, setShow] = useState(false);
  const [remember, setRemember] = useState(false);
  const [errors, setErrors] = useState<{ email?: string; password?: string; form?: string }>({});
  const [busy, setBusy] = useState(false);
  const [capsOn, setCapsOn] = useState(false);
  const emailRef = useRef<HTMLInputElement>(null);
  const pwRef = useRef<HTMLInputElement>(null);

  useEffect(() => { const saved = safeStore.get(); if (saved) { setEmail(saved); setRemember(true); } }, []);

  // Keep the focused field visible when the phone keyboard opens.
  const keepVisible = (e: React.FocusEvent<HTMLInputElement>) => {
    const el = e.currentTarget;
    window.setTimeout(() => el.scrollIntoView({ block: "center", behavior: "smooth" }), 250);
  };

  function validate(): boolean {
    const next: typeof errors = {};
    if (!email.trim()) next.email = "Please type your email address.";
    else if (!EMAIL_RE.test(email.trim())) next.email = "This does not look like an email address. Example: name@example.com";
    if (!password) next.password = "Please type your password.";
    setErrors(next);
    if (next.email) emailRef.current?.focus(); else if (next.password) pwRef.current?.focus();
    return !next.email && !next.password;
  }

  async function submit(e: FormEvent) {
  e.preventDefault();
  if (busy || !validate()) return;

  setBusy(true);
  setErrors({});

  try {
    const result: SignInResult = onSignIn
      ? await onSignIn({
          email: email.trim(),
          password,
          remember,
        })
      : {
          ok: false,
          message: "Sign-in is not connected yet. Please try again.",
        };

    // Step 1: Backend returned an OTP/biometric challenge
    if (result.ok === "challenge") {
      if (!onChallenge) {
        setErrors({
          form: "Verification could not start. Please try again.",
        });
        return;
      }

      remember ? safeStore.set(email.trim()) : safeStore.clear();
      setPassword("");

      onChallenge(result.challenge, result.signup);
    }

    // Step 2: Login completed successfully
    else if (result.ok === true) {
      remember ? safeStore.set(email.trim()) : safeStore.clear();
      setPassword("");
      onSuccess?.();
    }

    // Step 3: Login failed
    else {
      setErrors(
        result.field
          ? { [result.field]: result.message }
          : { form: result.message }
      );

      (result.field === "email" ? emailRef : pwRef).current?.focus();
    }
  } catch {
    setErrors({
      form: "We could not reach the server. Please check your internet and try again.",
    });
  } finally {
    setBusy(false);
  }
}

  return (
    <div className={styles.page}>
      <a href={`#${ids.form}-card`} className={styles.skip}>Skip to sign-in form</a>
      <div className={styles.aurora} aria-hidden="true" />

      <main className={styles.shell}>
        {/* ---------- Hero / illustration ---------- */}
        <section className={styles.hero} aria-labelledby={`${uid}-brand`}>
          <div className={styles.brand} id={`${uid}-brand`}>
            <span className={styles.logo} aria-hidden="true">
              <svg viewBox="0 0 24 24" width="26" height="26"><path d="M12 21s-7.5-4.6-9.3-9.2C1.3 8.2 3.4 5 6.6 5c2 0 3.6 1.1 5.4 3.1C13.800 6.100 15.400 5 17.400 5c3.200 0 5.300 3.200 3.900 6.800C19.500 16.400 12 21 12 21z" fill="currentColor" /></svg>
            </span>
            <span className={styles.brandText}>Swasthya Mitra <b>AI</b></span>
          </div>

          <div className={styles.art}>
            <LoginIllustration className={styles.illustration} />
            <div className={`${styles.chip} ${styles.chip1}`} aria-hidden="true"><span className={styles.chipIcon}>💊</span><span><strong>Medicine time</strong><small>8:00 AM · Metformin</small></span></div>
            <div className={`${styles.chip} ${styles.chip2}`} aria-hidden="true"><span className={`${styles.chipIcon} ${styles.beat}`}>❤</span><span><strong>72 bpm</strong><small>Heart looks steady</small></span></div>
            <div className={`${styles.chip} ${styles.chip3}`} aria-hidden="true"><span className={styles.chipIcon}>🤖</span><span><strong>Good morning!</strong><small>How are you feeling today?</small></span></div>
          </div>
          <p className={styles.heroNote}>Medicine reminders · health questions in your language · emergency help</p>
        </section>

        {/* ---------- Form ---------- */}
        <section className={styles.card} id={`${ids.form}-card`} aria-labelledby={`${uid}-title`}>
          <h1 id={`${uid}-title`} className={styles.title}>Welcome Back!</h1>
          <p className={styles.subtitle}>Your health companion is always by your side.</p>

          <form onSubmit={submit} noValidate aria-describedby={errors.form ? ids.form : undefined}>
            {errors.form && <div id={ids.form} role="alert" className={styles.formError}><span aria-hidden="true">⚠</span> {errors.form}</div>}

            <div className={`${styles.field} ${errors.email ? styles.invalid : ""}`}>
              <label htmlFor={ids.email} className={styles.label}>Email address</label>
              <div className={styles.inputWrap}>
                <span className={styles.icon} aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="5" width="18" height="14" rx="3" /><path d="m4 7 8 6 8-6" /></svg></span>
                <input ref={emailRef} id={ids.email} type="email" inputMode="email" autoComplete="username" autoCapitalize="none" spellCheck={false}
                  className={styles.input} value={email} onChange={(e) => setEmail(e.target.value)} onFocus={keepVisible}
                  aria-invalid={!!errors.email} aria-describedby={errors.email ? ids.emailErr : undefined} placeholder="name@example.com" />
              </div>
              {errors.email && <p id={ids.emailErr} role="alert" className={styles.error}>{errors.email}</p>}
            </div>

            <div className={`${styles.field} ${errors.password ? styles.invalid : ""}`}>
              <label htmlFor={ids.pw} className={styles.label}>Password</label>
              <div className={styles.inputWrap}>
                <span className={styles.icon} aria-hidden="true"><svg viewBox="0 0 24 24" width="22" height="22" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="5" y="11" width="14" height="10" rx="3" /><path d="M8 11V8a4 4 0 0 1 8 0v3" /></svg></span>
                <input ref={pwRef} id={ids.pw} type={show ? "text" : "password"} autoComplete="current-password" className={`${styles.input} ${styles.hasToggle}`}
                  value={password} onChange={(e) => setPassword(e.target.value)} onFocus={keepVisible}
                  onKeyUp={(e) => setCapsOn(e.getModifierState?.("CapsLock") ?? false)} onBlur={() => setCapsOn(false)}
                  aria-invalid={!!errors.password} aria-describedby={[errors.password ? ids.pwErr : "", capsOn ? `${uid}-caps` : ""].join(" ").trim() || undefined} />
                <button type="button" className={styles.toggle} onClick={() => setShow((s) => !s)} aria-pressed={show} aria-controls={ids.pw}>
                  {show ? "Hide" : "Show"}<span className={styles.srOnly}> password</span>
                </button>
              </div>
              {capsOn && <p id={`${uid}-caps`} className={styles.hint}>Caps Lock is on.</p>}
              {errors.password && <p id={ids.pwErr} role="alert" className={styles.error}>{errors.password}</p>}
            </div>

            <div className={styles.row}>
              <label className={styles.check}>
                <input type="checkbox" checked={remember} onChange={(e) => setRemember(e.target.checked)} />
                <span className={styles.box} aria-hidden="true" />
                <span>Remember my email<small>Only on this device. Never your password.</small></span>
              </label>
              <Link href={forgotPasswordHref} className={styles.link}>Forgot password?</Link>
            </div>

            <button type="submit" className={styles.submit} disabled={busy} aria-busy={busy}>
              {busy ? (<><span className={styles.spinner} aria-hidden="true" /> Signing you in…</>) : (<>Sign In <span aria-hidden="true" className={styles.arrow}>→</span></>)}
            </button>
            <p className={styles.srOnly} role="status" aria-live="polite">{busy ? "Signing in, please wait." : ""}</p>
          </form>

          <p className={styles.register}>New to Swasthya Mitra? <Link href={registerHref} className={styles.link}>Create an account</Link></p>
          <p className={styles.disclaimer}>Swasthya Mitra supports your health but does not replace a doctor. In an emergency call <a href="tel:108">108</a>.</p>
        </section>
      </main>
    </div>
  );
}
