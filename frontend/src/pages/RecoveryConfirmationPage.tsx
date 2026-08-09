import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { confirmRecovery } from "../api/auth";
import { useApiClient } from "../app/ApiClientContext";
import { Field, FormLayout } from "../components/FormLayout";
import { formValue } from "../components/formValues";

export function RecoveryConfirmationPage() {
  const client = useApiClient();
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  return (
    <FormLayout
      title={t("auth.recovery.confirmTitle")}
      description={t("auth.recovery.confirmDescription")}
      submitLabel={t("auth.recovery.confirmSubmit")}
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
        try {
          await confirmRecovery(client, formValue(form, "value"), formValue(form, "password"));
          form.reset();
          setSuccess(t("auth.recovery.confirmSuccess"));
        } catch {
          setError(t("auth.recovery.confirmFailure"));
        } finally {
          setBusy(false);
        }
      }}
      footer={<Link to="/login">{t("auth.common.backToLogin")}</Link>}
    >
      <Field
        label={t("auth.fields.recoveryValue")}
        name="value"
        type="password"
        autoComplete="off"
        required
        minLength={32}
        maxLength={512}
      />
      <Field
        label={t("auth.fields.newPassword")}
        hint={t("auth.fields.passwordHint")}
        name="password"
        type="password"
        autoComplete="new-password"
        required
        minLength={15}
        maxLength={1024}
      />
    </FormLayout>
  );
}
