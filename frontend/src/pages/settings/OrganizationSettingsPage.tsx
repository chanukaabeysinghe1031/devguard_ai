import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { ApiError } from "../../api/client";
import * as organizationsApi from "../../api/organizationsApi";
import { queryKeys } from "../../api/queryKeys";
import { Alert } from "../../components/ui/Alert";
import { Badge } from "../../components/ui/Badge";
import { Button } from "../../components/ui/Button";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { Input } from "../../components/ui/Input";
import { SkeletonCard } from "../../components/ui/Skeleton";
import { useAuth } from "../../hooks/useAuth";
import { formatDate, titleCase } from "../../utils/formatters";

interface FormValues {
  name: string;
}

export function OrganizationSettingsPage() {
  const { hasAnyRole } = useAuth();
  const canEdit = hasAnyRole(["organization_owner", "organization_admin"]);
  const queryClient = useQueryClient();

  const orgQuery = useQuery({
    queryKey: queryKeys.organization(),
    queryFn: () => organizationsApi.getCurrentOrganization(),
  });

  const membersQuery = useQuery({
    queryKey: queryKeys.organizationMembers(orgQuery.data?.id ?? ""),
    queryFn: () => organizationsApi.listOrganizationMembers(orgQuery.data!.id),
    enabled: Boolean(orgQuery.data?.id),
  });

  const { register, handleSubmit, reset } = useForm<FormValues>();

  useEffect(() => {
    if (orgQuery.data) reset({ name: orgQuery.data.name });
  }, [orgQuery.data, reset]);

  const mutation = useMutation({
    mutationFn: (values: FormValues) => organizationsApi.updateOrganization(orgQuery.data!.id, values),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: queryKeys.organization() }),
  });

  if (orgQuery.isLoading) return <SkeletonCard />;
  if (orgQuery.isError || !orgQuery.data) {
    return <Alert variant="danger">Failed to load organization details.</Alert>;
  }

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader title="Organization" subtitle={`Created ${formatDate(orgQuery.data.created_at)}`} />
        <CardBody>
          {mutation.isError && (
            <Alert variant="danger" className="mb-4">
              {mutation.error instanceof ApiError ? mutation.error.message : "Failed to update organization."}
            </Alert>
          )}
          <form
            onSubmit={handleSubmit((values) => mutation.mutate(values))}
            className="flex max-w-md flex-col gap-4"
          >
            <Input label="Organization name" disabled={!canEdit} {...register("name")} />
            <Input label="Slug" value={orgQuery.data.slug} disabled />
            <Input label="Plan" value={titleCase(orgQuery.data.plan)} disabled />
            {canEdit && (
              <div className="flex justify-end">
                <Button type="submit" isLoading={mutation.isPending}>
                  Save changes
                </Button>
              </div>
            )}
          </form>
        </CardBody>
      </Card>

      <Card>
        <CardHeader title="Members" />
        <CardBody className="!p-0">
          {membersQuery.isLoading ? (
            <div className="p-5">
              <SkeletonCard />
            </div>
          ) : (
            <ul className="divide-y divide-border">
              {membersQuery.data?.map((member) => (
                <li key={member.id} className="flex items-center justify-between px-5 py-3">
                  <div>
                    <p className="text-sm font-medium text-text-primary">{member.full_name}</p>
                    <p className="text-xs text-text-muted">{member.email}</p>
                  </div>
                  <div className="flex items-center gap-2">
                    <Badge tone="neutral">{titleCase(member.role)}</Badge>
                    {!member.is_active && <Badge tone="warning">Inactive</Badge>}
                  </div>
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
    </div>
  );
}
