"use client";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { api } from "@/lib/api";
import { shrinkImage } from "@/lib/rxText";
import type { Prescription, RxImpact } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Banner, Empty, PageHeader, Spinner, errMsg, useToast } from "@/components/ui";

const STATUS: Record<string, { text: string; cls: string }> = {
  extracted: { text: "Needs your review", cls: "bg-saffron-tint text-saffron-ink" },
  confirmed: { text: "Confirmed", cls: "bg-ok-tint text-ok" },
  failed: { text: "Could not read", cls: "bg-sos-tint text-sos" },
};

const ALLOWED = ["image/jpeg", "image/png", "image/webp"];
const MAX_ORIGINAL_MB = 25; // the photo is shrunk before upload; the server then allows up to 8 MB

export default function Prescriptions() {
  const router = useRouter();
  const [list, setList] = useState<Prescription[] | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [removing, setRemoving] = useState<Prescription | null>(null);
  const toast = useToast();
  const cameraRef = useRef<HTMLInputElement>(null);
  const galleryRef = useRef<HTMLInputElement>(null);

  useEffect(() => { api<Prescription[]>("/prescriptions").then(setList).catch((e) => { setError(errMsg(e)); setList([]); }); }, []);
  useEffect(() => () => { if (previewUrl) URL.revokeObjectURL(previewUrl); }, [previewUrl]); // free the preview when it changes or the page closes

  function choose(f: File | undefined) {
    setError(null);
    if (cameraRef.current) cameraRef.current.value = "";
    if (galleryRef.current) galleryRef.current.value = "";
    if (!f) return;
    if (!ALLOWED.includes(f.type)) { setError("This file type is not supported. Please use a JPG, PNG or WEBP photo."); return; }
    if (f.size > MAX_ORIGINAL_MB * 1024 * 1024) { setError(`This photo is too large (over ${MAX_ORIGINAL_MB} MB). Please take a new photo or choose a smaller one.`); return; }
    if (f.size === 0) { setError("This file is empty. Please choose another photo."); return; }
    setFile(f);
    setPreviewUrl(URL.createObjectURL(f));
  }

  function clearChoice() { setFile(null); setPreviewUrl(null); setError(null); }

  async function analyze() {
    if (!file || busy) return;
    setBusy(true); setError(null);
    try {
      const small = await shrinkImage(file);
      const form = new FormData(); form.append("file", small);
      const p = await api<Prescription>("/prescriptions", { form });
      router.push(`/prescriptions/${p.id}`);
    } catch (e) { setError(errMsg(e)); setBusy(false); }
  }

  return (
    <div className="space-y-8">
      <PageHeader title="Prescriptions" intro="Take a clear photo of your prescription. I will read it and show what I found. Nothing is used until you check and confirm every medicine." />
      <section className="rounded-2xl border-2 border-brand bg-brand-tint p-6 sm:p-8" aria-labelledby="scan-h">
        <h2 id="scan-h" className="text-xl font-bold">Read a new prescription</h2>
        {!file && (
          <ol className="mt-3 list-decimal space-y-1 pl-6">
            <li>Put the prescription flat in good light.</li><li>Take the photo straight from above.</li><li>Look at the photo, then tap “Read this prescription”.</li><li>Check the medicines I found and fix any mistakes.</li>
          </ol>
        )}
        <input ref={cameraRef} id="rx-camera" type="file" accept="image/jpeg,image/png,image/webp" capture="environment" className="sr-only" onChange={(e) => choose(e.target.files?.[0])} />
        <input ref={galleryRef} id="rx-gallery" type="file" accept="image/jpeg,image/png,image/webp" className="sr-only" onChange={(e) => choose(e.target.files?.[0])} />

        {previewUrl && file ? (
          <div className="mt-5 space-y-4">
            <p className="font-bold">Is the whole prescription visible and easy to read?</p>
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img src={previewUrl} alt="Preview of the prescription photo you chose" className="max-h-[28rem] w-full max-w-xl rounded-xl border-2 border-line bg-surface object-contain" />
            <p className="text-sm text-muted">{file.name} · {(file.size / 1024 / 1024).toFixed(1)} MB</p>
            <div className="flex flex-wrap gap-3">
              <button type="button" className="btn-primary !min-h-[60px] text-lg" onClick={analyze} disabled={busy}><Icon name="check" /> Read this prescription</button>
              <button type="button" className="btn-quiet !min-h-[60px]" onClick={clearChoice} disabled={busy}>Choose a different photo</button>
            </div>
          </div>
        ) : (
          <div className="mt-5 flex flex-wrap gap-3">
            <label htmlFor="rx-camera" className="btn-primary cursor-pointer !min-h-[60px] text-lg"><Icon name="camera" /> Take a photo</label>
            <label htmlFor="rx-gallery" className="btn-quiet cursor-pointer !min-h-[60px] text-lg"><Icon name="file" /> Choose a photo from my phone</label>
          </div>
        )}
        <p className="mt-4 text-sm text-muted">JPG, PNG or WEBP photos only. Your photo is only kept if you allowed it in Privacy.</p>
        {busy && <div role="status" aria-live="polite"><Spinner label="Reading your prescription. I am straightening the photo, reading the writing and checking it. This can take up to a minute." /></div>}
        {error && <div className="mt-4"><Banner tone="error" title="Could not read the image">{error}</Banner></div>}
      </section>

      <section aria-labelledby="past">
        <h2 id="past" className="mb-3 text-xl font-bold">Your prescriptions</h2>
        {list === null ? <Spinner /> : list.length === 0 ? <Empty title="No prescriptions yet">When you scan one it will appear here with its status.</Empty> : (
          <ul className="space-y-3">
            {list.map((p) => {
              const title = p.items.length ? p.items.map((i) => i.medicine_name).filter(Boolean).slice(0, 3).join(", ") + (p.items.length > 3 ? "…" : "") : "No medicines found";
              return (
                <li key={p.id} className="relative">
                  <Link href={`/prescriptions/${p.id}`} className="flex flex-wrap items-center gap-3 rounded-2xl border border-line bg-surface p-4 pr-14 hover:border-brand">
                    <div className="min-w-0 flex-1"><p className="font-bold">{title}</p>
                      <p className="text-sm text-muted">{new Date(p.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}{p.doctor_name ? ` · ${p.doctor_name}` : ""}</p></div>
                    <span className={`rounded-full px-4 py-1 text-sm font-bold ${STATUS[p.status]?.cls}`}>{STATUS[p.status]?.text ?? p.status}</span>
                  </Link>
                  <button type="button" onClick={() => setRemoving(p)} aria-label={`Remove prescription: ${title}`} title="Remove"
                    className="absolute right-1.5 top-1.5 grid h-11 w-11 place-items-center rounded-full text-muted transition-colors hover:bg-brand-tint hover:text-ink">
                    <Icon name="x" className="h-5 w-5" />
                  </button>
                </li>);
            })}
          </ul>)}
      </section>
      {removing && <RemoveDialog rx={removing} onCancel={() => setRemoving(null)} onRemoved={(id) => { setList((l) => (l ?? []).filter((x) => x.id !== id)); setRemoving(null); toast("Prescription removed."); }} />}
    </div>
  );
}

/** "Do you want to remove this prescription?" – nothing is deleted until the user presses Remove. Cancel is focused first. */
function RemoveDialog({ rx, onCancel, onRemoved }: { rx: Prescription; onCancel: () => void; onRemoved: (id: string) => void }) {
  const [impact, setImpact] = useState<RxImpact | null>(null);
  const [impactFailed, setImpactFailed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const cancelRef = useRef<HTMLButtonElement>(null);
  const removeRef = useRef<HTMLButtonElement>(null);
  const opener = useRef<Element | null>(null);

  useEffect(() => {
    opener.current = document.activeElement;
    cancelRef.current?.focus();
    api<RxImpact>(`/prescriptions/${rx.id}/impact`).then(setImpact).catch(() => setImpactFailed(true));
    return () => { (opener.current as HTMLElement | null)?.focus?.(); };
  }, [rx.id]);

  function onKey(e: React.KeyboardEvent) {
    if (e.key === "Escape" && !busy) { e.stopPropagation(); onCancel(); return; }
    if (e.key === "Tab") { // keep keyboard focus inside the dialog
      const first = cancelRef.current, last = removeRef.current?.disabled ? cancelRef.current : removeRef.current;
      if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last?.focus(); }
      else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first?.focus(); }
    }
  }

  async function remove() {
    setBusy(true); setError(null);
    try { await api(`/prescriptions/${rx.id}`, { method: "DELETE" }); onRemoved(rx.id); }
    catch (e) { setError(errMsg(e)); setBusy(false); }
  }

  const name = rx.items.map((i) => i.medicine_name).filter(Boolean).slice(0, 3).join(", ") || "this prescription";
  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-black/40 p-4" onKeyDown={onKey} onMouseDown={(e) => { if (e.target === e.currentTarget && !busy) onCancel(); }}>
      <div role="alertdialog" aria-modal="true" aria-labelledby="rm-title" aria-describedby="rm-body" className="w-full max-w-md rounded-2xl border border-line bg-surface p-6 shadow-xl">
        <h2 id="rm-title" className="text-xl font-bold">Do you want to remove this prescription?</h2>
        <div id="rm-body" className="mt-3 space-y-2">
          <p className="font-bold">{name}</p>
          {!impact && !impactFailed && <p className="text-muted">Checking what is linked to it…</p>}
          {impactFailed && <p className="text-muted">I could not check what is linked to it. If it has reminders, they will be removed too.</p>}
          {impact && (
            <ul className="list-disc space-y-1 pl-6">
              <li>{impact.reminders > 0
                ? `${impact.reminders} reminder${impact.reminders === 1 ? "" : "s"} made from it will also be removed${impact.doses_logged > 0 ? `, with your record of ${impact.doses_logged} dose${impact.doses_logged === 1 ? "" : "s"} you marked. Your 7-day summary will change` : ""}.`
                : "No reminders are linked to it."}</li>
              {impact.in_timeline && <li>It will also disappear from your health timeline.</li>}
              {impact.has_photo && <li>The saved photo will be deleted.</li>}
              <li>Your other prescriptions and your health records are not affected.</li>
            </ul>)}
          <p className="text-sm text-muted">This cannot be undone.</p>
        </div>
        {error && <div className="mt-3"><Banner tone="error" title="Could not remove it">{error}</Banner></div>}
        <div className="mt-5 flex flex-wrap justify-end gap-3">
          <button ref={cancelRef} type="button" className="btn-quiet" onClick={onCancel} disabled={busy}>Cancel</button>
          <button ref={removeRef} type="button" className="btn-danger" onClick={remove} disabled={busy}>{busy ? "Removing…" : "Remove"}</button>
        </div>
      </div>
    </div>
  );
}
