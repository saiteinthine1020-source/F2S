import { describe, expect, it } from "vitest";

import { listWorkspaces, login } from "../src/api/auth";
import { FakeApiClient } from "./auth-test-utils";

describe("authentication response contracts", () => {
  it("rejects malformed or expired session metadata before retaining credentials", async () => {
    const client = new FakeApiClient(() => ({
      data: {
        access_token: "a".repeat(48),
        csrf_token: "c".repeat(48),
        token_type: "Bearer",
        access_expires_at: "not-a-date",
        absolute_expires_at: "not-a-date",
      },
    }));
    await expect(login(client, "user@example.invalid", "synthetic-password-value")).rejects.toThrow(
      "SESSION_RESPONSE_INVALID",
    );
    expect(client.credentials).toBeNull();
  });

  it("rejects an untrusted workspace identifier before it can become a request path", async () => {
    const client = new FakeApiClient(() => ({
      data: [
        {
          membership_id: "11111111-1111-4111-8111-111111111111",
          role: "ADMIN",
          workspace: { id: "../foreign", name: "Unsafe" },
        },
      ],
    }));
    await expect(listWorkspaces(client)).rejects.toThrow("WORKSPACE_DIRECTORY_INVALID");
  });
});
