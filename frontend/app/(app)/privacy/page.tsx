"use client";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { api } from "@/lib/api";
import { useAuth } from "@/lib/auth";
import type { ConsentKey, Consents } from "@/lib/types";
import { Banner, Field, PageHeader, Spinner, errMsg, useToast } from "@/components/ui";

const CONSENT_COPY: Record<ConsentKey, { title: string; text: string }> = {
  ai_processing: { title: "Use the AI service", text: "Send my questions, voice recordings and prescription photos to the AI service (Google Gemini) so I get AI answers and better prescription reading. If off, only local tools are used." },
  store_chat_history: { title: "Save my conversations", text: "Keep my chats (encrypted) so I can read them later. If off, nothing is saved." },
  health_data_personalisation: { title: "Personalise with my health details", text: "Use my profile, allergies, conditions and confirmed medicines to tailor answers." },
  store_prescription_images: { title: "Keep my prescription photos", text: "Store the photo (encrypted) so I can view it later. If off, the photo is deleted after reading." },
  emergency_sharing: { title: "Share my location in an emergency", text: "Allow adding my location to the alert message I send to my emergency contacts." },
};

export default function Privacy() {
  const { consents, setConsents, logout } = useAuth();
  const toast = useToast();
  const router = useRouter();
  const [pw, setPw] = useState("");
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function toggle(k: ConsentKey, v: boolean) {
    try { const r = await api<{ consents: Consents }>("/consents", { method: "PUT", body: { consents: { [k]: v } } }); setConsents(r.consents); toast(v ? "Allowed." : "Turned off."); } catch (e) { toast(errMsg(e), "error"); }
  }
  async function exportData() {
    try { const d = await api("/account/export"); const url = URL.createObjectURL(new Blob([JSON.stringify(d, null, 2)], { type: "application/json" })); const a = document.createElement("a"); a.href = url; a.download = "swasthya-mitra-my-data.json"; a.click(); URL.revokeObjectURL(url); toast("Your data was downloaded."); } catch (e) { toast(errMsg(e), "error"); }
  }
  async function clearChats() { if (!window.confirm("Delete all saved conversations?")) return; try { await api("/account/chat-history", { method: "DELETE" }); toast("Conversations deleted."); } catch (e) { toast(errMsg(e), "error"); } }
  async function deleteAccount(e: React.FormEvent) {
    e.preventDefault();
    try { await api("/account/delete", { body: { password: pw } }); toast("Your account and data were deleted."); router.replace("/"); } catch (er) { toast(errMsg(er), "error"); }
  }
  if (!consents) return <Spinner />;
  return (
    <div className="space-y-8">
      <PageHeader title="Privacy and consent" intro="You decide what I may use. You can change any choice at any time, and I follow it straight away." />
      <ul className="divide-y divide-line rounded-2xl border border-line bg-surface">
        {(Object.keys(CONSENT_COPY) as ConsentKey[]).map((k) => (
          <li key={k} className="flex items-start gap-4 p-5">
            <div className="flex-1"><p className="text-lg font-bold" id={`c-${k}`}>{CONSENT_COPY[k].title}</p><p className="text-muted">{CONSENT_COPY[k].text}</p></div>
            <button role="switch" aria-checked={consents[k]} aria-labelledby={`c-${k}`} onClick={() => toggle(k, !consents[k])}
              className={`relative h-10 w-[72px] shrink-0 rounded-full border-2 transition-colors ${consents[k] ? "border-brand bg-brand" : "border-line bg-line"}`}>
              <span className={`absolute top-1 grid h-7 w-7 place-items-center rounded-full bg-white text-xs font-bold text-ink transition-all ${consents[k] ? "left-[38px]" : "left-1"}`}>{consents[k] ? "On" : "Off"}</span>
            </button>
          </li>))}
      </ul>
      <section className="panel space-y-3"><h2 className="text-xl font-bold">Your data</h2>
        <div className="flex flex-wrap gap-3"><button className="btn-quiet" onClick={exportData}>Download everything I stored</button><button className="btn-quiet" onClick={clearChats}>Delete saved conversations</button></div></section>
      <section className="panel space-y-3 border-sos"><h2 className="text-xl font-bold text-sos">Delete my account</h2>
        <p className="text-muted">This permanently deletes your profile, records, prescriptions, reminders, conversations and stored photos. It cannot be undone.</p>
        {!confirmDelete ? <button className="btn-quiet text-sos" onClick={() => setConfirmDelete(true)}>I want to delete my account</button> : (
          <form onSubmit={deleteAccount} className="space-y-3"><Banner tone="error">Enter your password to confirm.</Banner>
            <Field label="Password" htmlFor="dpw"><input id="dpw" type="password" required autoComplete="current-password" className="field" value={pw} onChange={(e) => setPw(e.target.value)} /></Field>
            <div className="flex gap-3"><button className="btn-danger">Delete everything</button><button type="button" className="btn-quiet" onClick={() => setConfirmDelete(false)}>Cancel</button></div></form>)}
      </section>
      <button className="btn-quiet" onClick={logout}>Log out</button>
    </div>
  );
}
