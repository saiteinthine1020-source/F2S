import { screen } from "@testing-library/react";
import { axe } from "vitest-axe";
import { describe, expect, it } from "vitest";

import { FakeApiClient, renderAuthApplication } from "./auth-test-utils";

const axeOptions = { rules: { "color-contrast": { enabled: false } } } as const;

describe("authentication accessibility", () => {
  it("renders the sign-in flow without detectable structural accessibility violations", async () => {
    const client = new FakeApiClient((path) => {
      if (path === "/setup/bootstrap") return { data: { available: false } };
      throw new Error(`Unexpected request: ${path}`);
    });
    const { container } = renderAuthApplication(client, "/login");
    expect(await screen.findByRole("heading", { name: "Sign in" })).toBeInTheDocument();
    expect((await axe(container, axeOptions)).violations).toEqual([]);
  });

  it("renders every required one-time bootstrap field with an accessible label", async () => {
    const client = new FakeApiClient((path) => {
      if (path === "/setup/bootstrap") return { data: { available: true } };
      throw new Error(`Unexpected request: ${path}`);
    });
    const { container } = renderAuthApplication(client, "/setup");
    expect(
      await screen.findByRole("heading", { name: "Create the first secure workspace" }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Your name")).toBeRequired();
    expect(screen.getByLabelText("Workspace name")).toBeRequired();
    expect(screen.getByLabelText("Base currency code")).toBeRequired();
    expect((await axe(container, axeOptions)).violations).toEqual([]);
  });
});
