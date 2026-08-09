import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { axe } from "vitest-axe";
import { describe, expect, it, vi } from "vitest";

import { appRoutes } from "../src/app/router";
import { App } from "../src/app/App";
import { ErrorState, LoadingState } from "../src/components/StatePanel";
import { renderLocalized } from "./test-utils";

const axeOptions = {
  rules: { "color-contrast": { enabled: false } },
} as const;

describe("accessible responsive foundation", () => {
  it("renders semantic landmarks, one heading, and a keyboard skip link", async () => {
    const user = userEvent.setup();
    const router = createMemoryRouter(appRoutes, { initialEntries: ["/"] });
    const { container } = renderLocalized(<RouterProvider router={router} />, {
      language: "shn",
      withRouter: false,
    });

    expect(screen.getByRole("banner")).toBeInTheDocument();
    expect(screen.getByRole("main")).toHaveAttribute("id", "main-content");
    expect(screen.getAllByRole("heading", { level: 1 })).toHaveLength(1);
    await user.tab();
    expect(screen.getByRole("link", { name: "Skip to main content" })).toHaveFocus();
    expect((await axe(container, axeOptions)).violations).toEqual([]);
  });

  it("provides translated loading and actionable error announcements", async () => {
    const retry = vi.fn();
    const loading = renderLocalized(<LoadingState />);
    expect(screen.getByText("Loading").closest("section")).toHaveAttribute("aria-live", "polite");
    loading.unmount();

    const { container } = renderLocalized(<ErrorState onRetry={retry} />);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));
    expect(retry).toHaveBeenCalledOnce();
    expect((await axe(container, axeOptions)).violations).toEqual([]);
  });

  it("renders a safe translated not-found route", () => {
    const router = createMemoryRouter(appRoutes, { initialEntries: ["/missing"] });
    renderLocalized(<RouterProvider router={router} />, { withRouter: false });
    expect(screen.getByRole("heading", { name: "Page not found" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Return home" })).toHaveAttribute("href", "/");
  });

  it("renders a safe translated failure when runtime configuration is invalid", () => {
    vi.stubEnv("VITE_API_BASE_URL", "invalid-configuration");
    const consoleError = vi.spyOn(console, "error").mockImplementation(() => undefined);
    renderLocalized(<App />, { withRouter: false });
    expect(
      screen.getByRole("heading", { name: "Application configuration is unavailable" }),
    ).toBeInTheDocument();
    expect(document.body).not.toHaveTextContent("invalid-configuration");
    consoleError.mockRestore();
    vi.unstubAllEnvs();
  });
});
