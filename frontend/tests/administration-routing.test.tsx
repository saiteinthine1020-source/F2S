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

describe("workspace administration routing", () => {
  it("does not request or render administration resources for a Contributor direct route", async () => {
    const contributor = membership(
      "11111111-1111-4111-8111-111111111111",
      "Contributor workspace",
      "CONTRIBUTOR",
    );
    const client = authenticatedClient(contributor);
    const user = userEvent.setup();
    const { router } = renderAuthApplication(client, "/login");
    await signIn(user);
    await router.navigate("/app/admin/members");

    expect(
      await screen.findByRole("heading", { name: "Administration is unavailable" }),
    ).toBeInTheDocument();
    expect(screen.queryByText("Workspace members")).not.toBeInTheDocument();
    expect(client.requests.filter((request) => request.path.endsWith("/members"))).toEqual([]);
  });

  it("exposes administration only to Admin and stops a stale settings overwrite", async () => {
    const admin = membership("22222222-2222-4222-8222-222222222222", "Admin workspace", "ADMIN");
    const client = authenticatedClient(admin, (path, init) => {
      if (path === `/workspaces/${admin.workspace.id}` && init?.method === "PATCH") {
        throw new ApiError(412, "VERSION_MISMATCH", null);
      }
      return undefined;
    });
    const user = userEvent.setup();
    const { router } = renderAuthApplication(client, "/login");
    await signIn(user);
    expect(await screen.findByRole("link", { name: "Administration" })).toBeInTheDocument();
    await router.navigate("/app/admin/settings");

    const name = await screen.findByLabelText("Workspace name");
    await user.clear(name);
    await user.type(name, "Locally edited name");
    await user.click(screen.getByRole("button", { name: "Review settings change" }));
    await user.click(screen.getByRole("button", { name: "Apply settings" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Your change was not applied");
    expect(name).toHaveValue("Locally edited name");
    expect(screen.getByRole("button", { name: "Reload latest settings" })).toBeInTheDocument();
  });

  it("preserves member provisioning fields after a recoverable server failure", async () => {
    const admin = membership("33333333-3333-4333-8333-333333333333", "Member workspace", "ADMIN");
    const client = authenticatedClient(admin, (path, init) => {
      if (path.endsWith("/members") && init?.method === "POST") {
        throw new ApiError(422, "VALIDATION_FAILED", null);
      }
      return undefined;
    });
    const user = userEvent.setup();
    const { router } = renderAuthApplication(client, "/login");
    await signIn(user);
    await router.navigate("/app/admin/members");

    const displayName = await screen.findByLabelText("Your name");
    const email = screen.getByLabelText("Email address");
    await user.type(displayName, "Preserved member");
    await user.type(email, "member@example.invalid");
    await user.click(screen.getByRole("button", { name: "Create pending member" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("non-secret entries remain");
    expect(displayName).toHaveValue("Preserved member");
    expect(email).toHaveValue("member@example.invalid");
  });

  it("lets the selected target confirm ownership without exposing evidence in the URL", async () => {
    const contributor = membership(
      "44444444-4444-4444-8444-444444444444",
      "Transfer workspace",
      "CONTRIBUTOR",
    );
    const transferId = "55555555-5555-4555-8555-555555555555";
    const evidence = "e".repeat(48);
    const client = authenticatedClient(contributor, (path) => {
      if (path.endsWith(`ownership-transfers/${transferId}/confirm`)) {
        return {
          data: {
            id: transferId,
            workspace_id: contributor.workspace.id,
            current_owner_membership_id: "66666666-6666-4666-8666-666666666666",
            target_membership_id: contributor.membership_id,
            former_owner_role: "CONTRIBUTOR",
            status: "COMPLETED",
            expires_at: new Date(Date.now() + 30 * 60_000).toISOString(),
            version: 2,
          },
        };
      }
      if (path === "/auth/logout") return undefined;
      return undefined;
    });
    const user = userEvent.setup();
    const { router } = renderAuthApplication(client, "/login");
    await signIn(user);
    await router.navigate("/app/ownership/confirm");
    await user.type(await screen.findByLabelText("Transfer ID"), transferId);
    await user.type(screen.getByLabelText("Ownership confirmation code"), evidence);
    await user.click(screen.getByLabelText(/I understand I will become the sole Admin owner/u));
    await user.click(screen.getByRole("button", { name: "Confirm ownership transfer" }));

    expect(await screen.findByText(/Ownership transfer completed/u)).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/login");
    expect(router.state.location.search).toBe("");
    expect(JSON.stringify(router.state.location)).not.toContain(evidence);
  });
});

function authenticatedClient(
  item: ReturnType<typeof membership>,
  override?: (path: string, init: RequestInit | undefined) => unknown,
) {
  return new FakeApiClient((path, init) => {
    const overridden = override?.(path, init);
    if (overridden !== undefined) return overridden;
    if (path === "/setup/bootstrap") return { data: { available: false } };
    if (path === "/auth/login") return sessionEnvelope;
    if (path === "/me/workspaces") return { data: [item] };
    if (path === `/workspaces/${item.workspace.id}`) {
      return {
        ...workspaceEnvelope(item),
        data: {
          ...workspaceEnvelope(item).data,
          administration: {
            description: null,
            address: null,
            business_category_code: null,
            farm_type_code: null,
          },
        },
      };
    }
    if (path === `/workspaces/${item.workspace.id}/members` && init?.method === undefined) {
      return { data: [] };
    }
    if (path === "/auth/logout") return undefined;
    throw new Error(`Unexpected request: ${path}`);
  });
}

async function signIn(user: ReturnType<typeof userEvent.setup>) {
  await user.type(await screen.findByLabelText("Email address"), "user@example.invalid");
  await user.type(screen.getByLabelText("Password"), "synthetic-password-value");
  await user.click(screen.getByRole("button", { name: "Sign in securely" }));
  await screen.findByRole("heading", { name: "Workspace access is ready" });
}
