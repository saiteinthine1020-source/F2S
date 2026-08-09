import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";

import {
  FakeApiClient,
  membership,
  renderAuthApplication,
  sessionEnvelope,
  workspaceEnvelope,
} from "./auth-test-utils";

const axeOptions = { rules: { "color-contrast": { enabled: false } } } as const;

describe("administration accessibility", () => {
  it("renders the Admin settings form and confirmation route without structural violations", async () => {
    const admin = membership(
      "11111111-1111-4111-8111-111111111111",
      "Accessible workspace",
      "ADMIN",
    );
    const client = new FakeApiClient((path) => {
      if (path === "/setup/bootstrap") return { data: { available: false } };
      if (path === "/auth/login") return sessionEnvelope;
      if (path === "/me/workspaces") return { data: [admin] };
      if (path === `/workspaces/${admin.workspace.id}`) return workspaceEnvelope(admin);
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    const { container, router } = renderAuthApplication(client, "/login");
    await user.type(await screen.findByLabelText("Email address"), "admin@example.invalid");
    await user.type(screen.getByLabelText("Password"), "synthetic-password-value");
    await user.click(screen.getByRole("button", { name: "Sign in securely" }));
    await router.navigate("/app/admin/settings");

    expect(await screen.findByRole("heading", { name: "Workspace settings" })).toBeInTheDocument();
    expect(screen.getByLabelText("Household finance")).toHaveAccessibleName();
    expect((await axe(container, axeOptions)).violations).toEqual([]);
  });
});
