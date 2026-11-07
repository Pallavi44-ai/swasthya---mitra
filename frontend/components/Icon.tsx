const P: Record<string, string> = {
  home: "M3 11l9-8 9 8M5 10v10h5v-6h4v6h5V10",
  chat: "M4 5h16v11H9l-5 4V5z",
  pill: "M8.5 4.5a4.2 4.2 0 016 6l-8 8a4.2 4.2 0 01-6-6l8-8zM8 9l7 7",
  bell: "M6 9a6 6 0 1112 0c0 6 2 7 2 7H4s2-1 2-7zM10 20a2 2 0 004 0",
  heart: "M12 20s-8-5-8-11a4.5 4.5 0 018-2.5A4.5 4.5 0 0120 9c0 6-8 11-8 11z",
  file: "M7 3h8l4 4v14H7V3zM14 3v5h5M10 13h6M10 17h6",
  shield: "M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3zM9 12l2 2 4-4",
  gear: "M12 15a3 3 0 100-6 3 3 0 000 6zM19 12l2-1-2-4-2 1a7 7 0 00-2-1l-.5-2h-4L10 7a7 7 0 00-2 1l-2-1-2 4 2 1a7 7 0 000 2l-2 1 2 4 2-1a7 7 0 002 1l.5 2h4l.5-2a7 7 0 002-1l2 1 2-4-2-1a7 7 0 000-2z",
  mic: "M12 3a3 3 0 00-3 3v6a3 3 0 006 0V6a3 3 0 00-3-3zM5 11a7 7 0 0014 0M12 18v3",
  phone: "M5 4h4l2 5-3 2a11 11 0 005 5l2-3 5 2v4a2 2 0 01-2 2A16 16 0 013 6a2 2 0 012-2z",
  camera: "M4 8h3l2-3h6l2 3h3v11H4V8zM12 17a4 4 0 100-8 4 4 0 000 8z",
  check: "M5 12l5 5 9-10",
  alert: "M12 3l10 18H2L12 3zM12 10v5M12 18v.5",
  speaker: "M4 9v6h4l5 4V5L8 9H4zM17 8a5 5 0 010 8",
  lock: "M6 11h12v10H6V11zM8 11V7a4 4 0 018 0v4",
  logout: "M10 4H5v16h5M15 8l4 4-4 4M19 12H9",
  menu: "M4 7h16M4 12h16M4 17h16",
  x: "M6 6l12 12M18 6L6 18",
};
export function Icon({ name, className = "h-6 w-6" }: { name: keyof typeof P | string; className?: string }) {
  return (
    <svg viewBox="0 0 24 24" className={className} fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
      <path d={P[name] ?? P.alert} />
    </svg>
  );
}
