"use client";
import { useEffect, useState } from "react";
import { api } from "@/lib/api";
import type { SystemStatus } from "@/lib/types";
import { Banner, PageHeader, Spinner, errMsg } from "@/components/ui";

const TONE = { implemented: { t: "Working", c: "bg-ok-tint text-ok" }, configured: { t: "Configured", c: "bg-ok-tint text-ok" }, needs_configuration: { t: "Needs setup", c: "bg-saffron-tint text-saffron-ink" } };

export default function Status() {
  const [s, setS] = useState<SystemStatus | null>(null);
  const [err, setErr] = useState<string | null>(null);
  useEffect(() => { api<SystemStatus>("/system/status").then(setS).catch((e) => setErr(errMsg(e))); }, []);
  if (err) return <Banner tone="error">{err}</Banner>;
  if (!s) return <Spinner />;
  return (
    <div className="space-y-6">
      <PageHeader title="System status" intro={`What is really running on this server right now (environment: ${s.environment}, database: ${s.database}). Items marked “Needs setup” are not working until configured.`} />
      <ul className="divide-y divide-line rounded-2xl border border-line bg-surface">
        {s.components.map((c) => (
          <li key={c.id} className="flex flex-wrap items-start gap-3 p-4"><div className="min-w-[14rem] flex-1"><p className="font-bold">{c.name}</p>{c.note && <p className="text-muted">{c.note}</p>}</div><span className={`rounded-full px-4 py-1 text-sm font-bold ${TONE[c.state].c}`}>{TONE[c.state].t}</span></li>))}
      </ul>
      <Banner tone="warn" title="Limitations"><ul className="list-disc pl-5">{s.limitations.map((l) => <li key={l}>{l}</li>)}</ul></Banner>
    </div>
  );
}
