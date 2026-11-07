"use client";
import { createContext, useCallback, useContext, useEffect, useState, type ReactNode } from "react";
import { useRouter } from "next/navigation";
import { api, ApiError } from "./api";
import type { Consents, User } from "./types";
import { usePrefs } from "./prefs";

interface AuthState { user: User | null; consents: Consents | null; loading: boolean; refresh: () => Promise<void>; logout: () => Promise<void>; setConsents: (c: Consents) => void }
const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [consents, setConsents] = useState<Consents | null>(null);
  const [loading, setLoading] = useState(true);
  const router = useRouter();
  const { setLang } = usePrefs();

  const refresh = useCallback(async () => {
    try {
      const me = await api<{ user: User; consents: Consents }>("/auth/me");
      setUser(me.user); setConsents(me.consents);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) { setUser(null); setConsents(null); } else throw e;
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { void refresh().catch(() => setLoading(false)); }, [refresh]);
  useEffect(() => {
    const h = () => { setUser(null); router.replace("/login?expired=1"); };
    window.addEventListener("sm:unauthorized", h);
    return () => window.removeEventListener("sm:unauthorized", h);
  }, [router]);
  useEffect(() => { if (user) setLang(user.preferred_language); }, [user, setLang]);

  const logout = useCallback(async () => { try { await api("/auth/logout", { method: "POST" }); } finally { setUser(null); setConsents(null); router.replace("/login"); } }, [router]);
  return <Ctx.Provider value={{ user, consents, loading, refresh, logout, setConsents }}>{children}</Ctx.Provider>;
}
export const useAuth = () => { const c = useContext(Ctx); if (!c) throw new Error("AuthProvider missing"); return c; };
