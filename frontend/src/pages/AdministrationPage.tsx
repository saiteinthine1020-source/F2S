import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

export function AdministrationPage() {
  const { t } = useTranslation();
  return (
    <section className="form-card administration-index">
      <div className="form-card__heading">
        <h1>{t("administration.index.title")}</h1>
        <p>{t("administration.index.description")}</p>
      </div>
      <nav className="administration-links" aria-label={t("administration.index.navigationLabel")}>
        <Link to="/app/admin/settings">
          <strong>{t("administration.settings.title")}</strong>
          <span>{t("administration.index.settingsDescription")}</span>
        </Link>
        <Link to="/app/admin/members">
          <strong>{t("administration.members.title")}</strong>
          <span>{t("administration.index.membersDescription")}</span>
        </Link>
        <Link to="/app/admin/ownership">
          <strong>{t("administration.ownership.title")}</strong>
          <span>{t("administration.index.ownershipDescription")}</span>
        </Link>
      </nav>
    </section>
  );
}
