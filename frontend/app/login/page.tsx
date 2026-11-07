"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Suspense, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { Challenge } from "@/lib/types";
import {
  biometricSupported,
  getPasskey,
  passkeyErrorText,
} from "@/lib/webauthn";

import SwasthyaLogin from "@/components/swasthya-login/SwasthyaLogin";
import { AuthShell } from "@/components/AuthShell";
import { CodeStep } from "@/components/CodeStep";
import { Banner, errMsg } from "@/components/ui";

type Step =
  | { kind: "password" }
  | { kind: "code"; ch: Challenge; signup?: boolean };

function LoginInner() {
  const router = useRouter();
  const { refresh } = useAuth();

  const [step, setStep] = useState<Step>({ kind: "password" });
  const [err, setErr] = useState<string | null>(null);
  const [canBio, setCanBio] = useState(false);

  useEffect(() => {
    setCanBio(biometricSupported());
  }, []);

  async function done() {
    await refresh();
    router.replace("/dashboard");
  }

  // Step 1: Email and password authentication
  async function signIn(values: {
    email: string;
    password: string;
    remember: boolean;
  }) {
    try {
      const ch = await api<Challenge>("/auth/login", {
        body: {
          email: values.email,
          password: values.password,
        },
      });

      return {
        ok: "challenge" as const,
        challenge: ch,
      };
    } catch (er) {
      if (er instanceof ApiError && er.status === 403) {
        const d = er.detail as { code?: string } & Challenge;

        if (d?.code === "verification_required") {
          return {
            ok: "challenge" as const,
            challenge: d,
            signup: true,
          };
        }
      }

      return {
        ok: false as const,
        message: errMsg(er),
      };
    }
  }

  // Step 2: Biometric/passkey authentication
  async function biometric(ch: Challenge) {
    setErr(null);

    try {
      const options = await api<Record<string, unknown>>(
        "/auth/webauthn/login/options",
        {
          body: { challenge_id: ch.challenge_id },
        }
      );

      const credential = await getPasskey(options);

      await api("/auth/webauthn/login/verify", {
        body: {
          challenge_id: ch.challenge_id,
          credential,
        },
      });

      await done();
    } catch (er) {
      setErr(
        er instanceof ApiError
          ? er.message
          : passkeyErrorText(er)
      );
    }
  }

  // Password/login screen
  if (step.kind === "password") {
    return (
      <SwasthyaLogin
        onSignIn={signIn}
        onChallenge={(ch, signup) => {
          setErr(null);
          setStep({
            kind: "code",
            ch,
            signup,
          });
        }}
        registerHref="/register"
        forgotPasswordHref="/forgot-password"
      />
    );
  }

  // OTP and biometric verification screen
  const ch = step.ch;
  const bio =
    !step.signup &&
    canBio &&
    ch.methods?.includes("biometric");

  return (
    <AuthShell
      title={
        step.signup
          ? "Confirm your account"
          : "Step 2 of 2: enter your code"
      }
      intro={
        step.signup
          ? "Your account is not confirmed yet."
          : "This second step keeps your health records safe."
      }
      footer={
        <button
          type="button"
          className="font-bold text-brand underline"
          onClick={() => {
            setStep({ kind: "password" });
            setErr(null);
          }}
        >
          ← Back
        </button>
      }
    >
      {err && (
        <div className="mb-4">
          <Banner tone="error">{err}</Banner>
        </div>
      )}

      {bio && !ch.otp_sent ? (
        <div className="space-y-4">
          <button
            className="btn-primary w-full"
            onClick={() => biometric(ch)}
          >
            Use fingerprint or face
          </button>

          <button
            className="btn-quiet w-full"
            onClick={async () => {
              try {
                const st = await api<Challenge>("/auth/mfa/send", {
                  body: {
                    challenge_id: ch.challenge_id,
                  },
                });

                setStep({
                  kind: "code",
                  ch: { ...ch, ...st },
                });

                setErr(null);
              } catch (er) {
                setErr(errMsg(er));
              }
            }}
          >
            Send me a code instead
          </button>
        </div>
      ) : (
        <CodeStep
          ch={ch}
          submitLabel={
            step.signup ? "Confirm and continue" : "Log in"
          }
          onSubmit={async (code, id) => {
            await api(
              step.signup
                ? "/auth/register/verify"
                : "/auth/mfa/verify",
              {
                body: {
                  challenge_id: id,
                  code,
                },
              }
            );

            await done();
          }}
          extra={
            bio ? (
              <button
                type="button"
                className="btn-quiet w-full"
                onClick={() => biometric(ch)}
              >
                Use fingerprint or face instead
              </button>
            ) : undefined
          }
        />
      )}
    </AuthShell>
  );
}

export default function Login() {
  return (
    <Suspense>
      <LoginInner />
    </Suspense>
  );
}