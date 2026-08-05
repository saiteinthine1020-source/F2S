# F2S Repository Instructions

## Authority

Read this file before changing the repository. Product and engineering decisions are
authoritative in this order:

1. Accepted architecture decision records in `docs/adr/`.
2. The focused design document that owns the affected area.
3. Cross-cutting requirements and the documentation index.
4. Project-management plans and issue text.

When documents conflict, stop implementation and resolve the conflict in documentation
and an ADR before writing application code.

## Current delivery boundary

F2S is moving from Phase 0 documentation into Phase 1 identity and workspace foundations.
The canonical tenant boundary is a **Workspace**. Household, Farm, Microbusiness, Small
Business, Combined, and Custom are workspace types or module configurations, not separate
security boundaries.

The only Phase 1 workspace membership roles are:

- **Admin** — the sole workspace owner in the MVP and the only role that can manage the
  workspace and its members.
- **Contributor** — can create submissions that require approval but cannot receive
  restricted totals, reports, complete debt/profit data, role management, or settings.
- **Advisor** — read-only access to permitted totals and reports, with review, comment, and
  flag actions; cannot create, edit, delete, or approve records.

Ownership is an invariant attached to one active Admin membership. It is not an additional
general-purpose role. A workspace must never have zero or more than one owner.

## Engineering rules

- Preserve workspace isolation in the database, service layer, API, jobs, reports, audit,
  files, AI preparation, and tests.
- Enforce permissions in backend policy code. UI visibility is not authorization.
- Never return restricted totals to a Contributor, including in nested resources, counts,
  error details, exports, notifications, or cached payloads.
- Only approved financial records may affect official balances, dashboards, reports, or AI
  datasets. Contributor submissions begin Pending and may become Approved or Rejected.
- Use exact decimal semantics defined by ADR-008. Do not use binary floating point in an
  authoritative financial path.
- Keep visible UI text externalized for English, Shan, Myanmar, and Japanese localization.
- Keep application code out of documentation-only issues and pull requests.
- Do not add secrets, generated artifacts, local environments, or unpinned GitHub Actions.

## Change workflow

1. Inspect the working tree and relevant documents before editing.
2. Work on a branch tied to one issue.
3. Keep changes within the issue acceptance criteria.
4. Add or update tests with implementation changes.
5. Run repository policy, Markdown/link, static, test, and secret checks that apply.
6. Report every changed file and any check that could not be run locally.

## Phase 1 implementation gate

Do not implement the identity/workspace database or API until ADR-012 through ADR-016 and
`docs/12_Workspace_Identity_Design.md` are accepted and mutually consistent.
