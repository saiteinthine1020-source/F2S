import { useState } from "react";
import { useTranslation } from "react-i18next";

import { confirmOwnershipTransfer } from "../api/administration";
import { useApiClient } from "../app/ApiClientContext";
import { useAuth } from "../auth/AuthContext";
import { Field, FormLayout } from "../components/FormLayout";
import { formValue } from "../components/formValues";

export function OwnershipConfirmationPage() {
  const client = useApiClient();
  const { endOwnershipTransferSession, state } = useAuth();
  const { t } = useTranslation();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  if (state.status !== "authenticated") return null;
  const workspaceId = state.selected.details.workspace.id;
  return (
    <FormLayout
      title={t("administration.ownership.confirmationTitle")}
      description={t("administration.ownership.confirmationDescription")}
      submitLabel={t("administration.ownership.complete")}
      busyLabel={t("auth.common.submitting")}
      busy={busy}
      error={error}
      onSubmit={async (event) => {
        event.preventDefault();
        const form = event.currentTarget;
        setBusy(true);
        setError(null);
        try {
          await confirmOwnershipTransfer(
            client,
            workspaceId,
            formValue(form, "transferId"),
            formValue(form, "transferValue"),
          );
          endOwnershipTransferSession();
        } catch {
          const evidence = form.elements.namedItem("transferValue");
          if (evidence instanceof HTMLInputElement) evidence.value = "";
          setError(t("administration.ownership.confirmationFailure"));
        } finally {
          setBusy(false);
        }
      }}
    >
      <Field
        label={t("administration.ownership.transferId")}
        name="transferId"
        required
        maxLength={36}
      />
      <Field
        label={t("administration.ownership.confirmationValue")}
        name="transferValue"
        type="password"
        autoComplete="off"
        required
        minLength={32}
        maxLength={512}
      />
      <label className="check-field check-field--warning">
        <input name="confirmationConsequences" type="checkbox" required />
        <span>{t("administration.ownership.confirmationConsequences")}</span>
      </label>
    </FormLayout>
  );
}
