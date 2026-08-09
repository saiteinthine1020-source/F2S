import { describe, expect, it } from "vitest";

import { createI18n, supportedLocales } from "../src/i18n";

describe("localization foundation", () => {
  it("registers Shan, Myanmar, English, and Japanese with Shan first", () => {
    expect(supportedLocales).toEqual(["shn", "my", "en", "ja"]);
  });

  it("falls back from unreviewed Shan copy to reviewed English", () => {
    const i18n = createI18n("shn");
    expect(i18n.t("foundation.title")).toBe("Your workspace starts here");
    expect(i18n.resolvedLanguage).toBe("shn");
  });

  it("never exposes a raw unknown translation key", () => {
    const i18n = createI18n("ja");
    expect(i18n.t("unknown.raw.key")).toBe("This information is unavailable.");
  });
});
