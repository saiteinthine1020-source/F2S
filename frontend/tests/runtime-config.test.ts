import { describe, expect, it } from "vitest";

import { loadRuntimeConfig, RuntimeConfigurationError } from "../src/config/runtime";

describe("runtime configuration", () => {
  it("accepts and normalizes one explicit HTTP(S) API base URL", () => {
    expect(loadRuntimeConfig({ VITE_API_BASE_URL: "https://api.example.invalid/api/v1/" })).toEqual(
      { apiBaseUrl: "https://api.example.invalid/api/v1" },
    );
  });

  it.each([
    {},
    { VITE_API_BASE_URL: "" },
    { VITE_API_BASE_URL: " /api/v1" },
    { VITE_API_BASE_URL: "/api/v1" },
    { VITE_API_BASE_URL: "ftp://api.example.invalid/api/v1" },
    { VITE_API_BASE_URL: "https://user:password@api.example.invalid/api/v1" },
    { VITE_API_BASE_URL: "https://api.example.invalid/api/v1?secret=value" },
    { VITE_API_BASE_URL: "https://api.example.invalid/" },
  ])("fails closed without echoing invalid configuration: %j", (environment) => {
    expect(() => loadRuntimeConfig(environment)).toThrow(RuntimeConfigurationError);
    try {
      loadRuntimeConfig(environment);
    } catch (error) {
      expect(String(error)).not.toContain(JSON.stringify(environment));
    }
  });
});
