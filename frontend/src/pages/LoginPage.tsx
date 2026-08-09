import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Link, useLocation, useNavigate } from "react-router-dom";

import { Field, FormLayout } from "../components/FormLayout";
import { formValue } from "../components/formValues";
import { useAuth, type SessionEndReason } from "../auth/AuthContext";

export function LoginPage() {
  const { t } = useTranslation();
  const { signIn } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const reason = (location.state as { readonly reason?: SessionEndReason } | null)?.reason;
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  return (
    <FormLayout
      title={t("auth.login.title")}
      description={t("auth.login.description")}
      submitLabel={t("auth.login.submit")}
      busyLabel={t("auth.common.submitting")}
      busy={busy}
      error={error ?? (reason && reason !== "ownership" ? t(`auth.session.${reason}`) : null)}
      success={reason === "ownership" ? t("auth.session.ownership") : null}
      onSubmit={async (event) => {
        event.preventDefault();
        setBusy(true);
        setError(null);
        try {
          await signIn(
            formValue(event.currentTarget, "email"),
            formValue(event.currentTarget, "password"),
          );
          await navigate("/app", { replace: true });
        } catch {
          setError(t("auth.login.failure"));
        } finally {
          setBusy(false);
        }
      }}
      footer={<Link to="/recovery">{t("auth.login.recoveryLink")}</Link>}
    >
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
        name="password"
        type="password"
        autoComplete="current-password"
        required
        maxLength={1024}
      />
    </FormLayout>
  );
}
