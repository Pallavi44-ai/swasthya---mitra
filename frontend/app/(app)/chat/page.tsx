"use client";
import { Suspense, useCallback, useEffect, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import { api } from "@/lib/api";
import { usePrefs } from "@/lib/prefs";
import { useAuth } from "@/lib/auth";
import { hasVoiceFor, speak, stopSpeaking, ttsSupported, useVoiceInput } from "@/lib/speech";
import { t } from "@/lib/i18n";
import type { ChatMessage, ChatReply, ChatSessionItem, Lang, StoredMessage } from "@/lib/types";
import { Icon } from "@/components/Icon";
import { Banner, PageHeader, errMsg, useToast } from "@/components/ui";
import Link from "next/link";

// Quick starters are optional shortcuts: each one simply sends this text to Ask Mitra like a typed message.
const STARTERS: Record<Lang, { lonely: string; talk: string; play: string; story: string; relax: string; health: string }> = {
  en: { lonely: "I feel lonely", talk: "I want to talk", play: "Let's play a game", story: "Tell me a story", relax: "Help me relax", health: "I have a health question" },
  hi: { lonely: "मुझे अकेलापन लग रहा है", talk: "मुझे बात करनी है", play: "चलो एक खेल खेलें", story: "मुझे एक कहानी सुनाओ", relax: "मुझे शांत होने में मदद करें", health: "मेरा एक स्वास्थ्य सवाल है" },
  kn: { lonely: "ನನಗೆ ಒಂಟಿತನ ಅನಿಸುತ್ತಿದೆ", talk: "ನನಗೆ ಮಾತನಾಡಬೇಕು", play: "ಒಂದು ಆಟ ಆಡೋಣ", story: "ನನಗೊಂದು ಕಥೆ ಹೇಳಿ", relax: "ನನಗೆ ಶಾಂತವಾಗಲು ಸಹಾಯ ಮಾಡಿ", health: "ನನಗೊಂದು ಆರೋಗ್ಯ ಪ್ರಶ್ನೆ ಇದೆ" },
  te: { lonely: "నాకు ఒంటరిగా అనిపిస్తోంది", talk: "నేను మాట్లాడాలనుకుంటున్నాను", play: "ఒక ఆట ఆడుదాం", story: "నాకు ఒక కథ చెప్పండి", relax: "నేను ప్రశాంతంగా ఉండటానికి సహాయం చేయండి", health: "నాకు ఒక ఆరోగ్య ప్రశ్న ఉంది" },
};

const SUGGESTIONS: Record<Lang, string[]> = {
  en: ["How do I make ORS at home?", "What should I do for a fever?", "Tips to control blood pressure"],
  hi: ["घर पर ORS कैसे बनाएँ?", "बुखार में क्या करना चाहिए?", "ब्लड प्रेशर कैसे नियंत्रित रखें?"],
  kn: ["ಮನೆಯಲ್ಲಿ ORS ಹೇಗೆ ಮಾಡುವುದು?", "ಜ್ವರ ಬಂದರೆ ಏನು ಮಾಡಬೇಕು?", "ರಕ್ತದೊತ್ತಡ ನಿಯಂತ್ರಣ ಸಲಹೆಗಳು"],
  te: ["ఇంట్లో ORS ఎలా తయారు చేయాలి?", "జ్వరం వస్తే ఏమి చేయాలి?", "రక్తపోటు నియంత్రణ చిట్కాలు"],
};

function ChatInner() {
  const { lang } = usePrefs();
  const { consents } = useAuth();
  const toast = useToast();
  const params = useSearchParams();
  const [msgs, setMsgs] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [heard, setHeard] = useState(false);
  const [voiceErr, setVoiceErr] = useState<string | null>(null);
  const [speakingId, setSpeakingId] = useState<string | null>(null);
  const sessionId = useRef<string | null>(null);
  const endRef = useRef<HTMLDivElement>(null);
  const [noVoice, setNoVoice] = useState(false);
  const [sessions, setSessions] = useState<ChatSessionItem[] | null>(null);
  const [activeId, setActiveId] = useState<string | null>(null);
  const [showHistory, setShowHistory] = useState(false);
  const wide = () => typeof window !== "undefined" && window.matchMedia("(min-width: 1024px)").matches;
  const [confirmId, setConfirmId] = useState<string | null>(null);

  const onText = useCallback((text: string) => { setInput(text); setHeard(true); setVoiceErr(null); }, []);
  const voice = useVoiceInput(lang, onText, setVoiceErr);

  const loadSessions = useCallback(async () => {
    try { setSessions(await api<ChatSessionItem[]>("/chat/sessions")); } catch { setSessions([]); }
  }, []);

  useEffect(() => { void loadSessions(); }, [loadSessions]);
  useEffect(() => {
    let saved: string | null = null;
    try { saved = localStorage.getItem("sm.chatHistoryOpen"); } catch { /* storage may be blocked */ }
    setShowHistory(window.matchMedia("(min-width: 1024px)").matches ? saved !== "0" : false);
  }, []);
  const toggleHistory = () => setShowHistory((v) => { const n = !v; try { localStorage.setItem("sm.chatHistoryOpen", n ? "1" : "0"); } catch { /* ignore */ } return n; });
  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [msgs, busy]);
  useEffect(() => { if (params.get("voice") === "1" && voice.supported) { /* browsers need a user gesture: show hint instead of auto-starting */ } }, [params, voice.supported]);
  useEffect(() => { if (ttsSupported()) { const f = () => setNoVoice(window.speechSynthesis.getVoices().length > 0 && !hasVoiceFor(lang)); f(); window.speechSynthesis.onvoiceschanged = f; } }, [lang]);

  async function send(text: string) {
    const q = text.trim(); if (!q || busy) return;
    stopSpeaking(); setSpeakingId(null); setInput(""); setHeard(false); setBusy(true);
    const history = msgs.slice(-6).map((m) => ({ role: m.role, content: m.text }));
    setMsgs((s) => [...s, { id: crypto.randomUUID(), role: "user", text: q }]);
    try {
      const hadSession = sessionId.current;
      const r = await api<ChatReply>("/chat", { body: { message: q, language: lang, session_id: sessionId.current, history } });
      if (r.session_id) { sessionId.current = r.session_id; setActiveId(r.session_id); }
      const id = crypto.randomUUID();
      setMsgs((s) => [...s, { id, role: "assistant", text: r.reply, reply: r }]);
      if (r.mode === "emergency") speak(r.reply, r.language); // emergencies are always read aloud
      if (r.stored && !hadSession) void loadSessions(); // a new saved chat appears in the list
    } catch (e) {
      setMsgs((s) => [...s, { id: crypto.randomUUID(), role: "assistant", text: (e as Error).message }]);
      toast((e as Error).message, "error");
    } finally { setBusy(false); }
  }

  function toggleSpeak(m: ChatMessage) {
    if (speakingId === m.id) { stopSpeaking(); setSpeakingId(null); return; }
    const ok = speak(m.text, m.reply?.language ?? lang, () => setSpeakingId(null));
    if (ok) setSpeakingId(m.id); else toast("This browser cannot read aloud.", "error");
  }

  function newChat() {
    stopSpeaking(); setSpeakingId(null); sessionId.current = null; setActiveId(null);
    setMsgs([]); setInput(""); setHeard(false); setVoiceErr(null); if (!wide()) setShowHistory(false);
  }

  async function openChat(id: string) {
    if (busy) return;
    stopSpeaking(); setSpeakingId(null);
    try {
      const rows = await api<StoredMessage[]>(`/chat/sessions/${id}/messages`);
      sessionId.current = id; setActiveId(id);
      setMsgs(rows.map((m) => ({ id: m.id, role: m.role, text: m.content })));
      if (!wide()) setShowHistory(false);
    } catch (e) { toast(errMsg(e), "error"); }
  }

  async function removeChat(id: string) {
    try {
      await api(`/chat/sessions/${id}`, { method: "DELETE" });
      setConfirmId(null);
      if (activeId === id) newChat();
      await loadSessions();
    } catch (e) { toast(errMsg(e), "error"); }
  }

  const S = STARTERS[lang];
  const starters: { text: string; label: string }[] = [
    { text: S.lonely, label: S.lonely }, { text: S.talk, label: S.talk }, { text: S.story, label: S.story }, { text: S.health, label: S.health },
  ];
  const historyOff = consents && !consents.store_chat_history;

  const historyPanel = (
    <nav aria-label={t("earlierChats", lang)} className="space-y-3">
      <button type="button" onClick={newChat} className="btn-primary w-full"><Icon name="chat" className="h-5 w-5" /> {t("newChat", lang)}</button>
      <h2 className="pt-2 text-lg font-bold">{t("earlierChats", lang)}</h2>
      {historyOff && (
        <p className="rounded-xl bg-saffron-tint p-3 text-sm text-saffron-ink">
          Chat history is switched off, so new chats are not saved. You can turn on “Store chat history” in <Link className="font-bold underline" href="/privacy">Privacy</Link>.
        </p>
      )}
      {sessions === null ? <p className="text-muted">…</p> : sessions.length === 0 ? (
        <p className="text-muted">{historyOff ? "No saved chats yet." : "Your saved chats will appear here."}</p>
      ) : (
        <ul className="space-y-2">
          {sessions.map((s) => (
            <li key={s.id} className={`rounded-xl border-2 ${activeId === s.id ? "border-brand bg-brand-tint" : "border-line bg-surface"}`}>
              <button type="button" onClick={() => void openChat(s.id)} aria-current={activeId === s.id} className="block min-h-[56px] w-full px-3 py-2 text-left">
                <span className="line-clamp-2 font-bold">{s.title || "Chat"}</span>
                <span className="text-sm text-muted">{new Date(s.created_at).toLocaleDateString("en-IN", { day: "numeric", month: "short", year: "numeric" })}</span>
              </button>
              {confirmId === s.id ? (
                <div className="flex flex-wrap items-center gap-2 border-t border-line px-3 py-2" role="alert">
                  <span className="font-bold">{t("sureDelete", lang)}</span>
                  <button type="button" className="btn-danger !min-h-[44px] !px-4 !py-1" onClick={() => void removeChat(s.id)}>{t("yesDelete", lang)}</button>
                  <button type="button" className="btn-quiet !min-h-[44px] !px-4 !py-1" onClick={() => setConfirmId(null)}>{t("cancel", lang)}</button>
                </div>
              ) : (
                <button type="button" className="min-h-[44px] w-full border-t border-line px-3 text-left text-sm font-bold text-sos hover:underline" onClick={() => setConfirmId(s.id)}>{t("deleteChat", lang)}</button>
              )}
            </li>
          ))}
        </ul>
      )}
    </nav>
  );

  return (
    <div className={showHistory ? "lg:grid lg:grid-cols-[18rem_1fr] lg:gap-8" : ""}>
      <aside className="mb-4 lg:mb-0">
        <button type="button" className="btn-quiet w-full lg:w-auto" aria-expanded={showHistory} aria-controls="chat-history" onClick={toggleHistory}>
          <Icon name={showHistory ? "x" : "menu"} className="h-5 w-5" /> {showHistory ? "Hide chat history" : `Show ${t("earlierChats", lang).toLowerCase()}`}
        </button>
        <div id="chat-history" className={`${showHistory ? "mt-3 block" : "hidden"} lg:sticky lg:top-24`}>{historyPanel}</div>
      </aside>

      <div className="flex min-h-[70vh] min-w-0 flex-col">
        <PageHeader title={t("chat", lang)} intro="Ask me anything, or just talk. For health questions I give general information in simple words. If something sounds like an emergency, I will tell you to call 108 straight away." />
        {consents && !consents.ai_processing && <div className="mb-4"><Banner tone="warn" title="AI answers are switched off">You have not allowed AI processing, so I can only show short notes from my trusted library (English). <Link className="font-bold underline" href="/privacy">Change in Privacy</Link></Banner></div>}
        {speakingId && <div className="mb-3"><button type="button" className="btn-danger" onClick={() => { stopSpeaking(); setSpeakingId(null); }}><Icon name="speaker" className="h-5 w-5" /> {t("stopReadingAll", lang)}</button></div>}

        <div className="flex-1 space-y-5" aria-live="polite">
          {msgs.length === 0 && (
            <div className="rounded-2xl bg-brand-tint p-6">
              <p className="text-xl font-bold">{lang === "en" ? "How can I help you today?" : t("typeHere", lang)}</p>
              <div className="mt-4 grid gap-3 sm:grid-cols-3">
                <button type="button" className="btn-primary !min-h-[64px] text-lg" onClick={() => void send(S.play)}>{t("letsPlay", lang)}</button>
                <button type="button" className="btn-primary !min-h-[64px] text-lg" onClick={() => void send(S.talk)}>{t("talkWithMe", lang)}</button>
                <button type="button" className="btn-primary !min-h-[64px] text-lg" onClick={() => void send(S.relax)}>{t("helpRelax", lang)}</button>
              </div>
              <div className="mt-4 flex flex-wrap gap-2">{starters.map((s) => <button key={s.text} type="button" className="btn-quiet !min-h-[48px] text-left" onClick={() => void send(s.text)}>{s.label}</button>)}</div>
              <p className="mt-5 font-bold">{lang === "en" ? "Or ask a health question:" : ""}</p>
              <div className="mt-2 flex flex-wrap gap-2">{SUGGESTIONS[lang].map((s) => <button key={s} type="button" className="btn-quiet !min-h-[48px] text-left" onClick={() => void send(s)}>{s}</button>)}</div>
            </div>
          )}
          {msgs.map((m) => m.role === "user" ? (
            <div key={m.id} className="ml-auto w-fit max-w-[85%] whitespace-pre-line rounded-2xl rounded-br-md bg-brand px-5 py-3 text-white">{m.text}</div>
          ) : <Reply key={m.id} m={m} speaking={speakingId === m.id} onSpeak={() => toggleSpeak(m)} lang={lang} />)}
          {busy && <p role="status" className="text-muted">…</p>}
          <div ref={endRef} className="h-32" aria-hidden />
        </div>

        <form className="sticky bottom-28 mt-6 rounded-2xl border-2 border-line bg-surface p-3 shadow-lg lg:bottom-4" onSubmit={(e) => { e.preventDefault(); void send(input); }}>
          {heard && <p className="mb-2 font-bold text-saffron-ink">{t("heard", lang)}</p>}
          {voiceErr && <p role="alert" className="mb-2 font-bold text-sos">{voiceErr}</p>}
          {noVoice && <p className="mb-2 text-sm text-muted">Your device has no {lang.toUpperCase()} voice installed, so answers may not be read aloud in this language.</p>}
          <div className="flex items-center gap-3">
            <button type="button" onClick={voice.toggle} disabled={voice.state === "transcribing"}
              aria-label={voice.state === "listening" ? t("listening", lang) : t("tapSpeak", lang)} aria-pressed={voice.state === "listening"}
              className={`relative grid h-[72px] w-[72px] shrink-0 place-items-center rounded-full text-white ${voice.state === "listening" ? "bg-sos" : "bg-brand hover:bg-brand-dark"} disabled:opacity-50`}>
              {voice.state === "listening" && <span className="orb-ring absolute inset-0 rounded-full bg-sos" aria-hidden />}
              <Icon name="mic" className="relative h-9 w-9" />
            </button>
            <label className="sr-only" htmlFor="q">{t("typeHere", lang)}</label>
            <input id="q" className="field" value={input} maxLength={2000} onChange={(e) => { setInput(e.target.value); setHeard(false); }}
              placeholder={voice.state === "listening" ? t("listening", lang) : voice.state === "transcribing" ? "…" : t("typeHere", lang)} autoComplete="off" />
            <button className="btn-primary" disabled={busy || !input.trim()}>{t("send", lang)}</button>
          </div>
          <p className="mt-2 text-xs text-muted">{voice.mode === "browser" ? "Voice uses your browser's speech recognition. You can always type instead." : voice.mode === "server" ? "Voice is sent to the server for transcription (needs AI consent). You can always type instead." : "Voice input is not available here – please type."}</p>
        </form>
      </div>
    </div>
  );
}

function Reply({ m, speaking, onSpeak, lang }: { m: ChatMessage; speaking: boolean; onSpeak: () => void; lang: Lang }) {
  const r = m.reply;
  if (r?.mode === "emergency") {
    return (
      <div role="alert" className="rounded-2xl border-4 border-sos bg-sos-tint p-6">
        <div className="flex items-center gap-3 text-sos"><Icon name="alert" className="h-9 w-9" /><p className="text-2xl font-bold">{t("emergencyHead", lang)}</p></div>
        <p className="mt-3 text-lg font-bold">{m.text}</p>
        <div className="mt-5 grid gap-3 sm:grid-cols-2">
          {r.safety.numbers.map((n) => <a key={n.number} href={`tel:${n.number}`} className="btn-danger !min-h-[64px] text-xl"><Icon name="phone" /> {n.number} – {n.label}</a>)}
          {r.safety.contacts.slice(0, 2).map((c) => <a key={c.id} href={`tel:${c.phone}`} className="btn-quiet !min-h-[64px]"><Icon name="phone" /> {c.name}</a>)}
        </div>
        <p className="mt-4 text-sm text-muted">{r.disclaimer}</p>
      </div>
    );
  }
  // The medical note belongs to health answers only; friendly chat and games do not need it.
  const showDisclaimer = r && r.mode !== "companion" && r.mode !== "general_chat" && r.topic !== "general" && r.topic !== "emotional" && r.topic !== "activity";
  return (
    <div className="max-w-[95%] space-y-3">
      {r?.safety.banner && <Banner tone="warn" role="alert" title={r.safety.banner} />}
      <div className="rounded-2xl rounded-bl-md border border-line bg-surface px-5 py-4">
        <p className="whitespace-pre-line text-lg">{m.text}</p>
        {r?.actions.map((a) => <Link key={a.href} href={a.href} className="btn-primary mt-4">{a.label}</Link>)}
        {r && r.mode === "unavailable" && <p className="mt-3 text-sm text-muted">{r.unavailable_reason === "no_consent" ? "AI processing consent is off (Privacy page)." : r.unavailable_reason === "not_configured" ? "The AI service is not configured on this server yet." : "The AI service did not respond."}</p>}
        {r && r.mode === "retrieval_only" && <p className="mt-3 text-sm text-muted">Showing a note from my library without AI ({r.unavailable_reason === "no_consent" ? "AI consent is off" : r.unavailable_reason === "not_configured" ? "AI service not configured" : "AI service unavailable"}).</p>}
        {r && r.sources.length > 0 && (
          <details className="mt-3 text-sm"><summary className="cursor-pointer font-bold text-brand">Sources ({r.sources.length})</summary>
            <ul className="mt-2 space-y-1 text-muted">{r.sources.map((s) => <li key={s.n}>[{s.n}] {s.title} – {s.section}. {s.source_url ? <a className="underline" href={s.source_url} target="_blank" rel="noreferrer">{s.source_name}</a> : s.source_name}{s.review_status.includes("unreviewed") && <span className="ml-1 rounded bg-saffron-tint px-1.5 text-saffron-ink">pending clinical review</span>}</li>)}</ul>
          </details>)}
        <div className="mt-3 flex flex-wrap items-center gap-3 border-t border-line pt-3">
          <button className="btn-quiet !min-h-[44px] !px-4 !py-1" onClick={onSpeak} aria-pressed={speaking}><Icon name="speaker" className="h-5 w-5" /> {speaking ? t("stopReading", lang) : t("readAloud", lang)}</button>
          {showDisclaimer && <span className="text-xs text-muted">{r.disclaimer}</span>}
        </div>
      </div>
    </div>
  );
}

export default function ChatPage() { return <Suspense><ChatInner /></Suspense>; }
