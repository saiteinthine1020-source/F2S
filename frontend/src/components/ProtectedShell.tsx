import { type PropsWithChildren, useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, NavLink } from "react-router-dom";

import type { SupportedRole } from "../api/contracts";
import { useAuth } from "../auth/AuthContext";

const navigation: Record<SupportedRole, readonly string[]> = {
  ADMIN: ["home", "transactions", "add", "reports", "more"],
  CONTRIBUTOR: ["submissions", "add", "status", "more"],
  ADVISOR: ["home", "transactions", "reports", "review", "more"],
};

export function ProtectedShell({ children }: PropsWithChildren) {
  const { beginWorkspaceSwitch, signOut, state } = useAuth();
  const { t } = useTranslation();
  const [confirmSwitch, setConfirmSwitch] = useState(false);
  const [menuBusy, setMenuBusy] = useState(false);
  if (state.status !== "authenticated") {
    return null;
  }
  const { membership } = state.selected;
  return (
    <div className="protected-shell">
      <section className="workspace-bar" aria-label={t("workspace.current.label")}>
        <div>
          <strong>{membership.workspace.name}</strong>
          <span>{t(`roles.${membership.role}`)}</span>
        </div>
        {state.memberships.length > 1 ? (
          <button className="text-button" type="button" onClick={() => setConfirmSwitch(true)}>
            {t("workspace.switch.start")}
          </button>
        ) : null}
      </section>
      {confirmSwitch ? (
        <section
          className="confirmation"
          role="alertdialog"
          aria-labelledby="switch-title"
          aria-describedby="switch-description"
        >
          <h2 id="switch-title">{t("workspace.switch.title")}</h2>
          <p id="switch-description">{t("workspace.switch.description")}</p>
          <div className="button-row">
            <button className="button" type="button" onClick={beginWorkspaceSwitch}>
              {t("workspace.switch.confirm")}
            </button>
            <button
              className="button button--secondary"
              type="button"
              onClick={() => setConfirmSwitch(false)}
            >
              {t("workspace.switch.cancel")}
            </button>
          </div>
        </section>
      ) : null}
      <nav className="primary-nav" aria-label={t("navigation.primaryLabel")}>
        {navigation[membership.role].map((destination) => (
          <NavLink
            key={destination}
            to={destination === "home" ? "/app" : `/app/${destination}`}
            end={destination === "home"}
          >
            {t(`navigation.${destination}`)}
          </NavLink>
        ))}
      </nav>
      <div className="protected-content">{children}</div>
      <footer className="account-actions">
        <Link to="/app/password">{t("auth.passwordChange.link")}</Link>
        <button
          className="text-button"
          type="button"
          disabled={menuBusy}
          onClick={async () => {
            setMenuBusy(true);
            await signOut("CURRENT");
          }}
        >
          {t("auth.logout.current")}
        </button>
        <button
          className="text-button"
          type="button"
          disabled={menuBusy}
          onClick={async () => {
            setMenuBusy(true);
            await signOut("ALL");
          }}
        >
          {t("auth.logout.all")}
        </button>
      </footer>
    </div>
  );
}
