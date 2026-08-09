import { Navigate, Outlet } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/StatePanel";
import { WorkspaceSelectionPage } from "../pages/WorkspaceSelectionPage";
import { ProtectedShell } from "../components/ProtectedShell";
import { useAuth } from "./AuthContext";

export function ProtectedBoundary() {
  const { retryStartup, state } = useAuth();
  if (state.status === "checking") {
    return <LoadingState />;
  }
  if (state.status === "unavailable") {
    return <ErrorState onRetry={() => void retryStartup()} />;
  }
  if (state.status === "bootstrap") {
    return <Navigate replace to="/setup" />;
  }
  if (state.status === "anonymous") {
    return <Navigate replace to="/login" state={{ reason: state.reason }} />;
  }
  if (state.status === "selecting-workspace") {
    return <WorkspaceSelectionPage />;
  }
  return (
    <ProtectedShell>
      <Outlet />
    </ProtectedShell>
  );
}
