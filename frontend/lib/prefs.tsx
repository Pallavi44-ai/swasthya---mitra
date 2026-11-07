"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import type { Lang } from "./types";

interface Prefs { lang: Lang; setLang: (l: Lang) => void; scale: number; setScale: (s: number) => void; contrast: boolean; setContrast: (c: boolean) => void }
const Ctx = createContext<Prefs | null>(null);

const read = (k: string): string | null => { try { return localStorage.getItem(k); } catch { return null; } };
const write = (k: string, v: string) => { try { localStorage.setItem(k, v); } catch { /* private mode */ } };

export function PrefsProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>("en");
  const [scale, setScaleState] = useState(1);
  const [contrast, setContrastState] = useState(false);

  useEffect(() => {
    const l = read("sm_lang") as Lang | null; if (l && ["en", "hi", "kn", "te"].includes(l)) setLangState(l);
    const s = parseFloat(read("sm_scale") ?? ""); if (s >= 1 && s <= 1.5) setScaleState(s);
    setContrastState(read("sm_contrast") === "1");
  }, []);
  useEffect(() => {
    document.documentElement.style.setProperty("--scale", String(scale));
    document.documentElement.dataset.contrast = contrast ? "high" : "normal";
    document.documentElement.lang = lang;
  }, [scale, contrast, lang]);

  const setLang = useCallback((l: Lang) => { setLangState(l); write("sm_lang", l); }, []);
  const setScale = useCallback((s: number) => { setScaleState(s); write("sm_scale", String(s)); }, []);
  const setContrast = useCallback((c: boolean) => { setContrastState(c); write("sm_contrast", c ? "1" : "0"); }, []);
  return <Ctx.Provider value={{ lang, setLang, scale, setScale, contrast, setContrast }}>{children}</Ctx.Provider>;
}
export const usePrefs = () => { const c = useContext(Ctx); if (!c) throw new Error("PrefsProvider missing"); return c; };
