import { Navigate, Route, Routes } from "react-router-dom";

import { AppShell } from "../components/layout/AppShell";
import { AuthLayout } from "../layouts/AuthLayout";
import { LoginPage } from "../pages/auth/LoginPage";
import { RegisterPage } from "../pages/auth/RegisterPage";
import { DashboardPage } from "../pages/dashboard/DashboardPage";
import { ForbiddenPage } from "../pages/errors/ForbiddenPage";
import { NotFoundPage } from "../pages/errors/NotFoundPage";
import { EvaluationPage } from "../pages/evaluation/EvaluationPage";
import { HistoryPage } from "../pages/history/HistoryPage";
import { IncidentAnalysisPage } from "../pages/incidents/IncidentAnalysisPage";
import { IncidentCreatePage } from "../pages/incidents/IncidentCreatePage";
import { IncidentDetailPage } from "../pages/incidents/IncidentDetailPage";
import { IncidentsListPage } from "../pages/incidents/IncidentsListPage";
import { NotificationsPage } from "../pages/notifications/NotificationsPage";
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
import { UsersPage } from "../pages/admin/UsersPage";
import { NotificationSettingsPage } from "../pages/settings/NotificationSettingsPage";
import { OrganizationSettingsPage } from "../pages/settings/OrganizationSettingsPage";
import { SecuritySettingsPage } from "../pages/settings/SecuritySettingsPage";
import { SettingsLayout } from "../pages/settings/SettingsLayout";
import { ErrorPage } from "../pages/errors/ErrorPage";
import { RequireAuth, RequireRole } from "./routeGuards";

const ADMIN_ROLES = ["organization_owner", "organization_admin"] as const;

export function AppRouter() {
  return (
    <Routes>
      <Route element={<AuthLayout />}>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/register" element={<RegisterPage />} />
      </Route>

      <Route
        element={
          <RequireAuth>
            <AppShell />
          </RequireAuth>
        }
      >
        <Route path="/" element={<Navigate to="/dashboard" replace />} />
        <Route path="/dashboard" element={<DashboardPage />} />

        <Route path="/projects" element={<ProjectsListPage />} />
        <Route path="/projects/new" element={<ProjectCreatePage />} />
        <Route path="/projects/:projectId" element={<ProjectDetailPage />} />
        <Route path="/projects/:projectId/edit" element={<ProjectEditPage />} />

        <Route path="/pipeline-runs/:pipelineRunId" element={<PipelineRunDetailPage />} />

        <Route path="/incidents" element={<IncidentsListPage />} />
        <Route path="/incidents/new" element={<IncidentCreatePage />} />
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
          path="/admin/users"
          element={
            <RequireRole roles={[...ADMIN_ROLES]}>
              <UsersPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/models"
          element={
            <RequireRole roles={[...ADMIN_ROLES]}>
              <ModelsPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/system-health"
          element={
            <RequireRole roles={[...ADMIN_ROLES]}>
              <SystemHealthPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/audit"
          element={
            <RequireRole roles={[...ADMIN_ROLES]}>
              <AuditLogPage />
            </RequireRole>
          }
        />
        <Route
          path="/admin/evaluation"
          element={
            <RequireRole roles={[...ADMIN_ROLES]}>
              <AdminEvaluationPage />
            </RequireRole>
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
