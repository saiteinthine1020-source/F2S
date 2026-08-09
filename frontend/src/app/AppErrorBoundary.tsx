import { Component, type PropsWithChildren, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import { StatePanel } from "../components/StatePanel";

interface BoundaryProps extends PropsWithChildren {
  readonly fallback: ReactNode;
}

interface BoundaryState {
  readonly failed: boolean;
}

class ErrorBoundary extends Component<BoundaryProps, BoundaryState> {
  override state: BoundaryState = { failed: false };

  static getDerivedStateFromError(): BoundaryState {
    return { failed: true };
  }

  override componentDidCatch(): void {
    // A future observability adapter may receive a bounded client code, never the raw error.
  }

  override render(): ReactNode {
    return this.state.failed ? this.props.fallback : this.props.children;
  }
}

export function AppErrorBoundary({ children }: PropsWithChildren) {
  const { t } = useTranslation();
  return (
    <ErrorBoundary
      fallback={
        <main id="main-content" className="app-main" tabIndex={-1}>
          <StatePanel
            title={t("errors.configuration.title")}
            description={t("errors.configuration.description")}
            tone="danger"
            live="assertive"
          />
        </main>
      }
    >
      {children}
    </ErrorBoundary>
  );
}
