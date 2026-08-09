import { screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import {
  FakeApiClient,
  membership,
  renderAuthApplication,
  sessionEnvelope,
  workspaceEnvelope,
} from "./auth-test-utils";

describe("authentication and protected routing", () => {
  it("redirects an unauthenticated deep link without rendering protected content", async () => {
    const client = new FakeApiClient((path) => {
      if (path === "/setup/bootstrap") return { data: { available: false } };
      throw new Error(`Unexpected request: ${path}`);
    });
    renderAuthApplication(client, "/app");
    expect(
      await screen.findByRole("heading", { name: "Sign in" }, { timeout: 5_000 }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Workspace access is ready")).not.toBeInTheDocument();
    expect(client.credentials).toBeNull();
  });

  it("signs in, requires explicit multi-workspace selection, and renders Admin navigation", async () => {
    const alpha = membership("11111111-1111-4111-8111-111111111111", "Alpha workspace", "ADMIN");
    const beta = membership(
      "22222222-2222-4222-8222-222222222222",
      "Beta workspace",
      "CONTRIBUTOR",
    );
    const client = new FakeApiClient((path) => {
      if (path === "/setup/bootstrap") return { data: { available: false } };
      if (path === "/auth/login") return sessionEnvelope;
      if (path === "/me/workspaces") return { data: [alpha, beta] };
      if (path === `/workspaces/${alpha.workspace.id}`) return workspaceEnvelope(alpha);
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    renderAuthApplication(client, "/login");
    await user.type(await screen.findByLabelText("Email address"), "admin@example.invalid");
    await user.type(screen.getByLabelText("Password"), "synthetic-password-value");
    await user.click(screen.getByRole("button", { name: "Sign in securely" }));

    expect(await screen.findByRole("heading", { name: "Choose a workspace" })).toBeInTheDocument();
    expect(screen.queryByText("Workspace access is ready")).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: /Alpha workspace/ }));
    expect(
      await screen.findByRole("heading", { name: "Workspace access is ready" }),
    ).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Workspace navigation" })).toHaveTextContent(
      "Reports",
    );
    expect(client.credentials?.csrfToken).toBe("c".repeat(48));
  });

  it("clears the prior protected view before switching workspace", async () => {
    const alpha = membership("11111111-1111-4111-8111-111111111111", "Alpha workspace", "ADMIN");
    const beta = membership("22222222-2222-4222-8222-222222222222", "Beta workspace", "ADVISOR");
    const client = new FakeApiClient((path) => {
      if (path === "/setup/bootstrap") return { data: { available: false } };
      if (path === "/auth/login") return sessionEnvelope;
      if (path === "/me/workspaces") return { data: [alpha, beta] };
      if (path === `/workspaces/${alpha.workspace.id}`) return workspaceEnvelope(alpha);
      if (path === `/workspaces/${beta.workspace.id}`) return workspaceEnvelope(beta);
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    renderAuthApplication(client, "/login");
    await user.type(await screen.findByLabelText("Email address"), "user@example.invalid");
    await user.type(screen.getByLabelText("Password"), "synthetic-password-value");
    await user.click(screen.getByRole("button", { name: "Sign in securely" }));
    await user.click(await screen.findByRole("button", { name: /Alpha workspace/ }));
    await user.click(await screen.findByRole("button", { name: "Switch workspace" }));
    await user.click(screen.getByRole("button", { name: "Clear and continue" }));

    await waitFor(() =>
      expect(screen.queryByText("Workspace access is ready")).not.toBeInTheDocument(),
    );
    await user.click(screen.getByRole("button", { name: /Beta workspace/ }));
    expect(await screen.findByText("Beta workspace")).toBeInTheDocument();
    expect(screen.getByRole("navigation", { name: "Workspace navigation" })).not.toHaveTextContent(
      "Add",
    );
  });

  it("does not expose restricted Admin or report navigation to a Contributor", async () => {
    const contributor = membership(
      "33333333-3333-4333-8333-333333333333",
      "Contributor workspace",
      "CONTRIBUTOR",
    );
    const client = new FakeApiClient((path) => {
      if (path === "/setup/bootstrap") return { data: { available: false } };
      if (path === "/auth/login") return sessionEnvelope;
      if (path === "/me/workspaces") return { data: [contributor] };
      if (path === `/workspaces/${contributor.workspace.id}`) return workspaceEnvelope(contributor);
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    renderAuthApplication(client, "/login");
    await user.type(await screen.findByLabelText("Email address"), "member@example.invalid");
    await user.type(screen.getByLabelText("Password"), "synthetic-password-value");
    await user.click(screen.getByRole("button", { name: "Sign in securely" }));
    const navigation = await screen.findByRole("navigation", { name: "Workspace navigation" });
    expect(navigation).toHaveTextContent("Submissions");
    expect(navigation).not.toHaveTextContent("Reports");
    expect(navigation).not.toHaveTextContent("Transactions");
  });
});
