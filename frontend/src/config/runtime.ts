export class RuntimeConfigurationError extends Error {
  constructor() {
    super("RUNTIME_CONFIGURATION_INVALID");
    this.name = "RuntimeConfigurationError";
  }
}

export interface RuntimeConfig {
  readonly apiBaseUrl: string;
}

export type RuntimeEnvironment = Readonly<Record<string, unknown>>;

export function loadRuntimeConfig(environment: RuntimeEnvironment): RuntimeConfig {
  const rawApiBaseUrl = environment.VITE_API_BASE_URL;
  if (typeof rawApiBaseUrl !== "string" || rawApiBaseUrl.trim() !== rawApiBaseUrl) {
    throw new RuntimeConfigurationError();
  }

  let parsed: URL;
  try {
    parsed = new URL(rawApiBaseUrl);
  } catch {
    throw new RuntimeConfigurationError();
  }
  if (
    !["http:", "https:"].includes(parsed.protocol) ||
    parsed.username !== "" ||
    parsed.password !== "" ||
    parsed.search !== "" ||
    parsed.hash !== "" ||
    !parsed.hostname ||
    parsed.pathname === "/"
  ) {
    throw new RuntimeConfigurationError();
  }

  return Object.freeze({
    apiBaseUrl: parsed.toString().replace(/\/$/, ""),
  });
}
