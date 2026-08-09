import { Navigate, Outlet } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/StatePanel";
import { useAuth } from "./AuthContext";

export function PublicBoundary() {
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
  if (state.status === "authenticated" || state.status === "selecting-workspace") {
    return <Navigate replace to="/app" />;
  }
  return <Outlet />;
}
