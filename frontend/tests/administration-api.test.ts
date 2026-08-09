import { describe, expect, it, vi } from "vitest";

import {
  cancelOwnershipTransfer,
  changeMemberRole,
  updateWorkspaceSettings,
} from "../src/api/administration";
import { createApiClient } from "../src/api/client";
import type { MemberRecord, OwnershipTransfer } from "../src/api/contracts";

const workspaceId = "11111111-1111-4111-8111-111111111111";
const memberId = "22222222-2222-4222-8222-222222222222";

describe("administration API contracts", () => {
  it("sends CSRF and the exact workspace version for settings updates", async () => {
    const fetchMock = vi.fn<typeof fetch>().mockResolvedValue(
      new Response(
        JSON.stringify({
          data: {
            workspace: {
              id: workspaceId,
              name: "Updated",
              type: "HOUSEHOLD",
              base_currency_code: "JPY",
              timezone: "Asia/Tokyo",
              preferred_language: "en",
              version: 4,
            },
            modules: [],
            administration: {
              description: null,
              address: null,
              business_category_code: null,
              farm_type_code: null,
            },
          },
        }),
        { status: 200, headers: { "Content-Type": "application/json" } },
      ),
    );
    const client = createApiClient({ apiBaseUrl: "https://api.example.invalid/api/v1" }, fetchMock);
    client.setSessionCredentials({ accessToken: "a".repeat(48), csrfToken: "c".repeat(48) });

    await updateWorkspaceSettings(client, workspaceId, 3, {
      name: "Updated",
      type: "HOUSEHOLD",
      base_currency_code: "JPY",
      timezone: "Asia/Tokyo",
      preferred_language: "en",
      description: null,
      address: null,
      business_category_code: null,
      farm_type_code: null,
      modules: [],
    });

    const request = fetchMock.mock.calls[0]?.[1];
    const headers = new Headers(request?.headers);
    expect(request?.method).toBe("PATCH");
    expect(headers.get("If-Match")).toBe('"v3"');
    expect(headers.get("X-CSRF-Token")).toBe("c".repeat(48));
  });

  it("uses the member version for role changes and transfer version for cancellation", async () => {
    const member = memberRecord();
    const transfer = transferRecord();
    const fetchMock = vi
      .fn<typeof fetch>()
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ data: { ...member, role: "ADVISOR", version: 6 } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 204 }));
    const client = createApiClient({ apiBaseUrl: "https://api.example.invalid/api/v1" }, fetchMock);
    client.setSessionCredentials({ accessToken: "a".repeat(48), csrfToken: "c".repeat(48) });

    await changeMemberRole(client, workspaceId, member, "ADVISOR");
    await cancelOwnershipTransfer(client, transfer);

    expect(new Headers(fetchMock.mock.calls[0]?.[1]?.headers).get("If-Match")).toBe('"v5"');
    expect(new Headers(fetchMock.mock.calls[1]?.[1]?.headers).get("If-Match")).toBe('"v2"');
  });
});

function memberRecord(): MemberRecord {
  return {
    id: memberId,
    email: "member@example.invalid",
    display_name: "Member",
    role: "CONTRIBUTOR",
    status: "ACTIVE",
    account_status: "ACTIVE",
    preferred_language: "en",
    timezone: "Asia/Tokyo",
    last_login_at: null,
    created_at: new Date().toISOString(),
    version: 5,
  };
}

function transferRecord(): OwnershipTransfer {
  return {
    id: "33333333-3333-4333-8333-333333333333",
    workspace_id: workspaceId,
    current_owner_membership_id: "44444444-4444-4444-8444-444444444444",
    target_membership_id: memberId,
    former_owner_role: "CONTRIBUTOR",
    status: "INITIATED",
    expires_at: new Date(Date.now() + 30 * 60_000).toISOString(),
    version: 2,
  };
}
