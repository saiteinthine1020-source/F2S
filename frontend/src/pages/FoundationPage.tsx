import { useTranslation } from "react-i18next";

import { StatePanel } from "../components/StatePanel";

export function FoundationPage() {
  const { t } = useTranslation();
  return (
    <StatePanel
      eyebrow={t("foundation.eyebrow")}
      title={t("foundation.title")}
      description={t("foundation.description")}
      action={<p className="language-notice">{t("foundation.languageNotice")}</p>}
    />
  );
}
