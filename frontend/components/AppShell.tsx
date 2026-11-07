"use client";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";
import { useAuth } from "@/lib/auth";
import { usePrefs } from "@/lib/prefs";
import { LANGS, t, type TKey } from "@/lib/i18n";
import type { Lang } from "@/lib/types";
import { Icon } from "./Icon";
import { Spinner } from "./ui";
import { DueDoseNotifier } from "./DueDoseNotifier";

const NAV: { href: string; key: TKey; icon: string; tab?: boolean }[] = [
  { href: "/dashboard", key: "home", icon: "home", tab: true },
  { href: "/chat", key: "chat", icon: "chat", tab: true },
  { href: "/prescriptions", key: "medicines", icon: "pill", tab: true },
  { href: "/reminders", key: "reminders", icon: "bell", tab: true },
  { href: "/profile", key: "profile", icon: "heart", tab: true },
  { href: "/records", key: "records", icon: "file" },
  { href: "/privacy", key: "privacy", icon: "shield" },
  { href: "/security", key: "security", icon: "lock" },
  { href: "/status", key: "status", icon: "gear" },
];

export function AppShell({ children }: { children: ReactNode }) {
  const { user, loading, logout } = useAuth();
  const { lang, setLang, scale, setScale, contrast, setContrast } = usePrefs();
  const path = usePathname();
  const router = useRouter();
  const [menu, setMenu] = useState(false);

  useEffect(() => { if (!loading && !user) router.replace("/login"); }, [loading, user, router]);
  useEffect(() => setMenu(false), [path]);
  useEffect(() => { try { if ("Notification" in window && Notification.permission === "default") { /* asked from Reminders page on user action */ } } catch { /* noop */ } }, []);

  if (loading || !user) return <div className="mx-auto max-w-md p-8"><Spinner label="Checking your session" /></div>;

  const link = (n: (typeof NAV)[number], cls: string) => (
    <Link key={n.href} href={n.href} aria-current={path.startsWith(n.href) ? "page" : undefined}
      className={`${cls} ${path.startsWith(n.href) ? "bg-brand text-white" : "text-ink hover:bg-brand-tint"}`}>
      <Icon name={n.icon} /> <span>{t(n.key, lang)}</span>
    </Link>
  );

  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[17rem_1fr]">
      <a href="#main" className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-lg focus:bg-white focus:p-3">Skip to content</a>
      <DueDoseNotifier />

      {/* Desktop rail */}
      <aside className="hidden border-r border-line bg-surface lg:flex lg:flex-col lg:gap-1 lg:p-4" aria-label="Main">
        <Link href="/dashboard" className="mb-4 flex items-center gap-3 px-2 py-2">
          <span className="grid h-11 w-11 place-items-center rounded-xl bg-brand text-white"><Icon name="heart" /></span>
          <span className="text-xl font-bold leading-tight">Swasthya<br />Mitra</span>
        </Link>
        <nav className="flex flex-col gap-1">{NAV.map((n) => link(n, "flex min-h-[52px] items-center gap-3 rounded-xl px-4 text-base font-bold"))}</nav>
        <div className="mt-auto space-y-3 border-t border-line pt-4">
          <p className="px-2 text-sm text-muted">{user.full_name}</p>
          <button className="btn-quiet w-full" onClick={logout}><Icon name="logout" /> {t("logout", lang)}</button>
        </div>
      </aside>

      <div className="flex min-w-0 flex-col">
        {/* Top bar: language + accessibility controls */}
        <div className="sticky top-0 z-30 flex flex-wrap items-center gap-2 border-b border-line bg-surface/95 px-3 py-2 backdrop-blur sm:px-6">
          <button className="btn-quiet !min-h-[48px] !px-3 lg:hidden" aria-expanded={menu} aria-controls="mobile-menu" onClick={() => setMenu(!menu)}>
            <Icon name={menu ? "x" : "menu"} /> <span className="sr-only">Menu</span>
          </button>
          <span className="mr-auto sm:hidden" /><span className="mr-auto hidden text-sm text-muted sm:inline sm:text-base">{t("notDoctor", lang)}</span>
          <label className="sr-only" htmlFor="lang">{t("language", lang)}</label>
          <select id="lang" className="field !min-h-[48px] !w-auto !py-1" value={lang} onChange={(e) => setLang(e.target.value as Lang)}>
            {LANGS.map((l) => <option key={l.code} value={l.code}>{l.native}</option>)}
          </select>
          <div role="group" aria-label={t("textSize", lang)} className="flex overflow-hidden rounded-xl border-2 border-line">
            {[1, 1.15, 1.3].map((s, i) => (
              <button key={s} onClick={() => setScale(s)} aria-pressed={scale === s} aria-label={`${t("textSize", lang)} ${i + 1}`}
                className={`min-h-[44px] min-w-[44px] font-bold ${scale === s ? "bg-brand text-white" : "bg-surface"}`} style={{ fontSize: 14 + i * 4 }}>A</button>
            ))}
          </div>
          <button className="btn-quiet !min-h-[48px] !px-3 !text-sm" aria-pressed={contrast} onClick={() => setContrast(!contrast)}>{t("contrast", lang)}</button>
        </div>

        {menu && (
          <nav id="mobile-menu" className="grid gap-1 border-b border-line bg-surface p-3 lg:hidden" aria-label="Menu">
            {NAV.map((n) => link(n, "flex min-h-[52px] items-center gap-3 rounded-xl px-4 text-base font-bold"))}
            <button className="btn-quiet mt-2" onClick={logout}><Icon name="logout" /> {t("logout", lang)}</button>
          </nav>
        )}

        <main id="main" className="mx-auto w-full max-w-5xl flex-1 px-4 pb-40 pt-6 sm:px-6 lg:pb-16">{children}</main>

        {/* Mobile tab bar */}
        <nav className="fixed inset-x-0 bottom-0 z-30 grid grid-cols-5 border-t border-line bg-surface lg:hidden" aria-label="Quick">
          {NAV.filter((n) => n.tab).map((n) => (
            <Link key={n.href} href={n.href} aria-current={path.startsWith(n.href) ? "page" : undefined}
              className={`flex min-h-[64px] flex-col items-center justify-center gap-0.5 text-[11px] font-bold ${path.startsWith(n.href) ? "text-brand" : "text-muted"}`}>
              <Icon name={n.icon} /><span className="max-w-full px-0.5">{t(n.key, lang)}</span>
            </Link>
          ))}
        </nav>

        {/* Always-visible emergency button */}
        <Link href="/emergency" className="fixed bottom-20 right-3 z-40 flex min-h-[56px] items-center gap-2 rounded-full bg-sos px-5 text-lg font-bold text-white shadow-xl hover:bg-sos-dark lg:bottom-6 lg:right-6">
          <Icon name="phone" /> {t("sos", lang)}
        </Link>
      </div>
    </div>
  );
}
