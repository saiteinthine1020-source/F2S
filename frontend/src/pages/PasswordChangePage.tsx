import { useState } from "react";
import { useTranslation } from "react-i18next";

import { changePassword } from "../api/auth";
import { useApiClient } from "../app/ApiClientContext";
import { Field, FormLayout } from "../components/FormLayout";
import { formValue } from "../components/formValues";

export function PasswordChangePage() {
  const client = useApiClient();
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  return (
    <FormLayout
      title={t("auth.passwordChange.title")}
      description={t("auth.passwordChange.description")}
      submitLabel={t("auth.passwordChange.submit")}
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
          await changePassword(
            client,
            formValue(form, "currentPassword"),
            formValue(form, "newPassword"),
          );
          form.reset();
          setSuccess(t("auth.passwordChange.success"));
        } catch {
          setError(t("auth.passwordChange.failure"));
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field
        label={t("auth.fields.currentPassword")}
        name="currentPassword"
        type="password"
        autoComplete="current-password"
        required
        maxLength={1024}
      />
      <Field
        label={t("auth.fields.newPassword")}
        hint={t("auth.fields.passwordHint")}
        name="newPassword"
        type="password"
        autoComplete="new-password"
        required
        minLength={15}
        maxLength={1024}
      />
    </FormLayout>
  );
}
