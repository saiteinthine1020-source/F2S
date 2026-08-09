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
    client.setSessionCredentials({ accessToken: credential, csrfToken: "c".repeat(48) });
    await client.request<{ data: { status: string } }>("/health");

    const headers = new Headers(observedInit?.headers);
    expect(observedInit?.credentials).toBe("include");
    expect(headers.get("Authorization")).toBe(`Bearer ${credential}`);
    client.setSessionCredentials(null);
  });

  it("adds the session-bound CSRF header only when explicitly required", async () => {
    let observedHeaders = new Headers();
    const fetchMock = vi.fn(async (...parameters: Parameters<typeof fetch>): Promise<Response> => {
      observedHeaders = new Headers(parameters[1]?.headers);
      return new Response(null, { status: 204 });
    });
    const client = createApiClient({ apiBaseUrl: "https://api.example.invalid/api/v1" }, fetchMock);
    client.setSessionCredentials({ accessToken: "a".repeat(48), csrfToken: "c".repeat(48) });
    await client.request(
      "/auth/logout",
      { method: "POST", body: "{}" },
      { authorization: "omit", csrf: true },
    );

    expect(observedHeaders.get("Authorization")).toBeNull();
    expect(observedHeaders.get("X-CSRF-Token")).toBe("c".repeat(48));
  });

  it("refuses a CSRF request when no in-memory session is available", async () => {
    const client = createApiClient({ apiBaseUrl: "https://api.example.invalid/api/v1" }, vi.fn());
    await expect(
      client.request("/auth/refresh", { method: "POST", body: "{}" }, { csrf: true }),
    ).rejects.toThrow("CSRF_CREDENTIAL_UNAVAILABLE");
  });

  it("invalidates protected state on a bearer-authenticated 401 but not a public 401", async () => {
    const handler = vi.fn();
    const fetchMock = vi.fn(
      async () =>
        new Response(JSON.stringify({ error: { code: "UNAUTHENTICATED" } }), {
          status: 401,
          headers: { "Content-Type": "application/json" },
        }),
    );
    const client = createApiClient({ apiBaseUrl: "https://api.example.invalid/api/v1" }, fetchMock);
    client.setSessionCredentials({ accessToken: "a".repeat(48), csrfToken: "c".repeat(48) });
    client.setUnauthorizedHandler(handler);

    await expect(client.request("/me/workspaces")).rejects.toMatchObject({ status: 401 });
    expect(handler).toHaveBeenCalledOnce();
    await expect(
      client.request("/auth/login", { method: "POST", body: "{}" }, { authorization: "omit" }),
    ).rejects.toMatchObject({ status: 401 });
    expect(handler).toHaveBeenCalledOnce();
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
