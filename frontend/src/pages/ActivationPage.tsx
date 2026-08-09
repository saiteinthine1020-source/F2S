import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { activateAccount } from "../api/auth";
import { useApiClient } from "../app/ApiClientContext";
import { Field, FormLayout } from "../components/FormLayout";
import { formValue } from "../components/formValues";

export function ActivationPage() {
  const client = useApiClient();
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  return (
    <FormLayout
      title={t("auth.activation.title")}
      description={t("auth.activation.description")}
      submitLabel={t("auth.activation.submit")}
      busyLabel={t("auth.common.submitting")}
      busy={busy}
      error={error}
      success={success}
      onSubmit={async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        setBusy(true);
        setError(null);
        setSuccess(null);
        const password = formValue(form, "password");
        try {
          await activateAccount(client, formValue(form, "value"), password || null);
          form.reset();
          setSuccess(t("auth.activation.success"));
        } catch {
          setError(t("auth.activation.failure"));
        } finally {
          setBusy(false);
        }
      }}
      footer={<Link to="/login">{t("auth.common.backToLogin")}</Link>}
    >
      <Field
        label={t("auth.fields.activationValue")}
        name="value"
        type="password"
        autoComplete="off"
        required
        minLength={32}
        maxLength={512}
      />
      <Field
        label={t("auth.fields.newPasswordOptional")}
        hint={t("auth.fields.passwordHint")}
        name="password"
        type="password"
        autoComplete="new-password"
        minLength={15}
        maxLength={1024}
      />
    </FormLayout>
  );
}
