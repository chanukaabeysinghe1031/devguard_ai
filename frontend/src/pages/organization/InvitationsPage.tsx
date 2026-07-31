import { useState } from "react";
import { zodResolver } from "@hookform/resolvers/zod";
import { Copy, Plus } from "lucide-react";
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
import type { OrganizationInvitation } from "../../types/organization";
import { formatDate } from "../../utils/formatters";

const ROLE_OPTIONS = [
  { value: "viewer", label: "Viewer" },
  { value: "engineer", label: "Engineer" },
  { value: "organization_admin", label: "Organization Admin (Project Manager)" },
];

const schema = z.object({
  email: z.string().email("Enter a valid email"),
  role: z.enum(["viewer", "engineer", "organization_admin"]),
});
type FormValues = z.infer<typeof schema>;

export function InvitationsPage() {
  const { session } = useAuth();
  const organizationId = session?.organizationId ?? "";
  const queryClient = useQueryClient();
  const [isOpen, setIsOpen] = useState(false);
  const [serverError, setServerError] = useState<string | null>(null);
  const [copiedUrl, setCopiedUrl] = useState<string | null>(null);

  const invitationsQuery = useQuery({
    queryKey: queryKeys.organizationInvitations(organizationId),
    queryFn: () => organizationsApi.listInvitations(organizationId),
    enabled: Boolean(organizationId),
  });

  const invalidate = () =>
    queryClient.invalidateQueries({ queryKey: queryKeys.organizationInvitations(organizationId) });

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { role: "engineer" } });

  const createMutation = useMutation({
    mutationFn: (values: FormValues) => organizationsApi.createInvitation(organizationId, values),
    onSuccess: async (invite) => {
      reset();
      setIsOpen(false);
      invalidate();
      if (invite.invite_url) {
        await navigator.clipboard.writeText(invite.invite_url);
        setCopiedUrl(invite.invite_url);
      }
    },
    onError: (error) =>
      setServerError(error instanceof ApiError ? error.message : "Failed to create invitation."),
  });

  const revokeMutation = useMutation({
    mutationFn: (id: string) => organizationsApi.revokeInvitation(organizationId, id),
    onSuccess: invalidate,
  });

  const resendMutation = useMutation({
    mutationFn: (id: string) => organizationsApi.resendInvitation(organizationId, id),
    onSuccess: async (invite) => {
      invalidate();
      if (invite.invite_url) {
        await navigator.clipboard.writeText(invite.invite_url);
        setCopiedUrl(invite.invite_url);
      }
    },
  });

  const columns: Array<DataTableColumn<OrganizationInvitation>> = [
    {
      key: "email",
      header: "Invitee",
      render: (row) => <span className="text-sm text-text-primary">{row.email}</span>,
    },
    {
      key: "role",
      header: "Role",
      render: (row) => <Badge tone="neutral">{row.role.replace(/_/g, " ")}</Badge>,
    },
    {
      key: "status",
      header: "Status",
      render: (row) => <Badge tone={row.status === "pending" ? "primary" : "neutral"}>{row.status}</Badge>,
    },
    {
      key: "expires_at",
      header: "Expires",
      render: (row) => formatDate(row.expires_at),
    },
    {
      key: "actions",
      header: "",
      render: (row) =>
        row.status === "pending" || row.status === "expired" ? (
          <div className="flex gap-2">
            <Button variant="ghost" size="sm" onClick={() => resendMutation.mutate(row.id)}>
              <Copy className="mr-1 h-3.5 w-3.5" />
              Resend / copy
            </Button>
            {row.status === "pending" && (
              <Button variant="ghost" size="sm" onClick={() => revokeMutation.mutate(row.id)}>
                Revoke
              </Button>
            )}
          </div>
        ) : null,
    },
  ];

  return (
    <div>
      <PageHeader
        title="Invitations"
        description="Create secure invite links. Copy and share them — email delivery is not required for the MVP."
        actions={
          <Button leftIcon={<Plus className="h-4 w-4" />} onClick={() => setIsOpen(true)}>
            Create invitation
          </Button>
        }
      />

      {copiedUrl && (
        <Alert variant="success" className="mb-4" title="Invite link copied">
          <code className="break-all text-xs">{copiedUrl}</code>
        </Alert>
      )}

      <DataTable
        columns={columns}
        rows={invitationsQuery.data ?? []}
        rowKey={(row) => row.id}
        isLoading={invitationsQuery.isLoading}
        emptyTitle="No invitations yet"
      />

      <Modal
        isOpen={isOpen}
        onClose={() => setIsOpen(false)}
        title="Create invitation"
        footer={
          <>
            <Button variant="ghost" onClick={() => setIsOpen(false)}>
              Cancel
            </Button>
            <Button
              onClick={handleSubmit((values) => {
                setServerError(null);
                createMutation.mutate(values);
              })}
              isLoading={createMutation.isPending}
            >
              Create & copy link
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
