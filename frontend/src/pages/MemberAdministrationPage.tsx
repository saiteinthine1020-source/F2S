import { useCallback, useEffect, useState } from "react";
import { useTranslation } from "react-i18next";

import {
  changeMemberRole,
  listMembers,
  provisionMember,
  reactivateMember,
  restartActivation,
  revokeMember,
  suspendMember,
} from "../api/administration";
import { ApiError } from "../api/client";
import type { MemberRecord, MemberRole, SupportedLanguage } from "../api/contracts";
import { useApiClient } from "../app/ApiClientContext";
import { useAuth } from "../auth/AuthContext";
import { Field, FormLayout, SelectField } from "../components/FormLayout";
import { formValue } from "../components/formValues";
import { ErrorState, LoadingState } from "../components/StatePanel";

type MemberAction =
  | { readonly kind: "ROLE"; readonly member: MemberRecord; readonly role: MemberRole }
  | {
      readonly kind: "SUSPEND" | "REACTIVATE" | "RESTART" | "REVOKE";
      readonly member: MemberRecord;
    };

export function MemberAdministrationPage() {
  const client = useApiClient();
  const { state } = useAuth();
  const { t } = useTranslation();
  const [members, setMembers] = useState<readonly MemberRecord[] | null>(null);
  const [loadError, setLoadError] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<{
    readonly kind: "error" | "success";
    readonly text: string;
  } | null>(null);
  const [pending, setPending] = useState<MemberAction | null>(null);
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

  if (members === null && !loadError) return <LoadingState />;
  if (loadError) return <ErrorState onRetry={() => void load()} />;

  const confirmAction = async () => {
    if (pending === null) return;
    setBusy(true);
    setMessage(null);
    try {
      if (pending.kind === "ROLE") {
        await changeMemberRole(client, workspaceId, pending.member, pending.role);
      } else if (pending.kind === "SUSPEND") {
        await suspendMember(client, workspaceId, pending.member);
      } else if (pending.kind === "REACTIVATE") {
        await reactivateMember(client, workspaceId, pending.member);
      } else if (pending.kind === "RESTART") {
        await restartActivation(client, workspaceId, pending.member);
      } else {
        await revokeMember(client, workspaceId, pending.member);
      }
      setPending(null);
      await load();
      setMessage({ kind: "success", text: t("administration.members.actionSuccess") });
    } catch (caught) {
      setPending(null);
      setMessage({
        kind: "error",
        text:
          caught instanceof ApiError && caught.code === "VERSION_MISMATCH"
            ? t("administration.conflict")
            : t("administration.members.actionFailure"),
      });
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="administration-stack">
      <FormLayout
        title={t("administration.members.createTitle")}
        description={t("administration.members.createDescription")}
        submitLabel={t("administration.members.create")}
        busyLabel={t("auth.common.submitting")}
        busy={busy}
        error={message?.kind === "error" ? message.text : null}
        success={message?.kind === "success" ? message.text : null}
        onSubmit={async (event) => {
          event.preventDefault();
          const form = event.currentTarget;
          setBusy(true);
          setMessage(null);
          try {
            await provisionMember(client, workspaceId, {
              email: formValue(form, "email"),
              display_name: formValue(form, "displayName"),
              role: formValue(form, "role") as MemberRole,
              preferred_language: formValue(form, "language") as SupportedLanguage,
              timezone: formValue(form, "timezone"),
            });
            form.reset();
            await load();
            setMessage({ kind: "success", text: t("administration.members.createSuccess") });
          } catch {
            setMessage({ kind: "error", text: t("administration.members.createFailure") });
          } finally {
            setBusy(false);
          }
        }}
      >
        <Field label={t("auth.fields.displayName")} name="displayName" required maxLength={120} />
        <Field label={t("auth.fields.email")} name="email" type="email" required maxLength={320} />
        <SelectField label={t("administration.fields.role")} name="role" defaultValue="CONTRIBUTOR">
          <option value="CONTRIBUTOR">{t("roles.CONTRIBUTOR")}</option>
          <option value="ADVISOR">{t("roles.ADVISOR")}</option>
        </SelectField>
        <SelectField label={t("auth.fields.language")} name="language" defaultValue="en">
          <option value="shn">{t("languages.shn")}</option>
          <option value="my">{t("languages.my")}</option>
          <option value="en">{t("languages.en")}</option>
          <option value="ja">{t("languages.ja")}</option>
        </SelectField>
        <Field
          label={t("auth.fields.timezone")}
          name="timezone"
          required
          maxLength={64}
          defaultValue={
            state.status === "authenticated" ? state.selected.details.workspace.timezone : "UTC"
          }
        />
      </FormLayout>

      <section className="form-card">
        <div className="form-card__heading">
          <h1>{t("administration.members.title")}</h1>
          <p>{t("administration.members.description")}</p>
        </div>
        {members?.length === 0 ? <p>{t("administration.members.empty")}</p> : null}
        <div className="member-list">
          {members?.map((member) => (
            <article className="member-card" key={member.id}>
              <div>
                <h2>{member.display_name}</h2>
                <p>{member.email}</p>
                <p>
                  <span className="status-badge">{t(`roles.${member.role}`)}</span>{" "}
                  <span className="status-badge">
                    {t(`administration.memberStatus.${member.status}`)}
                  </span>
                </p>
              </div>
              {member.role === "ADMIN" ? (
                <p className="notice">{t("administration.members.ownerProtected")}</p>
              ) : (
                <div className="member-actions">
                  {member.status !== "REVOKED" ? (
                    <label className="field">
                      <span>{t("administration.members.changeRole")}</span>
                      <select
                        defaultValue={member.role}
                        onChange={(event) =>
                          setPending({
                            kind: "ROLE",
                            member,
                            role: event.target.value as MemberRole,
                          })
                        }
                      >
                        <option value={member.role}>{t(`roles.${member.role}`)}</option>
                        <option value={member.role === "CONTRIBUTOR" ? "ADVISOR" : "CONTRIBUTOR"}>
                          {t(`roles.${member.role === "CONTRIBUTOR" ? "ADVISOR" : "CONTRIBUTOR"}`)}
                        </option>
                      </select>
                    </label>
                  ) : null}
                  <div className="button-row">
                    {member.status === "ACTIVE" ? (
                      <button
                        className="button button--secondary"
                        type="button"
                        onClick={() => setPending({ kind: "SUSPEND", member })}
                      >
                        {t("administration.members.suspend")}
                      </button>
                    ) : null}
                    {member.status === "SUSPENDED" ? (
                      <button
                        className="button button--secondary"
                        type="button"
                        onClick={() => setPending({ kind: "REACTIVATE", member })}
                      >
                        {t("administration.members.reactivate")}
                      </button>
                    ) : null}
                    {member.status === "PENDING" ? (
                      <button
                        className="button button--secondary"
                        type="button"
                        onClick={() => setPending({ kind: "RESTART", member })}
                      >
                        {t("administration.members.restart")}
                      </button>
                    ) : null}
                    {member.status !== "REVOKED" ? (
                      <button
                        className="button button--danger"
                        type="button"
                        onClick={() => setPending({ kind: "REVOKE", member })}
                      >
                        {t("administration.members.revoke")}
                      </button>
                    ) : null}
                  </div>
                </div>
              )}
            </article>
          ))}
        </div>
      </section>

      {pending === null ? null : (
        <section
          className="confirmation"
          role="alertdialog"
          aria-labelledby="member-confirm-title"
          aria-describedby="member-confirm-description"
        >
          <h2 id="member-confirm-title">{t("administration.members.confirmTitle")}</h2>
          <p id="member-confirm-description">
            {t(`administration.members.confirm.${pending.kind}`, {
              name: pending.member.display_name,
            })}
          </p>
          <div className="button-row">
            <button
              className="button button--danger"
              type="button"
              disabled={busy}
              onClick={() => void confirmAction()}
            >
              {t("administration.members.confirmAction")}
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
      )}
    </div>
  );
}
