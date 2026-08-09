# F2S frontend

This directory contains the Phase 1 React and TypeScript application. It provides the build,
routing, runtime configuration, API, localization, authentication, protected workspace shell,
accessible state components, and test boundaries needed by later business issues. It includes
Phase 1 workspace and member administration but intentionally contains no financial feature,
service worker, offline queue, or sample business data.

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
`credentials: "include"` for the server's secure cookie contract and keeps short-lived access
and synchronizer-CSRF values only in a module closure. It does not use browser persistent
storage.

## Authentication and protected routing

The client implements one-time bootstrap, activation, login, concealed recovery, password
change, logout, workspace selection, and role-aware navigation. The protected route boundary
renders no workspace directory, workspace name, role, navigation, or page content until the
server has accepted the access credential and selected-workspace request.

Login returns an opaque access value and synchronizer-CSRF value to browser memory while the
opaque refresh value remains in the `Secure`, `HttpOnly`, `SameSite=Strict` cookie. The client:

- attaches the access value only to protected requests;
- attaches CSRF only to refresh, logout, and protected browser mutations that explicitly
  require it;
- schedules one refresh before access expiry and never starts parallel refreshes;
- clears credentials, TanStack Query state, and selected workspace before logout, expiry,
  revocation, unsafe refresh failure, or workspace switching; and
- treats role-specific navigation as clarity only, never authorization.

A full reload destroys both readable credentials. The current backend has no approved
same-origin, non-mutating CSRF-bootstrap endpoint, so the client fails safely to sign-in rather
than rotating the HttpOnly cookie without its session-bound synchronizer value. If that API is
added later, it must remain `no-store`, return no protected workspace data, and preserve the
single-flight zero-grace refresh rule.

Public activation/recovery evidence is entered in password-style fields and is never read from
the URL. Recovery request and proof failures use generic translated copy that does not disclose
whether an account, owner, challenge, or foreign workspace exists.

## Workspace administration

Only an authenticated Admin sees the **Administration** destination. The nested routes are:

- `/app/admin/settings` for versioned workspace identity, profile, and module settings;
- `/app/admin/members` for member provisioning, role changes, suspension, reactivation,
  activation restart, and revocation;
- `/app/admin/ownership` for owner reauthentication, consequence confirmation, initiation,
  outcome, expiry, and cancellation; and
- `/app/ownership/confirm` for the selected target member to submit the transfer ID and
  single-use confirmation value without URL evidence.

Contributor and Advisor direct visits to Admin routes render no administration resource and
make no administration API request. This is a privacy optimization, not authorization: every
Admin request can still receive a safe backend denial if the client role is stale. Settings,
membership, and cancellation writes send the last observed version through `If-Match`. A `412`
stops the write, preserves appropriate non-secret input, and requires an explicit latest-state
reload; the client never retries a stale mutation automatically.

Destructive and privilege-changing actions require a labelled confirmation. Ownership
initiation additionally requires the current password and an explicit consequence checkbox.
Confirmation completes only for the authenticated target membership, atomically changes the
roles on the server, revokes both affected accounts' sessions, and destroys local protected
state before explaining that both users must sign in again.

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
pnpm exec playwright install chromium
pnpm test:e2e
pnpm build
```

The current tests cover runtime configuration, English fallback and missing keys, browser
persistent-storage exclusion, secure-cookie and memory-only API/CSRF credentials, public and
protected routing, role navigation, expiry/revocation, failed logout, workspace switching,
concealed recovery, Admin-only no-request routing, optimistic conflict handling, workspace and
member administration, ownership reauthentication/confirmation, translated states, semantic
landmarks, keyboard skip access, automated axe smoke checks, and Chromium critical flows.
Automated scanning supplements rather than replaces screen-reader, zoom, touch, contrast, Shan
linguistic, and reference-device review.

## Foundation structure

```text
src/
|-- api/          memory-only credential, safe fetch, and typed administration boundaries
|-- app/          providers, router, and translated error boundary
|-- auth/         in-memory session lifecycle and public/protected route guards
|-- components/   responsive forms, shells, and honest standard states
|-- config/       fail-closed public runtime configuration
|-- i18n/         locale registry and translation resources
|-- pages/        authentication, workspace-selection, protected, and safe fallback routes
`-- styles/       accessible tokens and mobile-first global styles
```

Backend authorization remains authoritative. The UI hides unavailable navigation for clarity,
but never treats visibility, route presence, selected-workspace state, or client role as
permission.
