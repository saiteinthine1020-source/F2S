import type { ReactElement } from "react";
import { render, type RenderResult } from "@testing-library/react";
import { I18nextProvider } from "react-i18next";
import { MemoryRouter } from "react-router-dom";

import { createI18n, type SupportedLocale } from "../src/i18n";

interface RenderOptions {
  readonly language?: SupportedLocale;
  readonly route?: string;
  readonly withRouter?: boolean;
}

export function renderLocalized(
  element: ReactElement,
  { language = "en", route = "/", withRouter = true }: RenderOptions = {},
): RenderResult {
  const i18n = createI18n(language);
  return render(
    <I18nextProvider i18n={i18n}>
      {withRouter ? <MemoryRouter initialEntries={[route]}>{element}</MemoryRouter> : element}
    </I18nextProvider>,
  );
}
