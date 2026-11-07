"use client";
import Link from "next/link";
import type { ReactNode } from "react";
import { usePrefs } from "@/lib/prefs";
import { Icon } from "./Icon";

/** Common frame for the sign-in pages: big heading, one short instruction, text-size button for elderly users. */
export function AuthShell({ title, intro, children, footer }: { title: string; intro?: string; children: ReactNode; footer?: ReactNode }) {
  const { scale, setScale } = usePrefs();
  return (
    <main className="mx-auto max-w-lg px-5 py-8 sm:py-12">
      <div className="mb-6 flex items-center justify-between gap-3">
        <Link href="/" className="flex items-center gap-2 font-bold text-brand"><Icon name="heart" /> Swasthya Mitra</Link>
        <button type="button" className="btn-quiet !min-h-[44px] !px-4" onClick={() => setScale(scale >= 1.3 ? 1 : scale + 0.15)}>A+ Bigger text</button>
      </div>
      <h1 className="text-3xl font-bold">{title}</h1>
      {intro && <p className="mt-2 text-lg text-muted">{intro}</p>}
      <div className="mt-6">{children}</div>
      {footer && <div className="mt-6 space-y-2 text-lg">{footer}</div>}
    </main>
  );
}
