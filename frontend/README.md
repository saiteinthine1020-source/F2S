# F2S frontend

This directory contains the Phase 1 React and TypeScript application foundation. It provides
the build, routing, runtime-configuration, API, localization, error-boundary, responsive shell,
accessible state-component, and test boundaries needed by later authentication and workspace
issues. It intentionally contains no authentication behavior, workspace/member screen,
financial feature, service worker, offline queue, or sample business data.

## Prerequisites

- Node.js `24.x` (`24.18.1` in CI)
- pnpm `11.20.0`

The exact application and development packages are recorded in `package.json` and
`pnpm-lock.yaml`. Do not use an unlocked install or commit `node_modules`, `dist`, coverage, or
TypeScript build-info output.

## Local configuration

Copy the synthetic example and keep the resulting `.env.local` file untracked:

```powershell
Copy-Item .env.example .env.local
```

The only frontend runtime variable is:

| Variable            | Example                        | Rule                                                                       |
| ------------------- | ------------------------------ | -------------------------------------------------------------------------- |
| `VITE_API_BASE_URL` | `http://127.0.0.1:8000/api/v1` | Required absolute HTTP(S) API base with no credentials, query, or fragment |

Vite embeds every `VITE_` variable in the browser bundle. Never place a password, digest key,
access/refresh/CSRF value, provider credential, private URL credential, or other secret in a
frontend environment variable. Invalid configuration fails closed through a translated safe
application state and never echoes the submitted value.

## Install and run

```powershell
pnpm install --frozen-lockfile --strict-peer-dependencies
pnpm dev
```

The development app defaults to Vite's loopback URL. The API client uses
`credentials: "include"` for the server's secure cookie contract and keeps a short-lived access
credential only in a module closure. It does not use browser persistent storage. Authentication
and credential lifecycle behavior belongs to Issue #56.

## Localization

The supported locale order is Shan (`shn`), Myanmar (`my`), English (`en`), and Japanese
(`ja`). Shan is requested initially and English is the safe fallback. Every visible and
assistive application string uses a semantic translation key; an unknown key resolves to a
safe generic message instead of appearing in the interface.

The Shan, Myanmar, and Japanese resource modules are intentionally partial until linguistic
review approves critical-flow copy. Do not fill them with machine-generated text and present it
as approved. Add reviewed translations as complete semantic keys, test fallback and expansion,
and preserve the UI/UX design's 320 CSS-pixel reflow and 30-percent text-expansion requirements.

## Validate

Run the same merge gates used by GitHub Actions:

```powershell
pnpm format:check
pnpm lint
pnpm typecheck
pnpm test
pnpm build
```

The current tests cover runtime configuration, English fallback and missing keys, browser
persistent-storage exclusion, secure-cookie and memory-only API credentials, safe API errors,
routing, translated loading/error/not-found states, semantic landmarks, keyboard skip access,
and automated axe smoke checks. Automated scanning supplements rather than replaces later
keyboard, screen-reader, zoom, touch, contrast, Shan linguistic, and reference-device review.

## Foundation structure

```text
src/
|-- api/          memory-only credential and safe fetch boundary
|-- app/          providers, router, and translated error boundary
|-- components/   responsive shell and honest standard states
|-- config/       fail-closed public runtime configuration
|-- i18n/         locale registry and translation resources
|-- pages/        foundation and safe not-found routes only
`-- styles/       accessible tokens and mobile-first global styles
```

Backend authorization remains authoritative. A later UI may hide unavailable actions for
clarity, but it must never treat visibility, route presence, or client state as permission.
