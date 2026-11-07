"use client";
import { useCallback, useEffect, useRef, useState } from "react";
import { api } from "./api";
import { localeOf } from "./i18n";
import type { Lang } from "./types";

/* ---------- Text-to-speech (browser speechSynthesis) ---------- */
export function ttsSupported() { return typeof window !== "undefined" && "speechSynthesis" in window; }

export function hasVoiceFor(lang: Lang): boolean {
  if (!ttsSupported()) return false;
  return window.speechSynthesis.getVoices().some((v) => v.lang.toLowerCase().startsWith(lang));
}

export function speak(text: string, lang: Lang, onEnd?: () => void): boolean {
  if (!ttsSupported()) return false;
  const synth = window.speechSynthesis;
  synth.cancel();
  const u = new SpeechSynthesisUtterance(text);
  u.lang = localeOf(lang);
  const voice = synth.getVoices().find((v) => v.lang.toLowerCase().replace("_", "-").startsWith(lang));
  if (voice) u.voice = voice;
  u.rate = 0.92; // slightly slower for elderly listeners
  u.onend = () => onEnd?.();
  u.onerror = () => onEnd?.();
  synth.speak(u);
  return true;
}
export function stopSpeaking() { if (ttsSupported()) window.speechSynthesis.cancel(); }

/* ---------- Speech-to-text: browser SpeechRecognition first, server (Gemini) transcription as fallback ---------- */
type SR = { start(): void; stop(): void; abort(): void; lang: string; interimResults: boolean; continuous: boolean;
  onresult: ((e: any) => void) | null; onerror: ((e: any) => void) | null; onend: (() => void) | null };

export type VoiceState = "idle" | "listening" | "transcribing";

export function useVoiceInput(lang: Lang, onText: (text: string) => void, onError: (msg: string) => void) {
  const [state, setState] = useState<VoiceState>("idle");
  const [mode, setMode] = useState<"browser" | "server" | "none">("none");
  const rec = useRef<SR | null>(null);
  const media = useRef<{ recorder: MediaRecorder; chunks: Blob[] } | null>(null);

  useEffect(() => {
    const w = window as any;
    if (w.SpeechRecognition || w.webkitSpeechRecognition) setMode("browser");
    else if (typeof MediaRecorder !== "undefined" && navigator.mediaDevices) setMode("server");
  }, []);

  const startBrowser = useCallback(() => {
    const w = window as any;
    const Ctor = w.SpeechRecognition || w.webkitSpeechRecognition;
    const r: SR = new Ctor();
    r.lang = localeOf(lang); r.interimResults = false; r.continuous = false;
    let got = false;
    r.onresult = (e) => { got = true; onText(Array.from(e.results as ArrayLike<any>).map((x) => x[0].transcript).join(" ").trim()); };
    r.onerror = (e) => {
      const m: Record<string, string> = {
        "not-allowed": "Microphone permission is blocked. Allow the microphone in your browser, or type your question.",
        "no-speech": "I could not hear anything. Tap the microphone and try again.",
        "network": "Voice recognition needs an internet connection. You can type instead.",
        "language-not-supported": "This browser cannot recognise this language by voice. Try typing instead.",
      };
      onError(m[e.error] ?? "Voice input stopped. You can type your question instead.");
    };
    r.onend = () => { setState("idle"); if (!got) { /* error already reported or silence */ } };
    rec.current = r; setState("listening"); r.start();
  }, [lang, onText, onError]);

  const startServer = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const recorder = new MediaRecorder(stream);
      const chunks: Blob[] = [];
      recorder.ondataavailable = (e) => chunks.push(e.data);
      recorder.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        setState("transcribing");
        try {
          const blob = new Blob(chunks, { type: recorder.mimeType || "audio/webm" });
          const form = new FormData();
          form.append("audio", blob, "voice.webm"); form.append("language", lang);
          const res = await api<{ text: string }>("/voice/transcribe", { form });
          onText(res.text);
        } catch (e: any) { onError(e.message || "Could not transcribe. Please type your question."); }
        setState("idle");
      };
      media.current = { recorder, chunks }; recorder.start(); setState("listening");
    } catch { onError("Microphone permission is blocked. Allow the microphone in your browser, or type your question."); setState("idle"); }
  }, [lang, onText, onError]);

  const toggle = useCallback(() => {
    if (state === "listening") { mode === "browser" ? rec.current?.stop() : media.current?.recorder.stop(); return; }
    if (state !== "idle") return;
    stopSpeaking();
    if (mode === "browser") startBrowser(); else if (mode === "server") void startServer();
    else onError("Voice input is not available in this browser. Please type your question.");
  }, [state, mode, startBrowser, startServer, onError]);

  useEffect(() => () => { rec.current?.abort(); }, []);
  return { state, mode, toggle, supported: mode !== "none" };
}
