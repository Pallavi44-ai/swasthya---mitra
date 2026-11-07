"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { shrinkImage } from "@/lib/rxText";
import type { Prescription } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Banner, Empty, PageHeader, Spinner, errMsg } from "@/components/ui";

const STATUS: Record<string, { text: string; cls: string }> = {
  extracted: { text: "Needs your review", cls: "bg-saffron-tint text-saffron-ink" },
  confirmed: { text: "Confirmed", cls: "bg-ok-tint text-ok" },
  failed: { text: "Could not read", cls: "bg-sos-tint text-sos" },
};

export default function Prescriptions() {
  const router = useRouter();
  const [list, setList] = useState<Prescription[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const fileRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api<Prescription[]>("/prescriptions").then(setList).catch((e) => { setError(errMsg(e)); setList([]); }); }, []);

  async function upload(f: File | undefined) {
    if (!f) return;
    setBusy(true); setError(null);
    try {
      const small = await shrinkImage(f);
      const form = new FormData(); form.append("file", small);
      const p = await api<Prescription>("/prescriptions", { form });
      router.push(`/prescriptions/${p.id}`);
    } catch (e) { setError(errMsg(e)); setBusy(false); if (fileRef.current) fileRef.current.value = ""; }
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Prescriptions" intro="Take a clear photo of your prescription. I will read it and show what I found. Nothing is used until you check and confirm every medicine." />
      <section className="rounded-2xl border-2 border-brand bg-brand-tint p-6 sm:p-8">
        <h2 className="text-xl font-bold">Read a new prescription</h2>
        <ol className="mt-3 list-decimal space-y-1 pl-6">
          <li>Put the prescription flat in good light.</li><li>Take the photo straight from above.</li><li>Check the medicines I found and fix any mistakes.</li>
        </ol>
        <input ref={fileRef} id="rx-file" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only" onChange={(e) => upload(e.target.files?.[0])} />
        <div className="mt-5 flex flex-wrap gap-3">
          <label htmlFor="rx-file" className={`btn-primary cursor-pointer !min-h-[60px] text-lg ${busy ? "pointer-events-none opacity-60" : ""}`}><Icon name="camera" /> Take or choose a photo</label>
        </div>
        {busy && <Spinner label="Reading your prescription (this can take up to a minute)" />}
        {error && <div className="mt-4"><Banner tone="error" title="Could not read the image">{error}</Banner></div>}
      </section>

      <section aria-labelledby="past">
        <h2 id="past" className="mb-3 text-xl font-bold">Your prescriptions</h2>
        {list === null ? <Spinner /> : list.length === 0 ? <Empty title="No prescriptions yet">When you scan one it will appear here with its status.</Empty> : (
          <ul className="space-y-3">
            {list.map((p) => (
              <li key={p.id}><Link href={`/prescriptions/${p.id}`} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-surface p-4 hover:border-brand">
                <div className="min-w-0 flex-1"><p className="font-bold">{p.items.length ? p.items.map((i) => i.medicine_name).filter(Boolean).slice(0, 3).join(", ") + (p.items.length > 3 ? "…" : "") : "No medicines found"}</p>
                  <p className="text-sm text-muted">{new Date(p.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}{p.doctor_name ? ` · ${p.doctor_name}` : ""}</p></div>
                <span className={`rounded-full px-4 py-1 text-sm font-bold ${STATUS[p.status]?.cls}`}>{STATUS[p.status]?.text ?? p.status}</span>
              </Link></li>))}
          </ul>)}
      </section>
    </div>
  );
}
