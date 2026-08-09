import { useTranslation } from "react-i18next";

import { useAuth } from "../auth/AuthContext";
import { StatePanel } from "../components/StatePanel";

export function ProtectedHomePage() {
  const { state } = useAuth();
  const { t } = useTranslation();
  if (state.status !== "authenticated") {
    return null;
  }
  return (
    <StatePanel
      eyebrow={t(`roles.${state.selected.membership.role}`)}
      title={t("protected.home.title")}
      description={t("protected.home.description")}
      action={<p className="language-notice">{t("protected.home.authorizationNotice")}</p>}
    />
  );
}
