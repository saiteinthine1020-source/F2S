# Contributing to F2S

Thank you for helping improve F2S. Contributions must protect household privacy, preserve financial correctness and stay within the active project phase.

By participating, you agree to follow the [Code of Conduct](CODE_OF_CONDUCT.md), [Security Policy](SECURITY.md), repository [governance rules](docs/project_management/Repository_Governance.md) and the existing [MIT License](LICENSE).

## 1. Current project status

F2S is in **Phase 0 - Foundation and Documentation**. No frontend or backend application feature has been implemented. Application code, infrastructure provisioning and future-phase features are not accepted unless a specific approved GitHub issue authorises that work.

Start with:

- [README.md](README.md);
- [Documentation Index](docs/00_Documentation_Index.md);
- [Project Overview](docs/01_Project_Overview.md);
- [System Architecture](docs/07_System_Architecture.md);
- [Security Design](docs/15_Security_Design.md);
- [Test Strategy](docs/17_Test_Strategy.md); and
- [Repository Governance](docs/project_management/Repository_Governance.md).

## 2. Choose work through an issue

Before making a material change:

1. Search existing issues and pull requests.
2. Use or request one focused issue with goal, scope, acceptance criteria, dependencies, security/privacy impact, database/API impact, validation and out-of-scope items.
3. Confirm the issue belongs to the active milestone and its dependencies are satisfied.
4. Keep one issue per branch and one focused pull request per issue.

Do not place vulnerability details in a public issue. Follow [SECURITY.md](SECURITY.md).

Small typo/link fixes may be proposed directly when their scope and validation are obvious, but maintainers may request an issue for traceability.

## 3. Branch and commit conventions

Create branches from current `main`:

- automated coding agents: `agent/<short-description>`;
- documentation: `docs/<short-description>`;
- features: `feat/<short-description>`;
- fixes: `fix/<short-description>`; and
- repository/maintenance: `chore/<short-description>`.

Use lowercase hyphen-separated names without personal data or secrets. Do not work directly on `main`.

Write small, meaningful commits. A useful commit subject is imperative and scoped, for example `docs: clarify recovery verification`. Do not mix formatting sweeps, generated dependencies or unrelated cleanup into a feature change.

## 4. Protect data and secrets

All examples, fixtures, screenshots and test artifacts must be synthetic. Never use real family names, contact details, locations, bank/payment data, transaction references, credentials, exported reports, attachments or unmasked AI source.

Do not commit:

- `.env` files or production configuration;
- passwords, tokens, cookies, private keys, API keys or connection strings;
- real household, finance, farming or provider data;
- generated dependency/vendor directories;
- private vulnerability or conduct reports; or
- logs/traces/screenshots containing prohibited values.

Use obvious non-working placeholders only where documentation requires a value. A secret scanner passing does not prove a contribution is safe; inspect the full diff and generated artifacts.

If you discover or submit sensitive material, stop sharing it publicly and follow the Security Policy. Do not rely on a follow-up deletion commit as remediation.

## 5. Architecture and correctness expectations

- Preserve the modular-monolith boundaries and public module contracts.
- PostgreSQL and backend services enforce household isolation; frontend filtering is never authority.
- Financial values use the accepted decimal, currency, unit and rounding rules; binary floating point is prohibited for authoritative values.
- Calculations have one backend source of truth and are not duplicated in routes, UI, reports or AI prompts.
- Corrections/reversals preserve history; ordinary flows do not silently rewrite posted facts.
- Empty states and examples never fabricate household totals, investments, recommendations or charts.
- AI only explains authorised verified masked data and never originates authoritative calculations.
- Security-sensitive configuration fails closed.

A material deviation requires an ADR or design update in the same issue.

## 6. Documentation changes

Documentation uses English for engineering content and stable requirement identifiers where applicable. Shan is the initial user-facing language; UI text belongs in the future internationalisation layer, not hardcoded documentation-driven application code.

When changing documentation:

- update every affected index/link and source-of-truth reference;
- distinguish approved, baseline, provisional, planned, deferred and unverified claims;
- include normal, failure, recovery, isolation and privacy behavior where relevant;
- keep Mermaid diagrams syntactically clear and label ambiguous relationships;
- do not claim a tool, test, control, deployment or restore exists unless executed evidence exists; and
- update [CHANGELOG.md](CHANGELOG.md) under `Unreleased` for a notable repository/product change.

## 7. Validation

Run the checks relevant to the actual change. During the documentation-only foundation, at minimum:

```powershell
git diff --check
git status --short
```

Also verify local Markdown links, inspect every changed file and confirm that no application code, secret, generated dependency or real data was introduced. A documentation-only pull request reports application suites as `NOT APPLICABLE/NOT RUN`, not passed.

As implementation begins, use the commands and required checks added by the owning scaffold/CI issues. Do not install or invent a substitute stack merely to claim a check passed. PostgreSQL-specific behavior must not be tested against SQLite.

The Phase 0 CI commands, tool versions, controlled-failure behavior and required check names are defined in [Continuous Integration](docs/project_management/Continuous_Integration.md). Run every locally available equivalent before pushing and report unavailable checks as `NOT RUN` or `BLOCKED`.

## 8. Pull requests

Open a draft pull request by default. Its description should include:

- the linked issue (`Closes #...` only when merge should close it);
- what changed and why;
- user/developer/security/data impact;
- files and contracts affected;
- validation commands/results, including `NOT RUN`/`BLOCKED`/`NOT APPLICABLE` honestly;
- screenshots or artifacts only when safe and useful; and
- deferred work and risks.

Before requesting review, confirm:

- [ ] The change is authorised by one issue and stays in scope.
- [ ] Dependencies and architecture boundaries are respected.
- [ ] Household isolation, financial precision, privacy, logs, files, reports, AI and offline impact were considered where applicable.
- [ ] No secret, real household data or generated dependency is included.
- [ ] Requirements/design/ADR/changelog links are updated together.
- [ ] Relevant checks pass, and unrun checks are labelled honestly.
- [ ] The branch is current enough to review and contains no unrelated changes.
- [ ] Actionable review comments and failing required checks are resolved before merge.

Security-sensitive, authentication, authorisation, destructive migration, backup and production changes require independent review when a qualified reviewer is available.

## 9. AI-assisted contributions

AI tools may assist, but the contributor remains accountable for every line, license, claim, test result and security decision. Do not send repository secrets, private reports or real household data to an AI provider. Review generated text/code for fabricated behavior, unsafe dependencies, copied/licensing concerns and architecture violations. Disclose material AI assistance in the pull request when it helps reviewers evaluate provenance or risk.

## 10. Licensing

F2S is distributed under the existing [MIT License](LICENSE), copyright 2026 Sai Tein Thine. Unless explicitly agreed otherwise in writing by the repository owner, submitted contributions are offered under the same MIT terms and the contributor represents that they have the right to submit them.

No Contributor License Agreement or Developer Certificate of Origin sign-off is currently required. A future change to licensing or contribution certification requires explicit repository-owner review and must not be inferred from this guide. If you cannot contribute under these terms, do not submit the material.

## 11. Review and acceptance

Maintainers may request changes, split an oversized pull request, close work outside the active phase or decline a contribution that creates unresolved correctness, privacy, licensing, maintenance or security risk. Merge is not guaranteed by effort or prior discussion.

Be precise, kind and patient. Ask questions in the relevant public issue when they do not involve security, conduct or private data.
