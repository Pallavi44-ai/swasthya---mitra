"use client";
import type { ReactNode } from "react";
import { PrefsProvider } from "@/lib/prefs";
import { AuthProvider } from "@/lib/auth";
import { ToastProvider } from "./ui";

export function Providers({ children }: { children: ReactNode }) {
  return <PrefsProvider><ToastProvider><AuthProvider>{children}</AuthProvider></ToastProvider></PrefsProvider>;
}
