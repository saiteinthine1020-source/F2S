import { useTranslation } from "react-i18next";
import { useParams } from "react-router-dom";

import { StatePanel } from "../components/StatePanel";

const allowedDestinations = new Set([
  "transactions",
  "add",
  "reports",
  "more",
  "submissions",
  "status",
  "review",
]);

export function ProtectedPlaceholderPage() {
  const { destination = "" } = useParams();
  const { t } = useTranslation();
  const key = allowedDestinations.has(destination) ? destination : "unavailable";
  return <StatePanel title={t(`navigation.${key}`)} description={t("protected.placeholder")} />;
}
