import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Plus } from "lucide-react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { z } from "zod";

import { ApiError } from "../../api/client";
import * as organizationsApi from "../../api/organizationsApi";
import { queryKeys } from "../../api/queryKeys";
import { Alert } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { DataTable, type DataTableColumn } from "../../components/ui/DataTable";
import { Input } from "../../components/ui/Input";
import { Modal } from "../../components/ui/Modal";
import { PageHeader } from "../../components/ui/PageHeader";
import { Select } from "../../components/ui/Select";
import { useAuth } from "../../hooks/useAuth";
import type { OrganizationMember } from "../../types/organization";
import { formatDate } from "../../utils/formatters";

const ROLE_OPTIONS = [
  { value: "viewer", label: "Viewer" },
  { value: "engineer", label: "Engineer" },
  { value: "organization_admin", label: "Organization Admin" },
  { value: "organization_owner", label: "Organization Owner" },
];

const inviteSchema = z.object({
  email: z.string().email("Enter a valid email"),
  role: z.enum(["viewer", "engineer", "organization_admin", "organization_owner"]),
});
type InviteFormValues = z.infer<typeof inviteSchema>;

export function MembersPage() {
  const { session } = useAuth();
  const organizationId = session?.organizationId ?? "";
  const queryClient = useQueryClient();
  const [isInviteOpen, setIsInviteOpen] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);

  const membersQuery = useQuery({
    queryKey: queryKeys.organizationMembers(organizationId),
    queryFn: () => organizationsApi.listOrganizationMembers(organizationId),
    enabled: Boolean(organizationId),
  });

  const invalidate = () => queryClient.invalidateQueries({ queryKey: queryKeys.organizationMembers(organizationId) });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<InviteFormValues>({ resolver: zodResolver(inviteSchema), defaultValues: { role: "viewer" } });

  const inviteMutation = useMutation({
    mutationFn: (values: InviteFormValues) => organizationsApi.addOrganizationMember(organizationId, values),
    onSuccess: () => {
      reset();
      setIsInviteOpen(false);
      invalidate();
    },
    onError: (error) => setServerError(error instanceof ApiError ? error.message : "Failed to add member."),
  });

  const roleMutation = useMutation({
    mutationFn: ({ membershipId, role }: { membershipId: string; role: string }) =>
      organizationsApi.updateOrganizationMember(organizationId, membershipId, { role }),
    onSuccess: invalidate,
  });

  const deactivateMutation = useMutation({
    mutationFn: (membershipId: string) => organizationsApi.deactivateOrganizationMember(organizationId, membershipId),
    onSuccess: invalidate,
  });

  const columns: Array<DataTableColumn<OrganizationMember>> = [
    {
      key: "name",
      header: "Member",
      render: (member) => (
        <div>
          <p className="font-medium text-text-primary">{member.full_name}</p>
          <p className="text-xs text-text-muted">{member.email}</p>
        </div>
      ),
    },
    {
      key: "role",
      header: "Role",
      render: (member) => (
        <Select
          value={member.role}
          options={ROLE_OPTIONS}
          onChange={(event) => roleMutation.mutate({ membershipId: member.id, role: event.target.value })}
          className="h-9 w-48"
        />
      ),
    },
    {
      key: "status",
      header: "Status",
      render: (member) => <Badge tone={member.is_active ? "success" : "neutral"}>{member.is_active ? "Active" : "Inactive"}</Badge>,
    },
    { key: "joined_at", header: "Joined", render: (member) => formatDate(member.joined_at) },
    {
      key: "actions",
      header: "",
      render: (member) =>
        member.is_active && (
          <Button variant="ghost" size="sm" onClick={() => deactivateMutation.mutate(member.id)}>
            Deactivate
          </Button>
        ),
    },
  ];

  return (
    <div>
      <PageHeader
        title="Members"
        description="Manage organization members and roles. Prefer invitations for new users."
        actions={
          <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsInviteOpen(true)}>
            Add existing user
          </Button>
        }
      />

      <DataTable
        columns={columns}
        rows={membersQuery.data ?? []}
        rowKey={(row) => row.id}
        isLoading={membersQuery.isLoading}
        emptyTitle="No members found"
      />

      <Modal
        isOpen={isInviteOpen}
        onClose={() => setIsInviteOpen(false)}
        title="Add organization member"
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsInviteOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit((values) => {
                setServerError(null);
                inviteMutation.mutate(values);
              })}
              isLoading={inviteMutation.isPending}
            >
              Add member
            </Button>
          </>
        }
      >
        {serverError && (
          <Alert variant="danger" className="mb-4">
            {serverError}
          </Alert>
        )}
        <form className="flex flex-col gap-4" noValidate>
          <Input label="Email" type="email" required error={errors.email?.message} {...register("email")} />
          <Select label="Role" options={ROLE_OPTIONS} {...register("role")} />
        </form>
      </Modal>
    </div>
  );
}
