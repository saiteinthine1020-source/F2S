import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { I18nextProvider } from "react-i18next";

import { App } from "./app/App";
import { appI18n } from "./i18n";
import "./styles/global.css";

const root = document.querySelector<HTMLElement>("#root");
if (root === null) {
  throw new Error("APPLICATION_ROOT_MISSING");
}

createRoot(root).render(
  <StrictMode>
    <I18nextProvider i18n={appI18n}>
      <App />
    </I18nextProvider>
  </StrictMode>,
);
