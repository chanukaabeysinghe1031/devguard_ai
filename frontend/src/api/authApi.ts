import { apiFetch, clearSession, saveSession } from "./client";
import type {
  AuthSession,
  ChangePasswordRequest,
  LoginRequest,
  RegisterRequest,
  TokenResponse,
  UserPublic,
} from "../types/auth";
import type { MessageResponse } from "../types/common";

function sessionFromToken(body: TokenResponse): AuthSession {
  const membership = body.user.memberships.find((m) => m.is_active) ?? body.user.memberships[0];
  if (!membership) {
    throw new Error("Your account has no active organization membership.");
  }
  return {
    accessToken: body.access_token,
    refreshToken: body.refresh_token,
    organizationId: membership.organization_id,
    email: body.user.email,
    fullName: body.user.full_name,
    role: membership.role,
    platformRole: body.user.platform_role,
    userId: body.user.id,
  };
}

export async function login(payload: LoginRequest): Promise<AuthSession> {
  const body = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    skipAuth: true,
    session: null,
    body: JSON.stringify(payload),
  });
  const session = sessionFromToken(body);
  saveSession(session);
  return session;
}

export async function register(payload: RegisterRequest): Promise<UserPublic> {
  return apiFetch<UserPublic>("/auth/register", {
    method: "POST",
    skipAuth: true,
    session: null,
    body: JSON.stringify(payload),
  });
}

export async function logout(): Promise<void> {
  const session = JSON.parse(sessionStorage.getItem("devguard.session") || "null") as AuthSession | null;
  try {
    if (session?.refreshToken) {
      await apiFetch<MessageResponse>("/auth/logout", {
        method: "POST",
        body: JSON.stringify({ refresh_token: session.refreshToken }),
      });
    }
  } finally {
    clearSession();
  }
}

export async function fetchCurrentUser(): Promise<UserPublic> {
  return apiFetch<UserPublic>("/auth/me");
}

export async function changePassword(payload: ChangePasswordRequest): Promise<MessageResponse> {
  return apiFetch<MessageResponse>("/auth/change-password", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}
