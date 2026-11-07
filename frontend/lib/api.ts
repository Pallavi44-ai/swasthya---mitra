export class ApiError extends Error {
  constructor(public status: number, message: string, public detail?: unknown) { super(message); }
}

function messageFrom(detail: unknown, fallback: string): string {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) return detail.map((d) => (d?.msg ? String(d.msg).replace(/^Value error, /, "") : "")).filter(Boolean).join(". ") || fallback;
  if (detail && typeof detail === "object") {
    const d = detail as { message?: string; problems?: string[] };
    if (d.problems?.length) return d.problems.join(". ");
    if (d.message) return d.message;
  }
  return fallback;
}

export async function api<T = unknown>(path: string, init: { method?: string; body?: unknown; form?: FormData } = {}): Promise<T> {
  const headers: Record<string, string> = {};
  let body: BodyInit | undefined;
  if (init.form) body = init.form;
  else if (init.body !== undefined) { headers["Content-Type"] = "application/json"; body = JSON.stringify(init.body); }
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { method: init.method ?? (body ? "POST" : "GET"), headers, body, credentials: "same-origin" });
  } catch {
    throw new ApiError(0, "Cannot reach the server. Check your internet connection and try again.");
  }
  if (res.status === 204) return undefined as T;
  const text = await res.text();
  let data: unknown = undefined;
  try { data = text ? JSON.parse(text) : undefined; } catch { /* non-JSON error page */ }
  if (!res.ok) {
    const detail = (data as { detail?: unknown } | undefined)?.detail;
    if (res.status === 401 && typeof window !== "undefined" && !path.startsWith("/auth/")) window.dispatchEvent(new Event("sm:unauthorized"));
    throw new ApiError(res.status, messageFrom(detail, res.status >= 500 ? "The server had a problem. Please try again." : "Request failed."), detail);
  }
  return data as T;
}
