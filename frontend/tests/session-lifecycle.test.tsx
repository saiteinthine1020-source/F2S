import { screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";

import { ApiError } from "../src/api/client";
import {
  FakeApiClient,
  membership,
  renderAuthApplication,
  sessionEnvelope,
  workspaceEnvelope,
} from "./auth-test-utils";

describe("session lifecycle", () => {
  it("fails safely to sign-in when an in-memory refresh is rejected", async () => {
    const item = membership("11111111-1111-4111-8111-111111111111", "Expiring workspace", "ADMIN");
    const expiringSession = {
      data: {
        ...sessionEnvelope.data,
        access_expires_at: new Date(Date.now() + 60_050).toISOString(),
      },
    };
    const client = new FakeApiClient((path) => {
      if (path === "/setup/bootstrap") return { data: { available: false } };
      if (path === "/auth/login") return expiringSession;
      if (path === "/me/workspaces") return { data: [item] };
      if (path === `/workspaces/${item.workspace.id}`) return workspaceEnvelope(item);
      if (path === "/auth/refresh") throw new ApiError(401, "UNAUTHENTICATED", null);
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    renderAuthApplication(client, "/login");
    await user.type(await screen.findByLabelText("Email address"), "admin@example.invalid");
    await user.type(screen.getByLabelText("Password"), "synthetic-password-value");
    await user.click(screen.getByRole("button", { name: "Sign in securely" }));
    expect(await screen.findByText("Expiring workspace")).toBeInTheDocument();

    expect(
      await screen.findByText("The session expired or was revoked. Sign in again.", undefined, {
        timeout: 2_500,
      }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Expiring workspace")).not.toBeInTheDocument();
    expect(client.credentials).toBeNull();
    expect(client.requests.filter((request) => request.path === "/auth/refresh")).toHaveLength(1);
  });

  it("clears all memory credentials even when logout transport fails", async () => {
    const item = membership("11111111-1111-4111-8111-111111111111", "Logout workspace", "ADMIN");
    const client = new FakeApiClient((path) => {
      if (path === "/setup/bootstrap") return { data: { available: false } };
      if (path === "/auth/login") return sessionEnvelope;
      if (path === "/me/workspaces") return { data: [item] };
      if (path === `/workspaces/${item.workspace.id}`) return workspaceEnvelope(item);
      if (path === "/auth/logout") throw new TypeError("NETWORK_UNAVAILABLE");
      throw new Error(`Unexpected request: ${path}`);
    });
    const user = userEvent.setup();
    renderAuthApplication(client, "/login");
    await user.type(await screen.findByLabelText("Email address"), "admin@example.invalid");
    await user.type(screen.getByLabelText("Password"), "synthetic-password-value");
    await user.click(screen.getByRole("button", { name: "Sign in securely" }));
    await user.click(await screen.findByRole("button", { name: "Sign out on this device" }));

    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect(client.credentials).toBeNull();
  });
});
