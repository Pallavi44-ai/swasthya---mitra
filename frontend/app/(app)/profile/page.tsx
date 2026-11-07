"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { Contact, Profile } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Banner, Empty, Field, PageHeader, Spinner, errMsg, useToast } from "@/components/ui";

const parseList = (s: string) => s.split(/[,\n]/).map((x) => x.trim()).filter(Boolean);

export default function ProfilePage() {
  const toast = useToast();
  const [p, setP] = useState<Profile | null>(null);
  const [allergies, setAllergies] = useState(""); const [conditions, setConditions] = useState("");
  const [contacts, setContacts] = useState<Contact[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [errs, setErrs] = useState<string | null>(null);

  const loadContacts = () => api<Contact[]>("/contacts").then(setContacts).catch((e) => toast(errMsg(e), "error"));
  useEffect(() => {
    api<Profile>("/profile").then((x) => { setP(x); setAllergies(x.allergies.join(", ")); setConditions(x.conditions.join(", ")); }).catch((e) => setErrs(errMsg(e)));
    void loadContacts();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  async function save(e: React.FormEvent) {
    e.preventDefault(); if (!p) return; setSaving(true); setErrs(null);
    try {
      const body = { date_of_birth: p.date_of_birth || null, sex: p.sex || null, blood_group: p.blood_group || null, height_cm: p.height_cm || null, weight_kg: p.weight_kg || null, allergies: parseList(allergies), conditions: parseList(conditions), notes: p.notes || null };
      const r = await api<Profile>("/profile", { method: "PUT", body }); setP(r); toast("Health profile saved.");
    } catch (er) { setErrs(errMsg(er)); } finally { setSaving(false); }
  }
  if (!p) return errs ? <Banner tone="error">{errs}</Banner> : <Spinner />;
  const up = <K extends keyof Profile>(k: K, v: Profile[K]) => setP({ ...p, [k]: v });

  return (
    <div className="space-y-10">
      <PageHeader title="My health" intro="This helps me personalise answers and check new prescriptions against your allergies. It is only used for personalisation if you allow it on the Privacy page." />
      <form onSubmit={save} className="panel space-y-5">
        {errs && <Banner tone="error">{errs}</Banner>}
        <div className="grid gap-5 sm:grid-cols-2">
          <Field label="Date of birth" htmlFor="dob"><input id="dob" type="date" className="field" value={p.date_of_birth ?? ""} max={new Date().toISOString().slice(0, 10)} onChange={(e) => up("date_of_birth", e.target.value)} /></Field>
          <Field label="Sex" htmlFor="sex"><select id="sex" className="field" value={p.sex ?? ""} onChange={(e) => up("sex", (e.target.value || null) as Profile["sex"])}><option value="">Prefer not to say</option><option value="female">Female</option><option value="male">Male</option><option value="other">Other</option></select></Field>
          <Field label="Blood group" htmlFor="bg"><select id="bg" className="field" value={p.blood_group ?? ""} onChange={(e) => up("blood_group", e.target.value || null)}><option value="">Not sure</option>{["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"].map((b) => <option key={b}>{b}</option>)}</select></Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label="Height (cm)" htmlFor="h"><input id="h" type="number" inputMode="decimal" className="field" value={p.height_cm ?? ""} onChange={(e) => up("height_cm", e.target.value ? Number(e.target.value) : null)} /></Field>
            <Field label="Weight (kg)" htmlFor="w"><input id="w" type="number" inputMode="decimal" className="field" value={p.weight_kg ?? ""} onChange={(e) => up("weight_kg", e.target.value ? Number(e.target.value) : null)} /></Field>
          </div>
        </div>
        <Field label="Allergies" htmlFor="al" hint="Separate with commas, for example: penicillin, dust"><textarea id="al" rows={2} className="field" value={allergies} onChange={(e) => setAllergies(e.target.value)} /></Field>
        <Field label="Long-term conditions" htmlFor="co" hint="For example: diabetes, high blood pressure"><textarea id="co" rows={2} className="field" value={conditions} onChange={(e) => setConditions(e.target.value)} /></Field>
        <Field label="Other notes" htmlFor="no"><textarea id="no" rows={3} className="field" maxLength={2000} value={p.notes ?? ""} onChange={(e) => up("notes", e.target.value)} /></Field>
        <button className="btn-primary" disabled={saving}>{saving ? "Saving…" : "Save health profile"}</button>
      </form>

      <section aria-labelledby="ec">
        <h2 id="ec" className="mb-1 text-xl font-bold">Emergency contacts</h2>
        <p className="mb-4 text-muted">People the emergency screen can call or message for you. Up to 5.</p>
        <ContactForm onSaved={loadContacts} />
        {contacts === null ? <Spinner /> : contacts.length === 0 ? <div className="mt-4"><Empty title="No emergency contacts yet">Add a family member or neighbour above.</Empty></div> : (
          <ul className="mt-4 space-y-3">{contacts.map((c) => (
            <li key={c.id} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-surface p-4">
              <div className="min-w-[10rem] flex-1"><p className="font-bold">{c.name}{c.is_primary && <span className="ml-2 rounded-full bg-brand-tint px-2 py-0.5 text-sm text-brand">Main contact</span>}</p><p className="text-muted">{c.phone}{c.relationship ? ` · ${c.relationship}` : ""}</p></div>
              <a className="btn-quiet !min-h-[44px]" href={`tel:${c.phone}`}><Icon name="phone" className="h-5 w-5" /> Call</a>
              <button className="btn-quiet !min-h-[44px] text-sos" onClick={async () => { try { await api(`/contacts/${c.id}`, { method: "DELETE" }); toast("Contact removed."); void loadContacts(); } catch (e) { toast(errMsg(e), "error"); } }}>Remove</button>
            </li>))}</ul>)}
      </section>
    </div>
  );
}

function ContactForm({ onSaved }: { onSaved: () => void }) {
  const toast = useToast();
  const [f, setF] = useState({ name: "", phone: "", relationship: "" });
  const [err, setErr] = useState<string | null>(null);
  async function add(e: React.FormEvent) { e.preventDefault(); setErr(null); try { await api("/contacts", { body: { ...f, relationship: f.relationship || null } }); setF({ name: "", phone: "", relationship: "" }); toast("Contact added."); onSaved(); } catch (er) { setErr(errMsg(er)); } }
  return (
    <form onSubmit={add} className="panel space-y-4">
      {err && <Banner tone="error">{err}</Banner>}
      <div className="grid gap-4 sm:grid-cols-3">
        <Field label="Name" htmlFor="cn"><input id="cn" required className="field" value={f.name} onChange={(e) => setF({ ...f, name: e.target.value })} /></Field>
        <Field label="Phone number" htmlFor="cp"><input id="cp" required type="tel" inputMode="tel" className="field" value={f.phone} onChange={(e) => setF({ ...f, phone: e.target.value })} /></Field>
        <Field label="Relationship" htmlFor="cr"><input id="cr" className="field" placeholder="Son, neighbour…" value={f.relationship} onChange={(e) => setF({ ...f, relationship: e.target.value })} /></Field>
      </div>
      <button className="btn-primary">Add contact</button>
    </form>
  );
}
