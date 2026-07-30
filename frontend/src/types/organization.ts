export interface Organization {
  id: string;
  name: string;
  slug: string;
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
