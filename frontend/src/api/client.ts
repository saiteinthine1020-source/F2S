import type { RuntimeConfig } from "../config/runtime";

const SAFE_ERROR_CODE = /^[A-Z][A-Z0-9_]{0,63}$/;

export class ApiError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    readonly correlationId: string | null,
  ) {
    super("API_REQUEST_FAILED");
    this.name = "ApiError";
  }
}

export interface ApiClient {
  setSessionCredentials(value: SessionCredentials | null): void;
  setUnauthorizedHandler(handler: (() => void) | null): void;
  request<T>(path: string, init?: RequestInit, security?: RequestSecurity): Promise<T>;
}

export interface SessionCredentials {
  readonly accessToken: string;
  readonly csrfToken: string;
}

export interface RequestSecurity {
  readonly authorization?: "include" | "omit";
  readonly csrf?: boolean;
}

export function createApiClient(
  config: RuntimeConfig,
  fetchImplementation: typeof fetch = fetch,
): ApiClient {
  let credentials: SessionCredentials | null = null;
  let unauthorizedHandler: (() => void) | null = null;

  return Object.freeze({
    setSessionCredentials(value: SessionCredentials | null): void {
      if (value !== null && (!isCredential(value.accessToken) || !isCredential(value.csrfToken))) {
        throw new TypeError("SESSION_CREDENTIALS_INVALID");
      }
      credentials = value;
    },

    setUnauthorizedHandler(handler: (() => void) | null): void {
      unauthorizedHandler = handler;
    },

    async request<T>(
      path: string,
      init: RequestInit = {},
      security: RequestSecurity = {},
    ): Promise<T> {
      if (!path.startsWith("/") || path.startsWith("//")) {
        throw new TypeError("API_PATH_INVALID");
      }
      const headers = new Headers(init.headers);
      headers.set("Accept", "application/json");
      if (init.body !== undefined && !headers.has("Content-Type")) {
        headers.set("Content-Type", "application/json");
      }
      if (security.authorization !== "omit" && credentials !== null) {
        headers.set("Authorization", `Bearer ${credentials.accessToken}`);
      }
      if (security.csrf === true) {
        if (credentials === null) {
          throw new TypeError("CSRF_CREDENTIAL_UNAVAILABLE");
        }
        headers.set("X-CSRF-Token", credentials.csrfToken);
      }

      const response = await fetchImplementation(`${config.apiBaseUrl}${path}`, {
        ...init,
        headers,
        credentials: "include",
      });
      if (!response.ok) {
        const code = await safeErrorCode(response);
        if (response.status === 401 && security.authorization !== "omit" && credentials !== null) {
          unauthorizedHandler?.();
        }
        throw new ApiError(response.status, code, response.headers.get("X-Correlation-ID"));
      }
      if (response.status === 204) {
        return undefined as T;
      }
      return (await response.json()) as T;
    },
  });
}

function isCredential(value: string): boolean {
  return value.length >= 32 && value.length <= 512;
}

async function safeErrorCode(response: Response): Promise<string> {
  try {
    const payload = (await response.clone().json()) as unknown;
    if (
      typeof payload === "object" &&
      payload !== null &&
      "error" in payload &&
      typeof payload.error === "object" &&
      payload.error !== null &&
      "code" in payload.error &&
      typeof payload.error.code === "string" &&
      SAFE_ERROR_CODE.test(payload.error.code)
    ) {
      return payload.error.code;
    }
  } catch {
    // The UI maps this bounded fallback and never renders an untrusted server payload.
  }
  return "REQUEST_FAILED";
}
