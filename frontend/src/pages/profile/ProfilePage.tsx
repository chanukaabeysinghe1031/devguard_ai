import { useQuery } from "@tanstack/react-query";

import { fetchCurrentUser } from "../../api/authApi";
import { queryKeys } from "../../api/queryKeys";
import { Avatar } from "../../components/ui/Avatar";
import { Badge } from "../../components/ui/Badge";
import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { ErrorRetryAlert } from "../../components/ui/Alert";
import { KeyValueList } from "../../components/ui/KeyValueList";
import { PageHeader } from "../../components/ui/PageHeader";
import { SkeletonCard } from "../../components/ui/Skeleton";
import { formatDateTime, titleCase } from "../../utils/formatters";

export function ProfilePage() {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: queryKeys.me(),
    queryFn: fetchCurrentUser,
  });

  return (
    <div>
      <PageHeader title="Profile" description="Your account details and organization memberships." />

      {isLoading ? (
        <SkeletonCard />
      ) : isError || !data ? (
        <ErrorRetryAlert message="Failed to load profile." onRetry={() => refetch()} />
      ) : (
        <div className="flex flex-col gap-6">
          <Card>
            <CardBody className="flex items-center gap-4">
              <Avatar name={data.full_name} src={data.avatar_url} size="lg" />
              <div>
                <p className="text-lg font-semibold text-text-primary">{data.full_name}</p>
                <p className="text-sm text-text-muted">{data.email}</p>
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Account details" />
            <CardBody>
              <KeyValueList
                columns={2}
                items={[
                  { label: "Platform role", value: titleCase(data.platform_role) },
                  { label: "Account status", value: data.is_active ? "Active" : "Disabled" },
                  { label: "Last login", value: formatDateTime(data.last_login_at) },
                  { label: "Member since", value: formatDateTime(data.created_at) },
                ]}
              />
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Organization memberships" />
            <CardBody className="!p-0">
              <ul className="divide-y divide-border">
                {data.memberships.map((membership) => (
                  <li key={membership.organization_id} className="flex items-center justify-between px-5 py-3">
                    <div>
                      <p className="text-sm font-medium text-text-primary">{membership.organization_name}</p>
                      <p className="text-xs text-text-muted">{membership.organization_slug}</p>
                    </div>
                    <div className="flex items-center gap-2">
                      <Badge tone="neutral">{titleCase(membership.role)}</Badge>
                      {!membership.is_active && <Badge tone="warning">Inactive</Badge>}
                    </div>
                  </li>
                ))}
              </ul>
            </CardBody>
          </Card>
        </div>
      )}
    </div>
  );
}
