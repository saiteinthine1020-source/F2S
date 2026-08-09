import { useCallback, useEffect, useRef, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  cancelOwnershipTransfer,
  initiateOwnershipTransfer,
  listMembers,
} from "../api/administration";
import { ApiError } from "../api/client";
import type { MemberRecord, MemberRole, OwnershipTransfer } from "../api/contracts";
import { useApiClient } from "../app/ApiClientContext";
import { useAuth } from "../auth/AuthContext";
import { FormLayout } from "../components/FormLayout";
import { formValue } from "../components/formValues";
import { ErrorState, LoadingState } from "../components/StatePanel";

interface PendingTransfer {
  readonly targetMembershipId: string;
  readonly formerOwnerRole: MemberRole;
  readonly currentPassword: string;
}

export function OwnershipTransferPage() {
  const client = useApiClient();
  const { state } = useAuth();
  const { t } = useTranslation();
  const formRef = useRef<HTMLFormElement | null>(null);
  const [members, setMembers] = useState<readonly MemberRecord[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [pending, setPending] = useState<PendingTransfer | null>(null);
  const [transfer, setTransfer] = useState<OwnershipTransfer | null>(null);
  const workspaceId = state.status === "authenticated" ? state.selected.details.workspace.id : "";

  const load = useCallback(async () => {
    setLoadError(false);
    try {
      setMembers(await listMembers(client, workspaceId));
    } catch {
      setLoadError(true);
    }
  }, [client, workspaceId]);

  useEffect(() => {
    queueMicrotask(() => void load());
  }, [load]);

  useEffect(() => {
    if (transfer?.status !== "INITIATED") return;
    const delay = Math.max(0, Date.parse(transfer.expires_at) - Date.now());
    const timer = window.setTimeout(() => {
      setTransfer((current) =>
        current?.status === "INITIATED" ? { ...current, status: "EXPIRED" } : current,
      );
    }, delay);
    return () => window.clearTimeout(timer);
  }, [transfer]);

  if (members === null && !loadError) return <LoadingState />;
  if (loadError) return <ErrorState onRetry={() => void load()} />;
  const candidates = members?.filter(
    (member) => member.role !== "ADMIN" && member.status === "ACTIVE",
  );

  return (
    <div className="administration-stack">
      <FormLayout
        title={t("administration.ownership.title")}
        description={t("administration.ownership.description")}
        submitLabel={t("administration.ownership.review")}
        busyLabel={t("auth.common.submitting")}
        busy={busy}
        error={error}
        success={
          transfer === null ? null : t(`administration.ownership.outcome.${transfer.status}`)
        }
        onSubmit={(event) => {
          event.preventDefault();
          formRef.current = event.currentTarget;
          setError(null);
          setPending({
            targetMembershipId: formValue(event.currentTarget, "targetMembership"),
            formerOwnerRole: formValue(event.currentTarget, "formerOwnerRole") as MemberRole,
            currentPassword: formValue(event.currentTarget, "currentPassword"),
          });
        }}
        footer={
          pending === null ? undefined : (
            <section
              className="confirmation"
              role="alertdialog"
              aria-labelledby="ownership-confirm-title"
              aria-describedby="ownership-confirm-description"
            >
              <h2 id="ownership-confirm-title">{t("administration.ownership.confirmTitle")}</h2>
              <p id="ownership-confirm-description">
                {t("administration.ownership.confirmDescription")}
              </p>
              <div className="button-row">
                <button
                  className="button button--danger"
                  type="button"
                  disabled={busy}
                  onClick={async () => {
                    setBusy(true);
                    setError(null);
                    try {
                      setTransfer(
                        await initiateOwnershipTransfer(
                          client,
                          workspaceId,
                          pending.targetMembershipId,
                          pending.formerOwnerRole,
                          pending.currentPassword,
                        ),
                      );
                      formRef.current?.reset();
                      setPending(null);
                    } catch (caught) {
                      const password = formRef.current?.elements.namedItem("currentPassword");
                      if (password instanceof HTMLInputElement) password.value = "";
                      setPending(null);
                      setError(
                        caught instanceof ApiError && caught.code === "REAUTHENTICATION_REQUIRED"
                          ? t("administration.ownership.reauthenticationFailure")
                          : t("administration.ownership.failure"),
                      );
                    } finally {
                      setBusy(false);
                    }
                  }}
                >
                  {t("administration.ownership.initiate")}
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
          )
        }
      >
        <label className="field">
          <span>{t("administration.ownership.target")}</span>
          <select name="targetMembership" required defaultValue="">
            <option value="" disabled>
              {t("administration.ownership.chooseTarget")}
            </option>
            {candidates?.map((member) => (
              <option key={member.id} value={member.id}>
                {member.display_name} — {member.email}
              </option>
            ))}
          </select>
        </label>
        {candidates?.length === 0 ? (
          <p className="notice">{t("administration.ownership.noCandidates")}</p>
        ) : null}
        <label className="field">
          <span>{t("administration.ownership.formerRole")}</span>
          <select name="formerOwnerRole" defaultValue="CONTRIBUTOR">
            <option value="CONTRIBUTOR">{t("roles.CONTRIBUTOR")}</option>
            <option value="ADVISOR">{t("roles.ADVISOR")}</option>
          </select>
        </label>
        <label className="field">
          <span>{t("auth.fields.currentPassword")}</span>
          <input
            name="currentPassword"
            type="password"
            autoComplete="current-password"
            required
            maxLength={1024}
          />
        </label>
        <label className="check-field check-field--warning">
          <input name="consequences" type="checkbox" required />
          <span>{t("administration.ownership.consequences")}</span>
        </label>
      </FormLayout>

      {transfer === null ? null : (
        <section className="form-card transfer-outcome" aria-live="polite">
          <h2>{t("administration.ownership.pendingTitle")}</h2>
          <dl>
            <div>
              <dt>{t("administration.ownership.transferId")}</dt>
              <dd>{transfer.id}</dd>
            </div>
            <div>
              <dt>{t("administration.ownership.status")}</dt>
              <dd>{t(`administration.ownership.outcome.${transfer.status}`)}</dd>
            </div>
            <div>
              <dt>{t("administration.ownership.expires")}</dt>
              <dd>{new Date(transfer.expires_at).toLocaleString()}</dd>
            </div>
          </dl>
          {transfer.status === "INITIATED" ? (
            <button
              className="button button--secondary"
              type="button"
              disabled={busy}
              onClick={async () => {
                setBusy(true);
                setError(null);
                try {
                  await cancelOwnershipTransfer(client, transfer);
                  setTransfer({ ...transfer, status: "CANCELLED" });
                } catch (caught) {
                  setError(
                    caught instanceof ApiError && caught.code === "VERSION_MISMATCH"
                      ? t("administration.conflict")
                      : t("administration.ownership.cancelFailure"),
                  );
                } finally {
                  setBusy(false);
                }
              }}
            >
              {t("administration.ownership.cancelTransfer")}
            </button>
          ) : null}
        </section>
      )}
    </div>
  );
}
