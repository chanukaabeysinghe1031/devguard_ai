const API_BASE = import.meta.env.VITE_API_BASE_URL || "http://localhost:8000/api/v1";

export type AuthSession = {
  accessToken: string;
  organizationId: string;
  email: string;
};

const SESSION_KEY = "devguard.session";

export function loadSession(): AuthSession | null {
  const raw = sessionStorage.getItem(SESSION_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw) as AuthSession;
  } catch {
    return null;
  }
}

export function saveSession(session: AuthSession): void {
  sessionStorage.setItem(SESSION_KEY, JSON.stringify(session));
}

export function clearSession(): void {
  sessionStorage.removeItem(SESSION_KEY);
}

export class ApiError extends Error {
  status: number;
  body: unknown;

  constructor(message: string, status: number, body: unknown) {
    super(message);
    this.status = status;
    this.body = body;
  }
}

export async function apiFetch<T>(
  path: string,
  options: RequestInit & { session?: AuthSession | null; formData?: FormData } = {},
): Promise<T> {
  const headers = new Headers(options.headers || {});
  const session = options.session === undefined ? loadSession() : options.session;
  if (session?.accessToken) {
    headers.set("Authorization", `Bearer ${session.accessToken}`);
  }
  if (session?.organizationId) {
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
    const err = (payload ?? {}) as {
      detail?: string | { message?: string };
      message?: string;
    };
    const detail =
      typeof err.detail === "string"
        ? err.detail
        : err.detail?.message || err.message || response.statusText;
    throw new ApiError(detail || "Request failed", response.status, payload);
  }
  return payload as T;
}

export { API_BASE };
