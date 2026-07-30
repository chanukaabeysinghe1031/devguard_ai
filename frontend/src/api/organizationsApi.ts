import { apiFetch } from "./client";
import type { MessageResponse } from "../types/common";
import type { Organization, OrganizationMember } from "../types/organization";

export async function getCurrentOrganization(): Promise<Organization> {
  return apiFetch<Organization>("/organizations/current");
}

export async function updateOrganization(
  organizationId: string,
  payload: { name?: string },
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
