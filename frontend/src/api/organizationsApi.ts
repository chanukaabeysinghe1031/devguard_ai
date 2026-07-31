import { apiFetch } from "./client";
import type { MessageResponse } from "../types/common";
import type {
  InvitationPreview,
  Organization,
  OrganizationInvitation,
  OrganizationMember,
} from "../types/organization";
import type { TokenResponse } from "../types/auth";
import { saveSession } from "./client";

function sessionFromToken(body: TokenResponse) {
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

export async function getCurrentOrganization(): Promise<Organization> {
  return apiFetch<Organization>("/organizations/current");
}

export async function updateOrganization(
  organizationId: string,
  payload: {
    name?: string;
    company_name?: string | null;
    description?: string | null;
    website?: string | null;
    industry?: string | null;
    country?: string | null;
    timezone?: string | null;
    logo_url?: string | null;
  },
): Promise<Organization> {
  return apiFetch<Organization>(`/organizations/${organizationId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function listOrganizationMembers(organizationId: string): Promise<OrganizationMember[]> {
  return apiFetch<OrganizationMember[]>(`/organizations/${organizationId}/members`);
}

export async function addOrganizationMember(
  organizationId: string,
  payload: { email: string; role: string },
): Promise<OrganizationMember> {
  return apiFetch<OrganizationMember>(`/organizations/${organizationId}/members`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function updateOrganizationMember(
  organizationId: string,
  membershipId: string,
  payload: { role?: string; is_active?: boolean },
): Promise<OrganizationMember> {
  return apiFetch<OrganizationMember>(`/organizations/${organizationId}/members/${membershipId}`, {
    method: "PATCH",
    body: JSON.stringify(payload),
  });
}

export async function deactivateOrganizationMember(
  organizationId: string,
  membershipId: string,
): Promise<MessageResponse> {
  return apiFetch<MessageResponse>(`/organizations/${organizationId}/members/${membershipId}`, {
    method: "DELETE",
  });
}

export async function listInvitations(organizationId: string): Promise<OrganizationInvitation[]> {
  return apiFetch<OrganizationInvitation[]>(`/organizations/${organizationId}/invitations`);
}

export async function createInvitation(
  organizationId: string,
  payload: { email: string; role: string },
): Promise<OrganizationInvitation> {
  return apiFetch<OrganizationInvitation>(`/organizations/${organizationId}/invitations`, {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

export async function revokeInvitation(
  organizationId: string,
  invitationId: string,
): Promise<OrganizationInvitation> {
  return apiFetch<OrganizationInvitation>(
    `/organizations/${organizationId}/invitations/${invitationId}/revoke`,
    { method: "POST" },
  );
}

export async function resendInvitation(
  organizationId: string,
  invitationId: string,
): Promise<OrganizationInvitation> {
  return apiFetch<OrganizationInvitation>(
    `/organizations/${organizationId}/invitations/${invitationId}/resend`,
    { method: "POST" },
  );
}

export async function previewInvitation(token: string): Promise<InvitationPreview> {
  return apiFetch<InvitationPreview>(`/invitations/preview?token=${encodeURIComponent(token)}`, {
    skipAuth: true,
    session: null,
  });
}

export async function acceptInvitation(
  token: string,
  payload: { password: string; full_name?: string },
): Promise<ReturnType<typeof sessionFromToken>> {
  const body = await apiFetch<TokenResponse>(
    `/invitations/accept?token=${encodeURIComponent(token)}`,
    {
      method: "POST",
      skipAuth: true,
      session: null,
      body: JSON.stringify(payload),
    },
  );
  const session = sessionFromToken(body);
  saveSession(session);
  return session;
}
