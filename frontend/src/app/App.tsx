import { useMemo } from "react";
import { RouterProvider } from "react-router-dom";

import { loadRuntimeConfig } from "../config/runtime";
import { AppErrorBoundary } from "./AppErrorBoundary";
import { AppProviders } from "./AppProviders";
import { createAppRouter } from "./router";

function ConfiguredApplication() {
  const config = useMemo(() => loadRuntimeConfig(import.meta.env), []);
  const router = useMemo(() => createAppRouter(), []);
  return (
    <AppProviders config={config}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}

export function App() {
  return (
    <AppErrorBoundary>
      <ConfiguredApplication />
    </AppErrorBoundary>
  );
}
