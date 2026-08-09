import i18next, { type i18n } from "i18next";
import { initReactI18next } from "react-i18next";

import { en } from "./resources/en";
import { ja } from "./resources/ja";
import { my } from "./resources/my";
import { shn } from "./resources/shn";

export const supportedLocales = ["shn", "my", "en", "ja"] as const;
export type SupportedLocale = (typeof supportedLocales)[number];

export function createI18n(language: SupportedLocale = "shn"): i18n {
  const instance = i18next.createInstance();
  void instance.use(initReactI18next).init({
    resources: { en, ja, my, shn },
    lng: language,
    supportedLngs: supportedLocales,
    fallbackLng: "en",
    initAsync: false,
    interpolation: { escapeValue: false },
    returnEmptyString: false,
    parseMissingKeyHandler: () => en.translation.errors.unavailable,
  });
  return instance;
}

export const appI18n = createI18n();
