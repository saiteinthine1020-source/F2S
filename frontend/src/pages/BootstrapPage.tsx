import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Navigate } from "react-router-dom";

import { completeBootstrap } from "../api/auth";
import type { BootstrapCommand, WorkspaceType } from "../api/contracts";
import { useApiClient } from "../app/ApiClientContext";
import { useAuth } from "../auth/AuthContext";
import { Field, FormLayout, SelectField } from "../components/FormLayout";
import { formValue } from "../components/formValues";

const workspaceTypes: readonly WorkspaceType[] = [
  "HOUSEHOLD",
  "FARM",
  "MICROBUSINESS",
  "SMALL_BUSINESS",
  "COMBINED",
  "CUSTOM",
];

export function BootstrapPage() {
  const client = useApiClient();
  const { markBootstrapComplete, state } = useAuth();
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (state.status !== "bootstrap") {
    return <Navigate replace to="/" />;
  }

  return (
    <FormLayout
      title={t("auth.bootstrap.title")}
      description={t("auth.bootstrap.description")}
      submitLabel={t("auth.bootstrap.submit")}
      busyLabel={t("auth.common.submitting")}
      busy={busy}
      error={error}
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError(null);
        const form = event.currentTarget;
        const command: BootstrapCommand = {
          display_name: formValue(form, "displayName"),
          email: formValue(form, "email"),
          password: formValue(form, "password"),
          account_language: formValue(
            form,
            "accountLanguage",
          ) as BootstrapCommand["account_language"],
          account_timezone: formValue(form, "accountTimezone"),
          workspace_name: formValue(form, "workspaceName"),
          workspace_type: formValue(form, "workspaceType") as WorkspaceType,
          base_currency_code: formValue(form, "currency").toUpperCase(),
          workspace_language: formValue(
            form,
            "workspaceLanguage",
          ) as BootstrapCommand["workspace_language"],
          workspace_timezone: formValue(form, "workspaceTimezone"),
        };
        try {
          await completeBootstrap(client, command);
          form.reset();
          markBootstrapComplete();
        } catch {
          setError(t("auth.bootstrap.failure"));
        } finally {
          setBusy(false);
        }
      }}
    >
      <div className="form-section">
        <h2>{t("auth.bootstrap.accountHeading")}</h2>
        <Field
          label={t("auth.fields.displayName")}
          name="displayName"
          autoComplete="name"
          required
          maxLength={120}
        />
        <Field
          label={t("auth.fields.email")}
          name="email"
          type="email"
          autoComplete="username"
          required
          maxLength={320}
        />
        <Field
          label={t("auth.fields.password")}
          hint={t("auth.fields.passwordHint")}
          name="password"
          type="password"
          autoComplete="new-password"
          required
          minLength={15}
          maxLength={1024}
        />
        <SelectField label={t("auth.fields.language")} name="accountLanguage" defaultValue="shn">
          <LanguageOptions />
        </SelectField>
        <Field
          label={t("auth.fields.timezone")}
          name="accountTimezone"
          defaultValue="Asia/Tokyo"
          required
          maxLength={64}
        />
      </div>
      <div className="form-section">
        <h2>{t("auth.bootstrap.workspaceHeading")}</h2>
        <Field
          label={t("auth.fields.workspaceName")}
          name="workspaceName"
          required
          maxLength={160}
        />
        <SelectField
          label={t("auth.fields.workspaceType")}
          name="workspaceType"
          defaultValue="HOUSEHOLD"
        >
          {workspaceTypes.map((type) => (
            <option key={type} value={type}>
              {t(`workspace.types.${type}`)}
            </option>
          ))}
        </SelectField>
        <Field
          label={t("auth.fields.currency")}
          name="currency"
          defaultValue="JPY"
          required
          minLength={3}
          maxLength={3}
        />
        <SelectField label={t("auth.fields.language")} name="workspaceLanguage" defaultValue="shn">
          <LanguageOptions />
        </SelectField>
        <Field
          label={t("auth.fields.timezone")}
          name="workspaceTimezone"
          defaultValue="Asia/Tokyo"
          required
          maxLength={64}
        />
      </div>
    </FormLayout>
  );
}

function LanguageOptions() {
  const { t } = useTranslation();
  return (
    <>
      {(["shn", "my", "en", "ja"] as const).map((locale) => (
        <option key={locale} value={locale}>
          {t(`languages.${locale}`)}
        </option>
      ))}
    </>
  );
}
