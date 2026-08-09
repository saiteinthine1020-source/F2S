import { useTranslation } from "react-i18next";
import { Navigate, Outlet, useLocation } from "react-router-dom";

import { StatePanel } from "../components/StatePanel";
import { useAuth } from "./AuthContext";

export function AdminBoundary() {
  const { state } = useAuth();
  const { t } = useTranslation();
  const location = useLocation();
  if (state.status !== "authenticated") {
    return <Navigate to="/login" replace state={{ from: location.pathname }} />;
  }
  if (state.selected.membership.role !== "ADMIN") {
    return (
      <StatePanel
        tone="danger"
        title={t("administration.denied.title")}
        description={t("administration.denied.description")}
      />
    );
  }
  return <Outlet />;
}
