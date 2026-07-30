/**
 * Direct API helpers (bypassing the UI) for fast test setup and org/data isolation checks.
 *
 * These use the same endpoints as the frontend `src/api/*` modules but call `fetch` directly
 * against E2E_API_BASE_URL, so they can be used from Playwright specs without booting a page.
 * Keep UI-driven assertions in the specs themselves — these helpers exist purely for setup,
 * teardown, and cross-checking state that would be slow or flaky to establish through the UI.
 */
import { API_BASE_URL } from "./env";

export interface ApiSession {
  accessToken: string;
  refreshToken: string;
  organizationId: string;
  userId: string;
  email: string;
  role: string;
}

interface Membership {
  organization_id: string;
  role: string;
  is_active: boolean;
}

interface TokenResponseBody {
  access_token: string;
  refresh_token: string;
  user: {
    id: string;
    email: string;
    memberships: Membership[];
  };
}

async function request<T>(
  path: string,
  options: { method?: string; body?: unknown; session?: ApiSession | null; formData?: FormData } = {},
): Promise<T> {
  const headers: Record<string, string> = {};
  if (options.session) {
    headers.Authorization = `Bearer ${options.session.accessToken}`;
    headers["X-Organization-Id"] = options.session.organizationId;
  }
  if (options.body !== undefined && !options.formData) {
    headers["Content-Type"] = "application/json";
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    method: options.method ?? "GET",
    headers,
    body: options.formData ?? (options.body !== undefined ? JSON.stringify(options.body) : undefined),
  });

  const text = await response.text();
  const payload = text ? JSON.parse(text) : null;

  if (!response.ok) {
    throw new Error(`API ${options.method ?? "GET"} ${path} failed with ${response.status}: ${text}`);
  }
  return payload as T;
}

export async function apiRegister(payload: { email: string; password: string; full_name: string }): Promise<void> {
  await request("/auth/register", { method: "POST", body: payload });
}

export async function apiLogin(email: string, password: string): Promise<ApiSession> {
  const body = await request<TokenResponseBody>("/auth/login", {
    method: "POST",
    body: { email, password },
  });
  const membership = body.user.memberships.find((m) => m.is_active) ?? body.user.memberships[0];
  if (!membership) {
    throw new Error(`User ${email} has no active organization membership`);
  }
  return {
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    organizationId: membership.organization_id,
    userId: body.user.id,
    email: body.user.email,
    role: membership.role,
  };
}

export async function apiRegisterAndLogin(user: {
  email: string;
  password: string;
  fullName: string;
}): Promise<ApiSession> {
  await apiRegister({ email: user.email, password: user.password, full_name: user.fullName });
  return apiLogin(user.email, user.password);
}

export interface ApiProject {
  id: string;
  name: string;
  key: string;
}

export async function apiCreateProject(
  session: ApiSession,
  overrides: Partial<{ name: string; key: string; ci_provider: string }> = {},
): Promise<ApiProject> {
  const stamp = Date.now().toString(36);
  return request<ApiProject>("/projects", {
    method: "POST",
    session,
    body: {
      name: overrides.name ?? `E2E API Project ${stamp}`,
      key: overrides.key ?? `E2EAPI${stamp}`.toUpperCase().slice(0, 20),
      ci_provider: overrides.ci_provider ?? "github_actions",
    },
  });
}

export interface ApiIncident {
  id: string;
  title: string;
  status: string;
}

export async function apiCreateIncident(
  session: ApiSession,
  projectId: string,
  overrides: Partial<{ title: string; severity: string; source: string }> = {},
): Promise<ApiIncident> {
  const stamp = Date.now().toString(36);
  return request<ApiIncident>("/incidents", {
    method: "POST",
    session,
    body: {
      project_id: projectId,
      title: overrides.title ?? `E2E API Incident ${stamp}`,
      severity: overrides.severity ?? "medium",
      source: overrides.source ?? "manual_upload",
    },
  });
}

export async function apiGetIncident(session: ApiSession, incidentId: string): Promise<Record<string, unknown>> {
  return request(`/incidents/${incidentId}`, { session });
}

export async function apiWaitForAnalysisCompletion(
  session: ApiSession,
  analysisRunId: string,
  timeoutMs = 180_000,
): Promise<Record<string, unknown>> {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const status = await request<{ status: string }>(`/analyses/${analysisRunId}/status`, { session });
    if (status.status === "completed" || status.status === "failed") {
      return status;
    }
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
  throw new Error(`Analysis ${analysisRunId} did not complete within ${timeoutMs}ms`);
}
