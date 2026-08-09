import { useState } from "react";
import { useTranslation } from "react-i18next";

import { useAuth } from "../auth/AuthContext";
import { StatePanel } from "../components/StatePanel";

export function WorkspaceSelectionPage() {
  const { selectWorkspace, signOut, state } = useAuth();
  const { t } = useTranslation();
  const [busyId, setBusyId] = useState<string | null>(null);
  if (state.status !== "selecting-workspace") {
    return null;
  }
  return (
    <StatePanel
      eyebrow={t("workspace.selection.eyebrow")}
      title={t("workspace.selection.title")}
      description={
        state.memberships.length === 0
          ? t("workspace.selection.empty")
          : t("workspace.selection.description")
      }
      tone={state.error ? "danger" : "neutral"}
      live={state.error ? "assertive" : undefined}
      action={
        <div className="workspace-list">
          {state.memberships.map((membership) => (
            <button
              className="workspace-choice"
              type="button"
              key={membership.membership_id}
              disabled={busyId !== null}
              onClick={async () => {
                setBusyId(membership.workspace.id);
                try {
                  await selectWorkspace(membership.workspace.id);
                } catch {
                  setBusyId(null);
                }
              }}
            >
              <strong>{membership.workspace.name}</strong>
              <span>{t(`roles.${membership.role}`)}</span>
              <span>
                {busyId === membership.workspace.id
                  ? t("workspace.selection.opening")
                  : t("workspace.selection.open")}
              </span>
            </button>
          ))}
          <button
            className="button button--secondary"
            type="button"
            onClick={() => void signOut("CURRENT")}
          >
            {t("auth.logout.current")}
          </button>
        </div>
      }
    />
  );
}
