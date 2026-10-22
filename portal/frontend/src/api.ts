// REST helpers for the stage portal. Every call returns a result, never throws, so a route the
// backend has not landed yet reads as "not available" on screen instead of a blank page.

export type ApiResult<T> =
  | { ok: true; data: T; status: number }
  | { ok: false; error: string; status: number; missing: boolean };

export const NOT_AVAILABLE = "not available";

async function call<T>(url: string, init?: RequestInit): Promise<ApiResult<T>> {
  try {
    const r = await fetch(url, init);
    let data: unknown = null;
    const text = await r.text();
    if (text) {
      try { data = JSON.parse(text); } catch { data = text; }
    }
    if (!r.ok) {
      const body = (data ?? {}) as Record<string, unknown>;
      const missing = r.status === 404 || r.status === 405 || r.status === 501;
      const reason = typeof body === "object" && body !== null ? (body.reason ?? body.detail ?? body.error) : null;
      return { ok: false, status: r.status, missing, error: missing ? NOT_AVAILABLE : String(reason ?? `HTTP ${r.status}`) };
    }
    return { ok: true, data: data as T, status: r.status };
  } catch (err) {
    return { ok: false, status: 0, missing: false, error: err instanceof Error ? err.message : String(err) };
  }
}

export function apiGet<T>(url: string): Promise<ApiResult<T>> { return call<T>(url); }
export function apiPost<T>(url: string, body?: unknown): Promise<ApiResult<T>> {
  return call<T>(url, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body ?? {}) });
}

export function errText<T>(r: ApiResult<T> | null | undefined): string | null {
  if (!r || r.ok) return null;
  return r.missing ? `${NOT_AVAILABLE} (backend route missing)` : r.error;
}
