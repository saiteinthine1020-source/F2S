import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { createMemoryRouter, RouterProvider } from "react-router-dom";

import type { ApiClient, RequestSecurity, SessionCredentials } from "../src/api/client";
import { ApiClientContext } from "../src/app/ApiClientContext";
import { appRoutes } from "../src/app/router";
import { AuthProvider } from "../src/auth/AuthProvider";
import { createI18n } from "../src/i18n";

export type RequestHandler = (
  path: string,
  init: RequestInit | undefined,
  security: RequestSecurity | undefined,
) => unknown | Promise<unknown>;

export class FakeApiClient implements ApiClient {
  credentials: SessionCredentials | null = null;
  readonly requests: Array<{ path: string; init?: RequestInit; security?: RequestSecurity }> = [];

  constructor(private readonly handler: RequestHandler) {}

  setUnauthorizedHandler(): void {
    // Tests invoke lifecycle failures through explicit fake responses.
  }

  setSessionCredentials(value: SessionCredentials | null): void {
    this.credentials = value;
  }

  async request<T>(path: string, init?: RequestInit, security?: RequestSecurity): Promise<T> {
    this.requests.push({ path, init, security });
    return (await this.handler(path, init, security)) as T;
  }
}

export function renderAuthApplication(
  client: ApiClient,
  route = "/",
): RenderResult & { readonly router: ReturnType<typeof createMemoryRouter> } {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false, gcTime: 0 }, mutations: { retry: false } },
  });
  const router = createMemoryRouter(appRoutes, { initialEntries: [route] });
  const result = render(
    <I18nextProvider i18n={createI18n("en")}>
      <ApiClientContext.Provider value={client}>
        <QueryClientProvider client={queryClient}>
          <AuthProvider>
            <RouterProvider router={router} />
          </AuthProvider>
        </QueryClientProvider>
      </ApiClientContext.Provider>
    </I18nextProvider>,
  );
  return { ...result, router };
}

export const sessionEnvelope = {
  data: {
    access_token: "a".repeat(48),
    csrf_token: "c".repeat(48),
    token_type: "Bearer" as const,
    access_expires_at: new Date(Date.now() + 15 * 60_000).toISOString(),
    absolute_expires_at: new Date(Date.now() + 30 * 24 * 60 * 60_000).toISOString(),
  },
};

export function membership(id: string, name: string, role: "ADMIN" | "CONTRIBUTOR" | "ADVISOR") {
  return {
    membership_id: id,
    role,
    workspace: {
      id,
      name,
      type: "HOUSEHOLD" as const,
      base_currency_code: "JPY",
      timezone: "Asia/Tokyo",
      preferred_language: "en" as const,
      version: 1,
    },
  };
}

export function workspaceEnvelope(item: ReturnType<typeof membership>) {
  return { data: { workspace: item.workspace, modules: [] } };
}
