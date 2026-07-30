export type OrganizationRole =
  | "organization_owner"
  | "organization_admin"
  | "engineer"
  | "viewer";

export type PlatformRole = "platform_admin" | "none";

export interface Membership {
  organization_id: string;
  organization_slug: string;
  organization_name: string;
  role: OrganizationRole;
  is_active: boolean;
}

export interface UserPublic {
  id: string;
  email: string;
  full_name: string;
  avatar_url: string | null;
  role: string;
  platform_role: PlatformRole;
  is_active: boolean;
  last_login_at: string | null;
  created_at: string | null;
  memberships: Membership[];
}

export interface TokenResponse {
  access_token: string;
  refresh_token: string;
  token_type: string;
  expires_in: number;
  user: UserPublic;
}

export interface AccessTokenResponse {
  access_token: string;
  token_type: string;
  expires_in: number;
  refresh_token?: string | null;
}

export interface LoginRequest {
  email: string;
  password: string;
}

export interface RegisterRequest {
  email: string;
  password: string;
  full_name: string;
}

export interface ChangePasswordRequest {
  current_password: string;
  new_password: string;
}

/** Session persisted client-side (sessionStorage). Never persisted to localStorage. */
export interface AuthSession {
  accessToken: string;
  refreshToken: string;
  organizationId: string;
  email: string;
  fullName?: string;
  role?: OrganizationRole;
  platformRole?: PlatformRole;
  userId?: string;
}
