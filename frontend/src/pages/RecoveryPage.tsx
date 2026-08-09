import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link } from "react-router-dom";

import { requestRecovery } from "../api/auth";
import { useApiClient } from "../app/ApiClientContext";
import { Field, FormLayout } from "../components/FormLayout";
import { formValue } from "../components/formValues";

export function RecoveryPage() {
  const client = useApiClient();
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  return (
    <FormLayout
      title={t("auth.recovery.requestTitle")}
      description={t("auth.recovery.requestDescription")}
      submitLabel={t("auth.recovery.requestSubmit")}
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
          await requestRecovery(client, formValue(form, "email"));
          form.reset();
          setSuccess(t("auth.recovery.requestSuccess"));
        } catch {
          setError(t("auth.recovery.requestFailure"));
        } finally {
          setBusy(false);
        }
      }}
      footer={
        <>
          <Link to="/recovery/confirm">{t("auth.recovery.confirmLink")}</Link>
          <Link to="/login">{t("auth.common.backToLogin")}</Link>
        </>
      }
    >
      <Field
        label={t("auth.fields.email")}
        name="email"
        type="email"
        autoComplete="username"
        required
        maxLength={320}
      />
    </FormLayout>
  );
}
