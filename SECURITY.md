# F2S Security Policy

## Supported versions

F2S is currently in Phase 0 and has no production release or supported application version.

| Version or branch | Security support |
| --- | --- |
| `main` during Phase 0 | Repository, documentation, workflow and disclosed design-security issues are reviewed |
| Production/application releases | None exist yet |
| Unmerged branches and forks | Not supported by the F2S maintainer |

When releases begin, this table will identify supported versions and end-of-support dates. A document being present does not mean the described application or security control is implemented.

## Report vulnerabilities privately

Do not disclose a suspected vulnerability in a public issue, pull request, discussion, commit message, screenshot, log, social post or other public channel. Do not include real workspace data, credentials, tokens, private keys, financial records, exported files or unmasked AI payloads in any report.

### Preferred path: GitHub private vulnerability reporting

If the repository's Security page shows **Report a vulnerability**, use the [private vulnerability report form](https://github.com/saiteinthine1020-source/F2S/security/advisories/new). Only the repository maintainers and invited collaborators can access the draft advisory.

### Fallback when the private form is unavailable

If **Report a vulnerability** is not available:

1. Open a [metadata-only security contact request](https://github.com/saiteinthine1020-source/F2S/issues/new?title=Private%20security%20contact%20requested&body=Please%20do%20not%20include%20vulnerability%20details%2C%20secrets%2C%20or%20private%20data%20in%20this%20public%20issue.) titled `Private security contact requested`.
2. Include no vulnerability description, affected path, proof of concept, secret, private data or exploit detail.
3. The maintainer will create a draft GitHub Security Advisory, invite the reporter as a collaborator and close the metadata-only issue.
4. Continue all technical discussion and file sharing only inside that private advisory.

This fallback makes the request for a private channel public, but keeps every vulnerability detail private. If even the request would identify a person or sensitive event, use a private contact method published on the [repository owner's GitHub profile](https://github.com/saiteinthine1020-source) instead.

## What to include privately

Provide only what is necessary to reproduce and assess the issue:

- a concise vulnerability type and impact;
- affected release, commit, route, module, configuration or document;
- safe reproduction steps using synthetic data;
- required access, preconditions and whether exploitation was observed;
- expected versus observed behavior;
- suggested mitigation if known; and
- the reporter's disclosure/credit preference.

Use placeholders for hosts, accounts and identifiers. Redact secrets even if they are expired. Attach the smallest safe proof and state whether it may contain sensitive metadata.

## Response process

The initial targets are:

- acknowledge a complete private report within 3 business days;
- provide an initial triage result or request for information within 7 business days;
- agree on severity, scope and coordinated-disclosure expectations after validation; and
- provide a status update at least every 14 days while material remediation remains active.

These are response targets, not a guaranteed fix timeline or bug-bounty promise. Complex fixes may depend on design, testing, provider or release constraints. The maintainer will communicate delays rather than silently closing a valid report.

The maintainer will:

1. preserve the private report and assign a safe tracking identity;
2. reproduce with synthetic data where possible;
3. assess confidentiality, integrity, availability, workspace isolation and financial-correctness impact;
4. contain active exposure or compromised credentials without destroying required evidence;
5. prepare and independently review the fix and regression tests;
6. coordinate release, user action and disclosure timing; and
7. publish an advisory/credit when appropriate and agreed.

## Coordinated disclosure

Please allow a reasonable remediation period before public disclosure. Do not access, modify, retain or distribute data beyond what is necessary to demonstrate the issue. Stop testing and report immediately if real workspace data or a usable credential is encountered.

The maintainer will not ask a reporter to hide unresolved harm indefinitely. If disclosure timing cannot be agreed, both parties should communicate their intended timeline and minimise risk to users.

## Testing boundaries

Without explicit written authorisation, do not:

- test production or another person's account/data;
- use social engineering, phishing, denial of service or resource exhaustion;
- upload malware or destructive payloads;
- attempt physical/provider/account takeover;
- persist access, move laterally or exfiltrate data; or
- publish secrets or vulnerability details to prove a report.

Phase 0 has no application deployment. Current testing should normally be limited to repository content, dependency/workflow configuration and synthetic local artifacts.

## Not security reports

Ordinary bugs, feature requests, documentation corrections and non-sensitive dependency questions may use public GitHub issues. Conduct concerns follow [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md), not the vulnerability process unless they also expose a security or privacy risk.

## Safe handling by contributors

Never commit or attach `.env` files, production configuration, credentials, tokens, private keys, real workspace/financial/farming records, private reports, exported user files or usable provider payloads. If sensitive material is committed, do not merely delete it in a later commit: notify the maintainer privately so rotation, history cleanup and incident review can be considered.

This policy is guidance for this repository and is not a promise of legal safe harbour, compensation or professional legal advice.
