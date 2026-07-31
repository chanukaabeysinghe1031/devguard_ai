import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { AuthLayout } from "../layouts/AuthLayout";
import { AcceptInvitationPage } from "../pages/auth/AcceptInvitationPage";
import { BrandSplashPage } from "../pages/auth/BrandSplashPage";
import { CreatingWorkspacePage } from "../pages/auth/CreatingWorkspacePage";
import { JoiningOrganizationPage } from "../pages/auth/JoiningOrganizationPage";
import { LoginPage } from "../pages/auth/LoginPage";
import { RegisterPage } from "../pages/auth/RegisterPage";
import { SigningInPage } from "../pages/auth/SigningInPage";
import { DashboardPage } from "../pages/dashboard/DashboardPage";
import { ForbiddenPage } from "../pages/errors/ForbiddenPage";
import { NotFoundPage } from "../pages/errors/NotFoundPage";
import { EvaluationPage } from "../pages/evaluation/EvaluationPage";
import { HistoryPage } from "../pages/history/HistoryPage";
import { IncidentAnalysisPage } from "../pages/incidents/IncidentAnalysisPage";
import { IncidentCreatePage } from "../pages/incidents/IncidentCreatePage";
import { IncidentDetailPage } from "../pages/incidents/IncidentDetailPage";
import { IncidentsListPage } from "../pages/incidents/IncidentsListPage";
import { GitHubIntegrationPage } from "../pages/integrations/GitHubIntegrationPage";
import { GitHubSetupCallbackPage } from "../pages/integrations/GitHubSetupCallbackPage";
import { ProjectIntegrationsPage } from "../pages/integrations/ProjectIntegrationsPage";
import { NotificationsPage } from "../pages/notifications/NotificationsPage";
import { InvitationsPage } from "../pages/organization/InvitationsPage";
import { MembersPage } from "../pages/organization/MembersPage";
import { RolesPage } from "../pages/organization/RolesPage";
import { PipelineRunDetailPage } from "../pages/pipelineRuns/PipelineRunDetailPage";
import { ProfilePage } from "../pages/profile/ProfilePage";
import { ProjectCreatePage } from "../pages/projects/ProjectCreatePage";
import { ProjectDetailPage } from "../pages/projects/ProjectDetailPage";
import { ProjectEditPage } from "../pages/projects/ProjectEditPage";
import { ProjectsListPage } from "../pages/projects/ProjectsListPage";
import { ReportDetailPage } from "../pages/reports/ReportDetailPage";
import { ReportsListPage } from "../pages/reports/ReportsListPage";
import { AuditLogPage } from "../pages/admin/AuditLogPage";
import { AdminEvaluationPage } from "../pages/admin/AdminEvaluationPage";
import { ModelsPage } from "../pages/admin/ModelsPage";
import { SystemHealthPage } from "../pages/admin/SystemHealthPage";
import { NotificationSettingsPage } from "../pages/settings/NotificationSettingsPage";
import { OrganizationSettingsPage } from "../pages/settings/OrganizationSettingsPage";
import { SecuritySettingsPage } from "../pages/settings/SecuritySettingsPage";
import { SettingsLayout } from "../pages/settings/SettingsLayout";
import { ErrorPage } from "../pages/errors/ErrorPage";
import { RequireBrandSplash } from "./RequireBrandSplash";
import { RequireAuth, RequirePlatformAdmin, RequireRole } from "./routeGuards";

const ORG_ADMIN_ROLES = ["organization_owner", "organization_admin"] as const;
const WRITER_ROLES = ["organization_owner", "organization_admin", "engineer"] as const;

export function AppRouter() {
  return (
    <Routes>
      <Route path="/welcome" element={<BrandSplashPage />} />
      <Route path="/" element={<Navigate to="/welcome?next=/login" replace />} />

      <Route
        element={
          <RequireBrandSplash>
            <AuthLayout />
          </RequireBrandSplash>
        }
      >
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
        <Route path="/invitations/accept" element={<AcceptInvitationPage />} />
      </Route>

      <Route path="/auth/signing-in" element={<SigningInPage />} />
      <Route path="/auth/creating-workspace" element={<CreatingWorkspacePage />} />
      <Route path="/auth/joining-organization" element={<JoiningOrganizationPage />} />

      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/dashboard" element={<DashboardPage />} />

        <Route path="/projects" element={<ProjectsListPage />} />
        <Route
          path="/projects/new"
          element={
            <RequireRole roles={[...WRITER_ROLES]}>
              <ProjectCreatePage />
            </RequireRole>
          }
        />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route
          path="/projects/:projectId/edit"
          element={
            <RequireRole roles={[...WRITER_ROLES]}>
              <ProjectEditPage />
            </RequireRole>
          }
        />
        <Route path="/projects/:projectId/integrations" element={<ProjectIntegrationsPage />} />
        <Route path="/projects/:projectId/integrations/github" element={<GitHubIntegrationPage />} />

        <Route path="/integrations/github/setup" element={<GitHubSetupCallbackPage />} />

        <Route path="/pipeline-runs/:pipelineRunId" element={<PipelineRunDetailPage />} />

        <Route path="/incidents" element={<IncidentsListPage />} />
        <Route
          path="/incidents/new"
          element={
            <RequireRole roles={[...WRITER_ROLES]}>
              <IncidentCreatePage />
            </RequireRole>
          }
        />
        <Route path="/incidents/:incidentId" element={<IncidentDetailPage />} />
        <Route path="/incidents/:incidentId/analysis" element={<IncidentAnalysisPage />} />

        <Route path="/history" element={<HistoryPage />} />
        <Route path="/reports" element={<ReportsListPage />} />
        <Route path="/reports/:reportId" element={<ReportDetailPage />} />
        <Route path="/notifications" element={<NotificationsPage />} />
        <Route path="/evaluation" element={<EvaluationPage />} />

        <Route path="/settings" element={<SettingsLayout />}>
          <Route index element={<Navigate to="/settings/organization" replace />} />
          <Route path="organization" element={<OrganizationSettingsPage />} />
          <Route path="security" element={<SecuritySettingsPage />} />
          <Route path="notifications" element={<NotificationSettingsPage />} />
        </Route>
        <Route path="/profile" element={<ProfilePage />} />

        <Route
          path="/organization/members"
          element={
            <RequireRole roles={[...ORG_ADMIN_ROLES]}>
              <MembersPage />
            </RequireRole>
          }
        />
        <Route
          path="/organization/invitations"
          element={
            <RequireRole roles={[...ORG_ADMIN_ROLES]}>
              <InvitationsPage />
            </RequireRole>
          }
        />
        <Route
          path="/organization/roles"
          element={
            <RequireRole roles={[...ORG_ADMIN_ROLES]}>
              <RolesPage />
            </RequireRole>
          }
        />

        <Route path="/admin/users" element={<Navigate to="/organization/members" replace />} />
        <Route path="/admin/models" element={<Navigate to="/system/models" replace />} />
        <Route path="/admin/system-health" element={<Navigate to="/system/health" replace />} />
        <Route path="/admin/audit" element={<Navigate to="/system/audit" replace />} />
        <Route path="/admin/evaluation" element={<Navigate to="/system/evaluation" replace />} />

        <Route
          path="/system/health"
          element={
            <RequirePlatformAdmin>
              <SystemHealthPage />
            </RequirePlatformAdmin>
          }
        />
        <Route
          path="/system/models"
          element={
            <RequirePlatformAdmin>
              <ModelsPage />
            </RequirePlatformAdmin>
          }
        />
        <Route
          path="/system/audit"
          element={
            <RequirePlatformAdmin>
              <AuditLogPage />
            </RequirePlatformAdmin>
          }
        />
        <Route
          path="/system/evaluation"
          element={
            <RequirePlatformAdmin>
              <AdminEvaluationPage />
            </RequirePlatformAdmin>
          }
        />

        <Route path="/diagnose" element={<Navigate to="/incidents/new" replace />} />
        <Route path="/403" element={<ForbiddenPage />} />
        <Route path="/error" element={<ErrorPage />} />
        <Route path="*" element={<NotFoundPage />} />
      </Route>
    </Routes>
  );
}
