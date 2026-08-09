import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { AdminBoundary } from "../auth/AdminBoundary";
import { ProtectedBoundary } from "../auth/ProtectedBoundary";
import { PublicBoundary } from "../auth/PublicBoundary";
import { AppShell } from "../components/AppShell";
import { ActivationPage } from "../pages/ActivationPage";
import { AdministrationPage } from "../pages/AdministrationPage";
import { BootstrapPage } from "../pages/BootstrapPage";
import { GatewayPage } from "../pages/GatewayPage";
import { LoginPage } from "../pages/LoginPage";
import { MemberAdministrationPage } from "../pages/MemberAdministrationPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { OwnershipConfirmationPage } from "../pages/OwnershipConfirmationPage";
import { OwnershipTransferPage } from "../pages/OwnershipTransferPage";
import { PasswordChangePage } from "../pages/PasswordChangePage";
import { ProtectedHomePage } from "../pages/ProtectedHomePage";
import { ProtectedPlaceholderPage } from "../pages/ProtectedPlaceholderPage";
import { RecoveryConfirmationPage } from "../pages/RecoveryConfirmationPage";
import { RecoveryPage } from "../pages/RecoveryPage";
import { WorkspaceSettingsPage } from "../pages/WorkspaceSettingsPage";

export const appRoutes: RouteObject[] = [
  {
    path: "/",
    element: <AppShell />,
    children: [
      { index: true, element: <GatewayPage /> },
      { path: "setup", element: <BootstrapPage /> },
      {
        element: <PublicBoundary />,
        children: [
          { path: "login", element: <LoginPage /> },
          { path: "activate", element: <ActivationPage /> },
          { path: "recovery", element: <RecoveryPage /> },
          { path: "recovery/confirm", element: <RecoveryConfirmationPage /> },
        ],
      },
      {
        path: "app",
        element: <ProtectedBoundary />,
        children: [
          { index: true, element: <ProtectedHomePage /> },
          { path: "password", element: <PasswordChangePage /> },
          { path: "ownership/confirm", element: <OwnershipConfirmationPage /> },
          {
            path: "admin",
            element: <AdminBoundary />,
            children: [
              { index: true, element: <AdministrationPage /> },
              { path: "settings", element: <WorkspaceSettingsPage /> },
              { path: "members", element: <MemberAdministrationPage /> },
              { path: "ownership", element: <OwnershipTransferPage /> },
            ],
          },
          { path: ":destination", element: <ProtectedPlaceholderPage /> },
        ],
      },
      { path: "*", element: <NotFoundPage /> },
    ],
  },
];

export function createAppRouter() {
  return createBrowserRouter(appRoutes);
}
