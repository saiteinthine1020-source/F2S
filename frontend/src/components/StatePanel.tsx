import type { ReactNode } from "react";
import { useTranslation } from "react-i18next";

interface StatePanelProps {
  readonly eyebrow?: string;
  readonly title: string;
  readonly description: string;
  readonly action?: ReactNode;
  readonly tone?: "neutral" | "danger";
  readonly live?: "polite" | "assertive";
}

export function StatePanel({
  action,
  description,
  eyebrow,
  live,
  title,
  tone = "neutral",
}: StatePanelProps) {
  return (
    <section
      className={`state-panel state-panel--${tone}`}
      aria-live={live}
      aria-atomic={live === undefined ? undefined : true}
    >
      {eyebrow === undefined ? null : <p className="state-panel__eyebrow">{eyebrow}</p>}
      <h1>{title}</h1>
      <p>{description}</p>
      {action === undefined ? null : <div className="state-panel__action">{action}</div>}
    </section>
  );
}

export function LoadingState() {
  const { t } = useTranslation();
  return (
    <StatePanel
      title={t("states.loading.title")}
      description={t("states.loading.description")}
      live="polite"
    />
  );
}

export function EmptyState() {
  const { t } = useTranslation();
  return <StatePanel title={t("states.empty.title")} description={t("states.empty.description")} />;
}

interface ErrorStateProps {
  readonly onRetry?: () => void;
}

export function ErrorState({ onRetry }: ErrorStateProps) {
  const { t } = useTranslation();
  return (
    <StatePanel
      title={t("states.error.title")}
      description={t("states.error.description")}
      tone="danger"
      live="assertive"
      action={
        onRetry === undefined ? undefined : (
          <button className="button" type="button" onClick={onRetry}>
            {t("states.error.retry")}
          </button>
        )
      }
    />
  );
}
