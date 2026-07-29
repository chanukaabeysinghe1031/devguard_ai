import { apiFetch, saveSession, type AuthSession } from "./client";

type TokenResponse = {
  access_token: string;
  user: {
    email: string;
    memberships: Array<{ organization_id: string }>;
  };
};

export async function login(email: string, password: string): Promise<AuthSession> {
  const body = await apiFetch<TokenResponse>("/auth/login", {
    method: "POST",
    session: null,
    body: JSON.stringify({ email, password }),
  });
  const organizationId = body.user.memberships[0]?.organization_id;
  if (!organizationId) {
    throw new Error("No organization membership on account.");
  }
  const session = {
    accessToken: body.access_token,
    organizationId,
    email: body.user.email,
  };
  saveSession(session);
  return session;
}

export async function register(
  email: string,
  password: string,
  fullName: string,
): Promise<AuthSession> {
  await apiFetch("/auth/register", {
    method: "POST",
    session: null,
    body: JSON.stringify({
      email,
      password,
      full_name: fullName,
    }),
  });
  return login(email, password);
}
