# F2S Repository Governance

## 1. Purpose and authority

This document defines how F2S work is proposed, selected, reviewed, merged, and tracked. It applies to maintainers, contributors, and automated coding agents.

The authoritative order is:

1. accepted Architecture Decision Records;
2. approved or baseline project documentation;
3. the active GitHub Issue and its acceptance criteria; and
4. the pull request that implements that issue.

A pull request must not expand into a later phase merely because related work appears convenient. Material scope or architecture changes require an updated issue or a new decision record before implementation.

## 2. Work-item model

- **Milestones** represent delivery phases and contain their exit criteria.
- **Project items** show workflow state across the roadmap.
- **Issues** are the unit of authorised, reviewable work.
- **Branches** isolate the changes for one issue.
- **Pull requests** provide the review, validation, and merge record.

Only one issue should be actively implemented at a time unless the maintainer explicitly approves independent parallel work. Dependencies must be complete before dependent work starts.

## 3. Issue standard

Every issue must identify:

- Goal;
- Background;
- Scope;
- Acceptance Criteria;
- Out of Scope;
- Dependencies;
- Security and Privacy Impact;
- Database and API Impact;
- Required Validation or Tests; and
- Documentation Impact.

Unknown impact must be written as `To be determined`; it must not be silently omitted. Use `None` only after considering the impact.

An issue is **Ready** when its goal, boundaries, dependencies, acceptance criteria, and relevant impacts are clear enough to implement and verify. Unresolved architecture or security decisions keep the issue in Backlog.

## 4. Labels

Labels classify work; milestones remain the source of truth for delivery phase.

### Type labels

Apply at least one type label that describes the primary work:

| Label | Use |
| --- | --- |
| `type: documentation` | Product, engineering, or operational documentation |
| `type: architecture` | Architecture decisions, boundaries, or contracts |
| `type: backend` | Backend application or service work |
| `type: frontend` | Frontend application or user-interface work |
| `type: database` | Schema, migration, query, or data-integrity work |
| `type: security` | Threat modelling, controls, or security remediation |
| `type: testing` | Test strategy, fixtures, automation, or quality gates |
| `type: devops` | CI/CD, infrastructure, deployment, backup, or operations |

Use multiple type labels only when the issue genuinely crosses those boundaries.

### Priority labels

Apply exactly one priority label:

| Label | Meaning |
| --- | --- |
| `priority: critical` | Immediate security, data-loss, or release-blocking work |
| `priority: high` | Required for the active milestone or a direct dependency |
| `priority: medium` | Planned work without an immediate milestone blocker |
| `priority: low` | Useful improvement that may be deferred safely |

Priority does not override dependencies, security review, or milestone scope.

## 5. Project fields and workflow

The `F2S Development Roadmap` uses these fields:

- Title;
- Assignees;
- Linked pull requests;
- Sub-issues progress; and
- Status.

Status values have the following meaning:

| Status | Entry rule | Exit rule |
| --- | --- | --- |
| Backlog | Approved work that is not ready to start | Requirements and dependencies are complete |
| Ready | Work can begin | Implementation starts |
| In Progress | Someone is actively implementing the issue | A complete pull request is awaiting review |
| In Review | Implementation is complete and undergoing review or verification | Required review and checks pass |
| Done | Acceptance criteria, validation, and documentation are complete | Terminal state |

Closing an issue does not replace the Done verification. When automation does not update the project, the maintainer updates it manually.

## 6. Branch conventions

- Create branches from the current `main` branch.
- Keep one issue per branch and one focused pull request per issue.
- Automated coding-agent branches use `agent/<short-description>`.
- Human-created branches use `docs/<short-description>`, `feat/<short-description>`, `fix/<short-description>`, or `chore/<short-description>` as appropriate.
- Use lowercase words separated by hyphens; do not include secrets, personal data, or issue descriptions containing sensitive information.
- Delete merged branches after confirming their commits are reachable from `main`.

Direct feature work on `main` is prohibited. Repository bootstrap and exceptional recovery actions must be documented.

## 7. Commit and pull-request conventions

Commit and pull-request titles use a short conventional prefix such as `docs:`, `feat:`, `fix:`, `test:`, `security:`, `ci:`, or `chore:`.

Pull requests must:

- link the issue with `Closes #<number>` when merging should close it;
- explain what changed and why;
- state security/privacy and database/API impacts;
- list validation performed and its result;
- identify documentation changes;
- contain no unrelated files; and
- start as a draft unless the work is already ready for review.

Do not merge a draft pull request. Resolve review findings in the same branch and keep the pull-request description accurate when scope changes.

## 8. Review and merge rules

Reviewers verify:

- the linked issue authorises the change;
- acceptance criteria are satisfied;
- architecture and module boundaries are preserved;
- household isolation, secrets, personal data, exports, logs, and AI payloads are considered where relevant;
- database and API compatibility are explicit;
- tests or documentation-only validation are proportionate to risk; and
- the change contains no generated dependencies, credentials, or real household data.

The maintainer may merge only after required checks pass and all actionable review findings are resolved. Security-sensitive, destructive migration, authentication, authorisation, backup, and production changes require independent review when a qualified reviewer is available. A lack of reviewer availability does not justify bypassing documented validation.

Squash or merge commits are permitted when they preserve a clear issue-to-change history. Force-pushing shared review branches should be avoided.

## 9. Definition of Done

An issue is Done only when:

- every acceptance criterion is satisfied or explicitly moved to a follow-up issue;
- required tests or validation pass;
- security/privacy and database/API impacts are addressed;
- documentation and indexes are updated;
- the pull request is merged into `main`;
- the issue is closed and the project status is Done; and
- the merged branch is deleted when safe.

## 10. Branch-protection rollout

Branch protection is intentionally deferred until Issue #19 establishes stable, reproducible CI checks. Requiring checks that do not yet exist or are not reliable would block legitimate repository maintenance.

After Issue #19 is merged and its checks demonstrate stability, configure `main` to:

- require a pull request before merging;
- require the documented CI checks to pass;
- require conversation resolution;
- block force pushes and branch deletion;
- dismiss approvals when review-relevant changes are pushed, when practical; and
- limit bypasses to documented recovery by repository administrators.

Enable rules in stages, verify them with a test pull request, and record the final check names in this document. Do not claim branch protection is complete before that verification.

## 11. Security and repository hygiene

- Never commit `.env` files, credentials, tokens, production configuration, real household financial data, or exported reports containing private data.
- Use placeholders in `.env.example` and documentation.
- Give GitHub Actions the minimum permissions required; pin or deliberately review third-party actions.
- Treat logs, artifacts, comments, issue bodies, and screenshots as possible disclosure channels.
- Report suspected vulnerabilities privately according to `SECURITY.md` once that file is added by its planned issue; until then, contact the repository owner privately and do not open a public vulnerability issue.

## 12. Governance changes

Changes to this policy require a focused issue and pull request. If a governance change alters an accepted architecture decision, a new ADR must supersede the existing decision.
