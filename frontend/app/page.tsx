import Link from "next/link";

const FEATURES = [
  ["Ask by voice or text", "In English, Hindi, Kannada or Telugu. Answers are read aloud if you like."],
  ["Read a prescription", "Take a photo. I show what I found and how sure I am. You confirm every medicine."],
  ["Remember your medicines", "Reminders are made only from medicines you confirmed, and you can see what you took."],
  ["Know when to get help", "Serious symptoms get a clear instruction to call 108, not a chatbot answer."],
];

export default function Landing() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between px-5 py-5">
        <span className="text-xl font-bold text-brand">Swasthya Mitra</span>
        <nav className="flex gap-3"><Link href="/login" className="btn-quiet">Log in</Link><Link href="/register" className="btn-primary">Create account</Link></nav>
      </header>
      <main>
        <section className="mx-auto grid max-w-6xl gap-10 px-5 pb-16 pt-8 lg:grid-cols-[1.2fr_1fr] lg:items-center">
          <div>
            <h1 className="text-3xl font-bold leading-tight sm:text-4xl lg:text-5xl">A health companion that listens, reads and reminds.</h1>
            <p className="mt-5 max-w-xl text-lg text-muted">Built for people who find health apps hard to use: big buttons, your own language, and your voice instead of typing.</p>
            <div className="mt-8 flex flex-wrap gap-3"><Link href="/register" className="btn-primary !min-h-[60px] text-lg">Create a free account</Link><Link href="/login" className="btn-quiet !min-h-[60px] text-lg">I already have one</Link></div>
          </div>
          <ul className="space-y-3" aria-label="What it does">
            {FEATURES.map(([h, p]) => <li key={h} className="rounded-2xl border border-line bg-surface p-5"><p className="text-lg font-bold">{h}</p><p className="text-muted">{p}</p></li>)}
          </ul>
        </section>
        <section className="border-t border-line bg-surface">
          <div className="mx-auto max-w-6xl px-5 py-8"><p className="max-w-3xl text-muted"><b className="text-ink">Please remember:</b> Swasthya Mitra is a support tool. It does not replace a doctor, give a diagnosis, prescribe medicines or change doses. In an emergency, call <b className="text-sos">108</b>.</p></div>
        </section>
      </main>
    </div>
  );
}
