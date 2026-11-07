"use client";
/**
 * EXAMPLE ONLY – shows how to mount the component and where your API call goes.
 * Copy the idea into your real app/login/page.tsx. Delete this preview page afterwards.
 */
import { useRouter } from "next/navigation";
import SwasthyaLogin, { type SignInResult, type SignInValues } from "@/components/swasthya-login/SwasthyaLogin";

export default function LoginPreview() {
  const router = useRouter();

  async function handleSignIn(values: SignInValues): Promise<SignInResult> {
    // ===================== API INTEGRATION POINT (placeholder) =====================
    // 1. Call YOUR existing login endpoint here with values.email / values.password.
    // 2. Return { ok: true } on success, or { ok: false, message: "..." } (optionally field: "email" | "password").
    // Example shape (replace the URL and body with whatever your API expects):
    //
    //   const res = await fetch("YOUR_LOGIN_ENDPOINT", {
    //     method: "POST",
    //     headers: { "Content-Type": "application/json" },
    //     credentials: "same-origin",
    //     body: JSON.stringify({ email: values.email, password: values.password }),
    //   });
    //   if (!res.ok) return { ok: false, message: "Incorrect email or password." };
    //   return { ok: true };
    // ================================================================================
    return { ok: false, message: "Placeholder: connect handleSignIn to your login API." };
  }

  return <SwasthyaLogin onSignIn={handleSignIn} onSuccess={() => router.replace("/dashboard")} registerHref="/register" forgotPasswordHref="/forgot-password" />;
}
