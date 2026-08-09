import { Navigate } from "react-router-dom";

import { ErrorState, LoadingState } from "../components/StatePanel";
import { useAuth } from "../auth/AuthContext";

export function GatewayPage() {
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
    return <Navigate replace to="/login" />;
  }
  return <Navigate replace to="/app" />;
}
