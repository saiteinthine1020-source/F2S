import { useState } from "react";
import { useTranslation } from "react-i18next";

import { updateWorkspaceSettings, type WorkspaceSettingsCommand } from "../api/administration";
import { getWorkspace } from "../api/auth";
import { ApiError } from "../api/client";
import type { ModuleCode, SupportedLanguage, WorkspaceType } from "../api/contracts";
import { useApiClient } from "../app/ApiClientContext";
import { useAuth } from "../auth/AuthContext";
import { FormLayout } from "../components/FormLayout";
import { formValue } from "../components/formValues";

const WORKSPACE_TYPES: readonly WorkspaceType[] = [
  "HOUSEHOLD",
  "FARM",
  "MICROBUSINESS",
  "SMALL_BUSINESS",
  "COMBINED",
  "CUSTOM",
];
const LANGUAGES: readonly SupportedLanguage[] = ["shn", "my", "en", "ja"];
const MODULES: readonly ModuleCode[] = ["HOUSEHOLD_FINANCE", "FARMING_INVESTMENTS"];

export function WorkspaceSettingsPage() {
  const client = useApiClient();
  const { acceptWorkspaceUpdate, state } = useAuth();
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [pending, setPending] = useState<WorkspaceSettingsCommand | null>(null);
  const [conflict, setConflict] = useState(false);
  if (state.status !== "authenticated") return null;
  const details = state.selected.details;
  const administration = details.administration;
  const moduleEnabled = (code: ModuleCode) =>
    details.modules.find((module) => module.code === code)?.enabled ?? false;

  return (
    <FormLayout
      key={details.workspace.version}
      title={t("administration.settings.title")}
      description={t("administration.settings.description")}
      submitLabel={t("administration.settings.review")}
      busyLabel={t("auth.common.submitting")}
      busy={busy}
      error={error}
      success={success}
      onSubmit={(event) => {
        event.preventDefault();
        const form = event.currentTarget;
        setError(null);
        setSuccess(null);
        setPending({
          name: formValue(form, "workspaceName"),
          type: formValue(form, "workspaceType") as WorkspaceType,
          base_currency_code: formValue(form, "currency").toUpperCase(),
          timezone: formValue(form, "timezone"),
          preferred_language: formValue(form, "language") as SupportedLanguage,
          description: optional(formValue(form, "description")),
          address: optional(formValue(form, "address")),
          business_category_code: optional(formValue(form, "businessCategory")),
          farm_type_code: optional(formValue(form, "farmType")),
          modules: MODULES.map((code) => ({
            code,
            enabled: (form.elements.namedItem(`module-${code}`) as HTMLInputElement).checked,
          })),
        });
      }}
      footer={
        pending !== null ? (
          <section
            className="confirmation"
            role="alertdialog"
            aria-labelledby="settings-confirm-title"
            aria-describedby="settings-confirm-description"
          >
            <h2 id="settings-confirm-title">{t("administration.settings.confirmTitle")}</h2>
            <p id="settings-confirm-description">
              {t("administration.settings.confirmDescription")}
            </p>
            <div className="button-row">
              <button
                className="button"
                type="button"
                disabled={busy}
                onClick={async () => {
                  setBusy(true);
                  setError(null);
                  try {
                    const updated = await updateWorkspaceSettings(
                      client,
                      details.workspace.id,
                      details.workspace.version,
                      pending,
                    );
                    acceptWorkspaceUpdate(updated);
                    setPending(null);
                    setSuccess(t("administration.settings.success"));
                  } catch (caught) {
                    setPending(null);
                    if (caught instanceof ApiError && caught.code === "VERSION_MISMATCH") {
                      setConflict(true);
                      setError(t("administration.conflict"));
                    } else {
                      setError(t("administration.settings.failure"));
                    }
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                {t("administration.settings.confirm")}
              </button>
              <button
                className="button button--secondary"
                type="button"
                disabled={busy}
                onClick={() => setPending(null)}
              >
                {t("administration.cancel")}
              </button>
            </div>
          </section>
        ) : conflict ? (
          <button
            className="button button--secondary"
            type="button"
            disabled={busy}
            onClick={async () => {
              setBusy(true);
              try {
                acceptWorkspaceUpdate(await getWorkspace(client, details.workspace.id));
                setConflict(false);
                setError(null);
                setSuccess(t("administration.settings.latestLoaded"));
              } catch {
                setError(t("administration.settings.reloadFailure"));
              } finally {
                setBusy(false);
              }
            }}
          >
            {t("administration.settings.reload")}
          </button>
        ) : undefined
      }
    >
      <div className="form-section">
        <h2>{t("administration.settings.identityHeading")}</h2>
        <label className="field">
          <span>{t("auth.fields.workspaceName")}</span>
          <input
            name="workspaceName"
            required
            maxLength={160}
            defaultValue={details.workspace.name}
          />
        </label>
        <label className="field">
          <span>{t("auth.fields.workspaceType")}</span>
          <select name="workspaceType" defaultValue={details.workspace.type}>
            {WORKSPACE_TYPES.map((type) => (
              <option key={type} value={type}>
                {t(`workspace.types.${type}`)}
              </option>
            ))}
          </select>
        </label>
        <label className="field">
          <span>{t("auth.fields.currency")}</span>
          <input
            name="currency"
            required
            minLength={3}
            maxLength={3}
            pattern="[A-Za-z]{3}"
            defaultValue={details.workspace.base_currency_code}
          />
        </label>
        <label className="field">
          <span>{t("auth.fields.timezone")}</span>
          <input
            name="timezone"
            required
            maxLength={64}
            defaultValue={details.workspace.timezone}
          />
        </label>
        <label className="field">
          <span>{t("auth.fields.language")}</span>
          <select name="language" defaultValue={details.workspace.preferred_language}>
            {LANGUAGES.map((language) => (
              <option key={language} value={language}>
                {t(`languages.${language}`)}
              </option>
            ))}
          </select>
        </label>
      </div>
      <div className="form-section">
        <h2>{t("administration.settings.profileHeading")}</h2>
        <label className="field">
          <span>{t("administration.fields.description")}</span>
          <textarea
            name="description"
            maxLength={2000}
            defaultValue={administration?.description ?? ""}
          />
        </label>
        <label className="field">
          <span>{t("administration.fields.address")}</span>
          <textarea name="address" maxLength={1000} defaultValue={administration?.address ?? ""} />
        </label>
        <label className="field">
          <span>{t("administration.fields.businessCategory")}</span>
          <input
            name="businessCategory"
            maxLength={64}
            defaultValue={administration?.business_category_code ?? ""}
          />
        </label>
        <label className="field">
          <span>{t("administration.fields.farmType")}</span>
          <input
            name="farmType"
            maxLength={64}
            defaultValue={administration?.farm_type_code ?? ""}
          />
        </label>
      </div>
      <div className="form-section module-settings">
        <h2>{t("administration.settings.modulesHeading")}</h2>
        <p>{t("administration.settings.modulesDescription")}</p>
        {MODULES.map((code) => (
          <label className="check-field" key={code}>
            <input name={`module-${code}`} type="checkbox" defaultChecked={moduleEnabled(code)} />
            <span>{t(`administration.modules.${code}`)}</span>
          </label>
        ))}
      </div>
    </FormLayout>
  );
}

function optional(value: string): string | null {
  const trimmed = value.trim();
  return trimmed.length === 0 ? null : trimmed;
}
