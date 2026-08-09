import { useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Outlet } from "react-router-dom";

export function AppShell() {
  const { i18n, t } = useTranslation();

  useEffect(() => {
    document.documentElement.lang = i18n.resolvedLanguage ?? "shn";
    document.title = t("app.name");
  }, [i18n.resolvedLanguage, t]);

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main-content">
        {t("accessibility.skipToMain")}
      </a>
      <header className="app-header">
        <div className="app-header__inner">
          <span className="app-mark" aria-label={t("app.name")}>
            {t("app.name")}
          </span>
        </div>
      </header>
      <main id="main-content" className="app-main" tabIndex={-1}>
        <Outlet />
      </main>
    </div>
  );
}
