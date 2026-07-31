export interface Organization {
  id: string;
  name: string;
  slug: string;
  company_name: string | null;
  description: string | null;
  website: string | null;
  industry: string | null;
  country: string | null;
  timezone: string;
  logo_url: string | null;
  plan: string;
  status: string;
  created_at: string | null;
  updated_at: string | null;
}

export interface OrganizationMember {
  id: string;
  user_id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  joined_at: string;
}

export interface OrganizationInvitation {
  id: string;
  organization_id: string;
  email: string;
  role: string;
  status: string;
  invited_by: string | null;
  expires_at: string;
  accepted_at: string | null;
  revoked_at: string | null;
  created_at: string | null;
  invite_url?: string | null;
  token?: string;
}

export interface InvitationPreview {
  organization_name: string;
  organization_slug: string;
  email: string;
  role: string;
  status: string;
  expires_at: string;
  is_expired: boolean;
  user_exists: boolean;
}
