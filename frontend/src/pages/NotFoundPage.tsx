import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { StatePanel } from "../components/StatePanel";

export function NotFoundPage() {
  const { t } = useTranslation();
  return (
    <StatePanel
      title={t("notFound.title")}
      description={t("notFound.description")}
      action={
        <Link className="button" to="/">
          {t("notFound.backHome")}
        </Link>
      }
    />
  );
}
