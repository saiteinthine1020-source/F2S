import { describe, expect, it, vi } from "vitest";

import { createApiClient } from "../src/api/client";

describe("API boundary", () => {
  it("uses secure cookies and holds an access credential only in memory", async () => {
    let observedInit: RequestInit | undefined;
    const fetchMock = vi.fn(async (...parameters: Parameters<typeof fetch>): Promise<Response> => {
      observedInit = parameters[1];
      return Promise.resolve(
        new Response(JSON.stringify({ data: { status: "ok" } }), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    });
    const client = createApiClient({ apiBaseUrl: "https://api.example.invalid/api/v1" }, fetchMock);
    const credential = "x".repeat(48);
    client.setAccessCredential(credential);
    await client.request<{ data: { status: string } }>("/health");

    const headers = new Headers(observedInit?.headers);
    expect(observedInit?.credentials).toBe("include");
    expect(headers.get("Authorization")).toBe(`Bearer ${credential}`);
    client.setAccessCredential(null);
  });

  it("maps only bounded error codes and never trusts server messages", async () => {
    const fetchMock = vi.fn(async () =>
      Promise.resolve(
        new Response(
          JSON.stringify({ error: { code: "RESOURCE_NOT_FOUND", message: "unsafe detail" } }),
          {
            status: 404,
            headers: {
              "Content-Type": "application/json",
              "X-Correlation-ID": "11111111-1111-4111-8111-111111111111",
            },
          },
        ),
      ),
    );
    const client = createApiClient({ apiBaseUrl: "https://api.example.invalid/api/v1" }, fetchMock);
    await expect(client.request("/workspaces/unknown")).rejects.toMatchObject({
      status: 404,
      code: "RESOURCE_NOT_FOUND",
      message: "API_REQUEST_FAILED",
    });
  });

  it("rejects absolute or protocol-relative request paths", async () => {
    const client = createApiClient({ apiBaseUrl: "https://api.example.invalid/api/v1" }, vi.fn());
    await expect(client.request("https://hostile.invalid")).rejects.toThrow("API_PATH_INVALID");
    await expect(client.request("//hostile.invalid")).rejects.toThrow("API_PATH_INVALID");
  });
});
