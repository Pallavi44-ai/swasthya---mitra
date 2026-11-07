"use client";
import { createContext, useCallback, useContext, useState, type ReactNode } from "react";

export function Spinner({ label = "Loading" }: { label?: string }) {
  return (
    <div role="status" className="flex items-center gap-3 py-6 text-muted">
      <span className="spinner inline-block h-6 w-6 rounded-full border-4 border-line border-t-brand" aria-hidden />
      <span>{label}…</span>
    </div>
  );
}

export function Banner({ tone = "info", title, children, role }: { tone?: "info" | "warn" | "error" | "ok"; title?: string; children?: ReactNode; role?: string }) {
  const cls = { info: "bg-brand-tint border-brand", warn: "bg-saffron-tint border-saffron", error: "bg-sos-tint border-sos", ok: "bg-ok-tint border-ok" }[tone];
  return (
    <div role={role ?? (tone === "error" ? "alert" : "status")} className={`rounded-xl border-l-8 p-4 ${cls}`}>
      {title && <p className="font-bold">{title}</p>}
      {children && <div className={title ? "mt-1" : ""}>{children}</div>}
    </div>
  );
}

export function Empty({ title, children, action }: { title: string; children?: ReactNode; action?: ReactNode }) {
  return (
    <div className="rounded-2xl border-2 border-dashed border-line p-8 text-center">
      <p className="text-lg font-bold">{title}</p>
      {children && <p className="mx-auto mt-2 max-w-prose text-muted">{children}</p>}
      {action && <div className="mt-5 flex justify-center">{action}</div>}
    </div>
  );
}

export function Field({ label, hint, error, children, htmlFor }: { label: string; hint?: string; error?: string | null; children: ReactNode; htmlFor: string }) {
  return (
    <div>
      <label htmlFor={htmlFor} className="label">{label}</label>
      {children}
      {hint && !error && <p className="mt-1 text-sm text-muted">{hint}</p>}
      {error && <p role="alert" className="mt-1 text-sm font-bold text-sos">{error}</p>}
    </div>
  );
}

/* Toasts: success / error notifications */
interface Toast { id: number; tone: "ok" | "error"; text: string }
const ToastCtx = createContext<(text: string, tone?: "ok" | "error") => void>(() => {});
export const useToast = () => useContext(ToastCtx);
export function ToastProvider({ children }: { children: ReactNode }) {
  const [items, setItems] = useState<Toast[]>([]);
  const push = useCallback((text: string, tone: "ok" | "error" = "ok") => {
    const id = Date.now() + Math.random();
    setItems((s) => [...s, { id, tone, text }]);
    setTimeout(() => setItems((s) => s.filter((x) => x.id !== id)), tone === "error" ? 8000 : 4500);
  }, []);
  return (
    <ToastCtx.Provider value={push}>
      {children}
      <div className="pointer-events-none fixed inset-x-0 bottom-24 z-50 flex flex-col items-center gap-2 px-4 lg:bottom-6" aria-live="polite">
        {items.map((t) => (
          <div key={t.id} role={t.tone === "error" ? "alert" : "status"}
            className={`pointer-events-auto max-w-md rounded-xl px-5 py-3 font-bold shadow-lg ${t.tone === "ok" ? "bg-ok text-white" : "bg-sos text-white"}`}>{t.text}</div>
        ))}
      </div>
    </ToastCtx.Provider>
  );
}

export function PageHeader({ title, intro, right }: { title: string; intro?: string; right?: ReactNode }) {
  return (
    <header className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div><h1 className="text-2xl font-bold sm:text-3xl">{title}</h1>{intro && <p className="mt-1 max-w-prose text-muted">{intro}</p>}</div>
      {right}
    </header>
  );
}

export const errMsg = (e: unknown) => (e instanceof Error ? e.message : "Something went wrong. Please try again.");
