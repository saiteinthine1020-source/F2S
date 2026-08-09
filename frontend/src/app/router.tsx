import { createBrowserRouter, type RouteObject } from "react-router-dom";

import { ProtectedBoundary } from "../auth/ProtectedBoundary";
import { PublicBoundary } from "../auth/PublicBoundary";
import { AppShell } from "../components/AppShell";
import { ActivationPage } from "../pages/ActivationPage";
import { BootstrapPage } from "../pages/BootstrapPage";
import { GatewayPage } from "../pages/GatewayPage";
import { LoginPage } from "../pages/LoginPage";
import { NotFoundPage } from "../pages/NotFoundPage";
import { PasswordChangePage } from "../pages/PasswordChangePage";
import { ProtectedHomePage } from "../pages/ProtectedHomePage";
import { ProtectedPlaceholderPage } from "../pages/ProtectedPlaceholderPage";
import { RecoveryConfirmationPage } from "../pages/RecoveryConfirmationPage";
import { RecoveryPage } from "../pages/RecoveryPage";

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
