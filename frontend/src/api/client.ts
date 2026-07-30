import type { AccessTokenResponse, AuthSession } from "../types/auth";

export type { AuthSession } from "../types/auth";

const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

const SESSION_KEY = "devguard.session";

/** Session storage lives only for the tab lifetime. Never persisted to localStorage. */
export function loadSession(): AuthSession | null {
  try {
    const raw = sessionStorage.getItem(SESSION_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as AuthSession;
  } catch {
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function updateSessionTokens(tokens: { accessToken: string; refreshToken?: string }): void {
  const current = loadSession();
  if (!current) return;
  saveSession({
    ...current,
    accessToken: tokens.accessToken,
    refreshToken: tokens.refreshToken ?? current.refreshToken,
  });
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

export class ApiError extends Error {
  status: number;
  body: unknown;
  code: string | null;
  requestId: string | null;

  constructor(message: string, status: number, body: unknown, code: string | null = null, requestId: string | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.body = body;
    this.code = code;
    this.requestId = requestId;
  }
}

function mapDetail(payload: unknown, fallback: string): { message: string; code: string | null; requestId: string | null } {
  if (payload && typeof payload === "object") {
    const body = payload as Record<string, unknown>;
    const errorObj = body.error;
    if (errorObj && typeof errorObj === "object") {
      const err = errorObj as Record<string, unknown>;
      return {
        message: typeof err.message === "string" ? err.message : fallback,
        code: typeof err.code === "string" ? err.code : null,
        requestId: typeof err.request_id === "string" ? err.request_id : null,
      };
    }
    const detail = body.detail;
    if (typeof detail === "string") {
      return { message: detail, code: null, requestId: null };
    }
    if (detail && typeof detail === "object") {
      const detailObj = detail as Record<string, unknown>;
      if (typeof detailObj.message === "string") {
        return { message: detailObj.message, code: null, requestId: null };
      }
    }
    if (typeof body.message === "string") {
      return { message: body.message, code: null, requestId: null };
    }
  }
  return { message: fallback, code: null, requestId: null };
}

let refreshPromise: Promise<boolean> | null = null;

async function performRefresh(): Promise<boolean> {
  const session = loadSession();
  if (!session?.refreshToken) return false;
  try {
    const response = await fetch(`${API_BASE}/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ refresh_token: session.refreshToken }),
    });
    if (!response.ok) return false;
    const data = (await response.json()) as AccessTokenResponse;
    updateSessionTokens({
      accessToken: data.access_token,
      refreshToken: data.refresh_token ?? undefined,
    });
    return true;
  } catch {
    return false;
  }
}

function redirectToLogin(): void {
  clearSession();
  if (typeof window !== "undefined") {
    const next = encodeURIComponent(window.location.pathname + window.location.search);
    window.location.href = `/login?next=${next}`;
  }
}

export interface ApiFetchOptions extends RequestInit {
  session?: AuthSession | null;
  formData?: FormData;
  /** Internal: prevents infinite refresh loops. */
  _isRetry?: boolean;
  /** Skip auth headers entirely (login/register/refresh). */
  skipAuth?: boolean;
}

export async function apiFetch<T>(path: string, options: ApiFetchOptions = {}): Promise<T> {
  const headers = new Headers(options.headers || {});
  const session = options.session === undefined ? loadSession() : options.session;

  if (!options.skipAuth && session?.accessToken) {
    headers.set("Authorization", `Bearer ${session.accessToken}`);
  }
  if (!options.skipAuth && session?.organizationId) {
    headers.set("X-Organization-Id", session.organizationId);
  }
  if (!options.formData && !headers.has("Content-Type") && options.body) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE}${path}`, {
    ...options,
    headers,
    body: options.formData ?? options.body,
  });

  if (response.status === 401 && !options.skipAuth && !options._isRetry && loadSession()?.refreshToken) {
    if (!refreshPromise) {
      refreshPromise = performRefresh().finally(() => {
        refreshPromise = null;
      });
    }
    const refreshed = await refreshPromise;
    if (refreshed) {
      return apiFetch<T>(path, { ...options, _isRetry: true });
    }
    redirectToLogin();
    throw new ApiError("Session expired. Please sign in again.", 401, null, "SESSION_EXPIRED");
  }

  const text = await response.text();
  let payload: unknown = null;
  if (text) {
    try {
      payload = JSON.parse(text);
    } catch {
      payload = { detail: text };
    }
  }

  if (!response.ok) {
    const { message, code, requestId } = mapDetail(payload, response.statusText || "Request failed");
    if (response.status === 401 && !options.skipAuth) {
      redirectToLogin();
    }
    throw new ApiError(message, response.status, payload, code, requestId);
  }

  return payload as T;
}

export { API_BASE };
