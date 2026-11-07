"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { speak } from "@/lib/speech";
import { t } from "@/lib/i18n";
import type { Dose } from "@/lib/types";
import { Icon } from "./Icon";
import { useToast } from "./ui";

/** Polls for due doses every 30 s while the app is open: on-screen prompt + spoken prompt + browser notification. */
export function DueDoseNotifier() {
  const { lang } = usePrefs();
  const toast = useToast();
  const [due, setDue] = useState<Dose[]>([]);
  const announced = useRef<Set<string>>(new Set());

  const poll = useCallback(async () => {
    try {
      const d = await api<Dose[]>("/reminders/due");
      setDue(d);
      for (const dose of d) {
        if (announced.current.has(dose.id)) continue;
        announced.current.add(dose.id);
        const msg = `${t("timeToTake", lang)}: ${dose.medicine_name} ${dose.strength ?? ""}`.trim();
        speak(msg, lang);
        try { if ("Notification" in window && Notification.permission === "granted") new Notification("Swasthya Mitra", { body: msg, tag: dose.id }); } catch { /* unsupported */ }
      }
    } catch { /* offline or logged out – ignore, will retry */ }
  }, [lang]);

  useEffect(() => { void poll(); const id = setInterval(poll, 30000); return () => clearInterval(id); }, [poll]);

  async function mark(d: Dose, status: "taken" | "skipped") {
    try { await api(`/reminders/doses/${d.id}`, { body: { status } }); setDue((s) => s.filter((x) => x.id !== d.id)); toast(status === "taken" ? `${d.medicine_name}: ${t("taken", lang)}` : `${d.medicine_name}: ${t("skip", lang)}`); }
    catch (e) { toast((e as Error).message, "error"); }
  }
  if (!due.length) return null;
  const d = due[0];
  return (
    <div role="alertdialog" aria-label={t("timeToTake", lang)} className="fixed inset-x-3 top-3 z-50 mx-auto max-w-xl rounded-2xl border-4 border-saffron bg-saffron-tint p-5 shadow-2xl">
      <div className="flex items-start gap-3">
        <Icon name="pill" className="mt-1 h-8 w-8 text-saffron-ink" />
        <div className="min-w-0 flex-1">
          <p className="font-bold text-saffron-ink">{t("timeToTake", lang)}{due.length > 1 && ` (+${due.length - 1})`}</p>
          <p className="text-xl font-bold">{d.medicine_name} {d.strength}</p>
          <p className="text-muted">{d.dosage_instruction} · {d.local_time}</p>
        </div>
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <button className="btn-primary" onClick={() => mark(d, "taken")}>{t("taken", lang)}</button>
        <button className="btn-quiet" onClick={() => mark(d, "skipped")}>{t("skip", lang)}</button>
      </div>
    </div>
  );
}
