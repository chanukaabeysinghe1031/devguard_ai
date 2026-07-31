import { Card, CardBody, CardHeader } from "../../components/ui/Card";
import { PageHeader } from "../../components/ui/PageHeader";

const MATRIX = [
  {
    role: "organization_owner",
    label: "Organization Owner",
    capabilities: [
      "Full organization control",
      "Invite / remove members",
      "Manage GitHub integrations",
      "Manage projects and incidents",
    ],
  },
  {
    role: "organization_admin",
    label: "Organization Admin (= Project Manager for MVP)",
    capabilities: [
      "Invite / remove members",
      "Configure GitHub integrations",
      "Manage projects and incidents",
      "View analytics",
    ],
  },
  {
    role: "engineer",
    label: "Engineer",
    capabilities: [
      "Create incidents and upload logs",
      "Run AI analysis",
      "Resolve and comment on incidents",
      "Cannot configure GitHub or invite users",
    ],
  },
  {
    role: "viewer",
    label: "Viewer",
    capabilities: ["Read-only access to projects, incidents, and reports"],
  },
];

export function RolesPage() {
  return (
    <div>
      <PageHeader
        title="Roles"
        description="Frozen organization roles (ADR-013). Platform administrators use a separate System menu."
      />
      <div className="grid gap-4 md:grid-cols-2">
        {MATRIX.map((item) => (
          <Card key={item.role}>
            <CardHeader title={item.label} subtitle={item.role} />
            <CardBody>
              <ul className="list-disc space-y-1 pl-5 text-sm text-text-secondary">
                {item.capabilities.map((cap) => (
                  <li key={cap}>{cap}</li>
                ))}
              </ul>
            </CardBody>
          </Card>
        ))}
      </div>
    </div>
  );
}
