import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { BrowserRouter, Navigate, Route, Routes, useLocation } from "react-router-dom";
import { Spinner } from "./components/ui";
import { AuthProvider, useAuth } from "./hooks/useAuth";
import { PortalProvider } from "./hooks/usePortal";
import { ToastProvider } from "./hooks/useToast";
import { AppLayout } from "./layouts/AppLayout";
import { PortalLayout } from "./layouts/PortalLayout";
import { AssistantPage } from "./pages/AssistantPage";
import { ActivatePage, ForgotPasswordPage, LoginPage, RegisterPage, ResetPasswordPage } from "./pages/auth/AuthPages";
import { ClientDetailPage } from "./pages/ClientDetailPage";
import { ClientsPage } from "./pages/ClientsPage";
import { CompliancePage } from "./pages/CompliancePage";
import { DashboardPage } from "./pages/DashboardPage";
import { DocumentDetailPage } from "./pages/DocumentDetailPage";
import { DocumentRequestsPage } from "./pages/DocumentRequestsPage";
import { DocumentsPage } from "./pages/DocumentsPage";
import { EmployeesPage } from "./pages/EmployeesPage";
import { InvoicesPage } from "./pages/InvoicesPage";
import { OnboardingPage } from "./pages/OnboardingPage";
import { PortalLinkPage, PortalLoginPage } from "./pages/portal/PortalAuth";
import {
  PortalDashboard, PortalDocuments, PortalInvoices, PortalMessages, PortalPayments, PortalProfile, PortalRequests, PortalSupport, PortalTasks,
} from "./pages/portal/PortalPages";
import { ReportsPage } from "./pages/ReportsPage";
import { SettingsPage } from "./pages/SettingsPage";
import { SupportPage } from "./pages/SupportPage";
import { TasksPage } from "./pages/TasksPage";
import { WhatsAppPage } from "./pages/WhatsAppPage";

export function makeQueryClient() {
  return new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: 1, refetchOnWindowFocus: false } } });
}

function RequireStaff({ children }: { children: ReactNode }) {
  const { me, loading } = useAuth();
  const loc = useLocation();
  if (loading) return <Spinner label="Loading ProDesk…" />;
  if (!me) return <Navigate to="/login" replace state={{ from: loc.pathname }} />;
  return <>{children}</>;
}

function RequirePerm({ perm, children }: { perm: string; children: ReactNode }) {
  const { can } = useAuth();
  return can(perm) ? <>{children}</> : <div className="rounded-lg border border-ink-200 bg-white p-8 text-center text-sm text-ink-600">You don't have access to this section. Ask your firm admin.</div>;
}

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/login" element={<LoginPage />} />
      <Route path="/register" element={<RegisterPage />} />
      <Route path="/forgot-password" element={<ForgotPasswordPage />} />
      <Route path="/reset-password" element={<ResetPasswordPage />} />
      <Route path="/activate" element={<ActivatePage />} />

      <Route path="/portal/login" element={<PortalLoginPage />} />
      <Route path="/portal/link/:token" element={<PortalLinkPage />} />
      <Route path="/portal" element={<PortalLayout />}>
        <Route index element={<PortalDashboard />} />
        <Route path="documents" element={<PortalDocuments />} />
        <Route path="requests" element={<PortalRequests />} />
        <Route path="tasks" element={<PortalTasks />} />
        <Route path="invoices" element={<PortalInvoices />} />
        <Route path="payments" element={<PortalPayments />} />
        <Route path="messages" element={<PortalMessages />} />
        <Route path="support" element={<PortalSupport />} />
        <Route path="profile" element={<PortalProfile />} />
      </Route>

      <Route element={<RequireStaff><AppLayout /></RequireStaff>}>
        <Route path="/" element={<DashboardPage />} />
        <Route path="/onboarding" element={<RequirePerm perm="SETTINGS_MANAGE"><OnboardingPage /></RequirePerm>} />
        <Route path="/clients" element={<ClientsPage />} />
        <Route path="/clients/:id" element={<ClientDetailPage />} />
        <Route path="/documents" element={<RequirePerm perm="DOCUMENT_VIEW"><DocumentsPage /></RequirePerm>} />
        <Route path="/documents/:id" element={<RequirePerm perm="DOCUMENT_VIEW"><DocumentDetailPage /></RequirePerm>} />
        <Route path="/tasks" element={<RequirePerm perm="TASK_VIEW"><TasksPage /></RequirePerm>} />
        <Route path="/tasks/:id" element={<Navigate to="/tasks" replace />} />
        <Route path="/document-requests" element={<RequirePerm perm="TASK_VIEW"><DocumentRequestsPage /></RequirePerm>} />
        <Route path="/document-requests/:id" element={<Navigate to="/document-requests" replace />} />
        <Route path="/whatsapp" element={<RequirePerm perm="WHATSAPP_VIEW"><WhatsAppPage /></RequirePerm>} />
        <Route path="/compliance" element={<RequirePerm perm="TASK_VIEW"><CompliancePage /></RequirePerm>} />
        <Route path="/invoices" element={<RequirePerm perm="INVOICE_VIEW"><InvoicesPage /></RequirePerm>} />
        <Route path="/invoices/:id" element={<Navigate to="/invoices" replace />} />
        <Route path="/reports" element={<RequirePerm perm="REPORT_VIEW"><ReportsPage /></RequirePerm>} />
        <Route path="/employees" element={<RequirePerm perm="USER_MANAGE"><EmployeesPage /></RequirePerm>} />
        <Route path="/assistant" element={<AssistantPage />} />
        <Route path="/support" element={<SupportPage />} />
        <Route path="/settings" element={<RequirePerm perm="SETTINGS_MANAGE"><SettingsPage /></RequirePerm>} />
        <Route path="/settings/*" element={<Navigate to="/settings" replace />} />
      </Route>
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export function Providers({ children, client }: { children: ReactNode; client?: QueryClient }) {
  return (
    <QueryClientProvider client={client ?? makeQueryClient()}>
      <ToastProvider>
        <AuthProvider>
          <PortalProvider>{children}</PortalProvider>
        </AuthProvider>
      </ToastProvider>
    </QueryClientProvider>
  );
}

export default function App() {
  return (
    <BrowserRouter>
      <Providers><AppRoutes /></Providers>
    </BrowserRouter>
  );
}
