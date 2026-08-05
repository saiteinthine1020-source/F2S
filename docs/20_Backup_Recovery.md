# F2S Backup and Recovery Design

## 1. Purpose and status

This document defines how future F2S production data is backed up, protected, retained, verified, restored and recovered. It establishes recovery objectives, backup types and schedules, independent copies, encryption and key custody, monitoring, expiry, restore procedures, reconciliation, drills and release gates.

It follows the [Non-Functional Requirements](04_Non_Functional_Requirements.md), [Database Design](08_Database_Design.md), [Security Design](15_Security_Design.md), [Test Strategy](17_Test_Strategy.md), [Deployment Design](18_Deployment_Design.md), [Operations Runbook](19_Operations_Runbook.md), and [ADR-002](adr/ADR-002-use-postgresql.md).

This document creates no backup job, storage account, key, archive, database copy, scheduled task, cloud resource or production command. Exact tools/providers and validated commands are implementation decisions reviewed before production.

## 2. Recovery principles

1. Live storage, a replica, server snapshot and provider availability are not backups by themselves.
2. A backup is incomplete until encrypted, transferred off-host, catalogued and integrity checked.
3. A backup is not proven recoverable until an isolated restore completes and business reconciliation passes.
4. Database records, protected files, schema/version, required configuration references and audit relationships form one recovery set.
5. Backup credentials cannot mutate production data; runtime credentials cannot read/delete backup history.
6. Backup encryption keys are separated from backup bytes and are recoverable if the production host/account is lost.
7. At least one backup copy is outside the primary server and primary account/provider failure boundary.
8. Restores never overwrite the only surviving evidence or the failed production source before preservation decisions.
9. Restored environments deny public access and disable email, Gemini and other external side effects.
10. Recovery success requires exact financial reconciliation and workspace-isolation evidence, not only service startup.
11. Retention expiry is deliberate, auditable and tested; indefinite accumulation is a privacy and cost failure.
12. Objectives remain provisional until timed drills prove them on production-like volume and replacement infrastructure.

## 3. Official technical baseline

Implementation rechecks the documentation for the selected supported PostgreSQL version. Initial official references are:

- [PostgreSQL backup and restore](https://www.postgresql.org/docs/current/backup.html)
- [Continuous archiving and point-in-time recovery](https://www.postgresql.org/docs/current/continuous-archiving.html)
- [`pg_basebackup`](https://www.postgresql.org/docs/current/app-pgbasebackup.html)
- [`pg_verifybackup`](https://www.postgresql.org/docs/current/app-pgverifybackup.html)
- [SQL dump](https://www.postgresql.org/docs/current/backup-dump.html)
- [Hetzner server backup and snapshot limitations](https://docs.hetzner.com/cloud/servers/backups-snapshots/faq/)

PostgreSQL documents that physical base backups plus a continuous WAL sequence enable point-in-time recovery. Backup manifests can be checked with `pg_verifybackup`, but manifest verification does not replace starting the restored cluster and reconciling F2S data. Hetzner documents that running-server snapshots may be inconsistent and do not include attached Volumes; they remain supplemental only.

## 4. Scope and data inventory

| Asset | Included | Recovery relationship |
| --- | --- | --- |
| PostgreSQL cluster | Required | Source facts, identities, memberships, audit, jobs and metadata |
| PostgreSQL roles/grants | Required through protected role-definition procedure | Restored separately; no usable secret embedded in dump |
| Schema/migration version | Required | Must match restored data before compatible application starts |
| Protected uploaded files | Required while within approved record retention | Reconciled against database file metadata/checksums |
| Required file-storage metadata | Required | Proves object identity, purpose, state and checksum |
| Generated report/export bytes | Normally excluded | Short-lived and regenerable; metadata/expiry follows source policy |
| Application images/source/config schema | Rebuildable, not data backup | Recovered from approved Git/registry artifacts by commit/digest |
| Secret values | Not stored with backup set | Recovered from separate secret/key custody process or rotated |
| TLS certificate/private key | Reissue preferred; protected recovery only if required | Never embedded in database/file backup |
| Operational logs | Separate retention/export | Not authoritative business data and not required to reconstruct audit |
| Audit events | Included in PostgreSQL | Reconciled as append-only evidence |
| Backup catalog/manifests | Required safe metadata | Identifies chain, cutoff, integrity, retention and restore eligibility |

An asset cannot be introduced without a backup/restore/retention classification. “Not backed up” must be intentional and demonstrate regeneration or safe loss.

## 5. Initial recovery objectives

| Objective | Initial target | Start/end measurement | Status |
| --- | --- | --- | --- |
| Full-system RPO | No more than 24 hours of committed database/file data loss | Incident/recovery cutoff minus newest mutually consistent recovered database and protected-file point | Provisional release gate |
| PostgreSQL PITR capability | Continuous WAL with archive-lag warning at 5 minutes and critical at 15 minutes | Latest safely archived WAL versus primary WAL position/time | Defense in depth; not a promised full-system RPO |
| Full-system RTO | No more than 4 hours | Declared recovery start through verified application readiness, reconciliation and approved return to service | Provisional release gate |
| Restore drill frequency | Before first production, quarterly, and after material format/topology/key/version change | Last passing complete drill | Required |

The RPO is not “time since the last job started.” It is measured from the latest recovered committed event and protected-file cutoff. The RTO excludes pre-declaration indecision but includes infrastructure replacement, key access, transfer, restore, WAL replay, file recovery, application startup, reconciliation and approval.

A missed RPO/RTO drill is a failed objective requiring remediation or an explicit narrower service claim; results are not adjusted after the fact.

## 6. Backup strategy

### 6.1 Primary physical recovery chain

The initial PostgreSQL strategy uses:

- one application-consistent physical base backup at least every 24 hours;
- continuous WAL archiving to protected off-host storage;
- a manifest with cryptographic integrity protection separate from the archive where practical;
- all WAL/history files required to restore each retained recovery point; and
- one self-contained recovery set designation after completeness validation.

The selected tool may wrap native PostgreSQL facilities but must expose exact PostgreSQL version, start/end WAL position, timeline, checksum/manifest, exit state and restore instructions. Incremental backups are not initial baseline complexity; they require a chain-dependency and expiry design plus successful combine/restore evidence before adoption.

### 6.2 Logical portability copy

At least weekly, F2S creates an encrypted logical database dump plus required global role/grant definitions without secret values. This is a secondary portability and selective-inspection aid, not the primary PITR chain and not a substitute for physical recovery testing. Logical restore time and cross-version compatibility are measured before it is accepted as an emergency alternative.

### 6.3 Protected-file recovery set

Protected files are backed up at least every 24 hours using content checksums and a database-derived manifest from a consistent cutoff. The procedure records created/changed/deleted object state without copying temporary reports past their approved retention.

A recovery point is full-system eligible only when its database cutoff, file manifest and available file objects reconcile. Orphan bytes are not silently published; missing required bytes fail recovery verification or remain quarantined with explicit impact.

### 6.4 Provider snapshots

Hetzner backups/snapshots may accelerate host reconstruction but are supplemental. They do not satisfy the F2S recovery objective, copy-count rule, database consistency, attached-Volume coverage, encryption/key separation or restore verification by themselves.

## 7. Copy and failure-domain policy

F2S keeps at least three effective copies of retained production information:

1. live production data;
2. a primary encrypted off-host backup copy inaccessible to the runtime role; and
3. a secondary encrypted recovery copy in a separate account/provider or otherwise approved independent administrative and deletion failure boundary.

At least one backup copy uses deletion protection, immutability or credentials incapable of ordinary overwrite/delete for its protected window. The job that creates/uploads new backups does not automatically receive authority to delete protected history. Expiry deletion is a separate authorised operation.

The implementation records server, datacentre/network zone, account, storage service, credentials, billing dependency, key dependency and operator dependency for every copy. Two buckets under one broadly privileged account are not automatically two independent failure domains.

## 8. Encryption, keys and credentials

Backup content is encrypted before or at protected storage with an authenticated encryption design. Transport also uses TLS. Each recovery set has a unique data-encryption key or equivalent isolation; keys are wrapped by a separately governed recovery key.

| Capability | Required separation |
| --- | --- |
| Produce/upload backup | Minimum database/file read and create-only storage access where supported |
| Verify catalog/integrity | Read safe metadata and backup bytes; no production mutation |
| Expire/delete backup | Separate scheduled authority and approval; cannot access production data |
| Decrypt/restore | Restricted recovery authority, unavailable to ordinary runtime/job |
| Administer storage/account | Break-glass provider authority with MFA and audit |

The production host must not be the sole location of decryption material. Recovery key custody has a named primary and alternate custodian, tested access, revocation/rotation procedure and protected emergency record. Backups never contain their own plaintext decryption key, `.env`, database password, provider token or TLS private key.

Key rotation retains the old key only as long as required to decrypt unexpired backups, or rewraps them through a tested procedure. Suspected key compromise suspends unsafe deletion, preserves evidence, rotates upload/storage credentials and evaluates re-encryption or accelerated expiry without destroying the only recovery copy.

## 9. Initial retention matrix

Values are provisional until cost, legal/business need, dataset growth and restore evidence are approved before production.

| Artifact | Retention | Expiry dependency |
| --- | --- | --- |
| Daily full database + protected-file recovery set | 7 daily points | Keep required manifest/WAL and both backup copies |
| Weekly promoted self-contained recovery set | 5 weekly points | Promotion must be verified before daily source expires |
| Monthly promoted self-contained recovery set | 12 monthly points | Full independent recoverability; PITR beyond included cutoff not implied |
| Continuous WAL archive | 35 days minimum and never less than required by retained PITR base backups | Delete only after chain graph proves no retained point depends on it |
| Weekly logical dump/roles copy | 5 weekly and 12 monthly points | Restore compatibility evidence and encryption retained |
| Backup catalog/manifests/integrity results | 13 months after represented set expires | Contains safe metadata only |
| Restore drill record | 24 months | Contains no restored workspace content or credentials |
| Backup/expiry operational logs | 90 days | Safe categories only; audit evidence follows audit retention |

Retention uses generation/cutoff instants in UTC and prevents premature expiry caused by failed later backups. A new failed/corrupt backup never ages out the last known good recovery set.

Legal/business requirements may lengthen or shorten these values through a reviewed change. Retention changes are prospective unless a protected, authorised expiry plan states otherwise.

## 10. Backup execution contract

Each scheduled run:

1. identifies environment, source cluster/system identifier, approved tool/version and backup ID;
2. checks time sync, source health, capacity, prior chain state and storage/key reachability;
3. obtains only the backup principal/file access required;
4. creates the database/file artifact at a recorded consistent cutoff;
5. encrypts content and transfers it off-host without exposing values in arguments/logs;
6. creates checksum/manifest, size, object count, start/end time, WAL/timeline and version metadata;
7. verifies remote readability and integrity using an independent read path where practical;
8. confirms secondary-copy replication/protection;
9. marks the set `ELIGIBLE` only when all required components succeed;
10. updates safe last-success/age metrics and audit evidence; and
11. expires old sets only through dependency-aware policy after a known-good successor exists.

States are `STARTED`, `UPLOADED`, `VERIFIED`, `ELIGIBLE`, `FAILED`, `QUARANTINED` and `EXPIRED`. A partial set is never `ELIGIBLE`.

Backup logs contain backup ID, safe source/version, times, bytes/counts, checksum algorithm/result, copy state, result code and correlation. They exclude archive names derived from workspace data, record values, credentials, key material and raw command output that may contain secrets.

## 11. Backup monitoring and alerts

| Signal | Warning | Critical/action |
| --- | --- | --- |
| Full-system eligible recovery-point age | 18 hours | 24 hours: RPO at risk/breached; page recovery owner |
| WAL archive lag/failure | 5 minutes | 15 minutes or repeated failure; preserve disk headroom and investigate |
| Physical base-backup duration | Exceeds measured baseline by 50% | Cannot complete before 24-hour eligibility deadline |
| Primary/secondary copy | Delayed beyond expected replication window | Missing independent copy at eligibility deadline |
| Integrity/manifest check | Any anomaly | Quarantine set; keep prior good set; security/recovery review |
| Backup storage capacity | 70% | 85%; stop unsafe expiry shortcuts and expand/remediate |
| Restore drill age | 75 days | 90 days; production readiness/compliance failure |
| Key-custody test age | 75 days | 90 days or failed access test |

Thresholds are initial and must be calibrated. Alert delivery is tested without injecting production content. Silence/maintenance windows require owner, reason, expiry and a separate check that cannot conceal an RPO breach.

## 12. Restore authority and safety

A full restore requires an incident/recovery lead, database/recovery operator and recorded approval. One person may fill multiple roles for a small team, but the record states who decided, executed and verified. Destructive overwrite of existing production needs explicit confirmation after evidence preservation.

The restore target is new/replacement isolated infrastructure by default. It has:

- no public route except the restricted operator path;
- email, Gemini, webhooks and other side effects disabled;
- production-equivalent PostgreSQL major/version or an approved compatibility plan;
- separate temporary credentials and no reuse of compromised secrets;
- sufficient storage plus replay headroom; and
- logging that records safe recovery evidence only.

## 13. Full restore runbook

### 13.1 Declare and select

1. Declare recovery start, incident/correlation ID, scope, suspected cause and write-freeze decision.
2. Preserve the failed source, recent WAL and provider evidence when safe; do not clean/rebuild first.
3. Choose the newest `ELIGIBLE` recovery set before the corruption/incident cutoff.
4. Confirm database, file, WAL/timeline, versions, encryption key and both-copy availability.
5. Record expected RPO and target RTO; escalate immediately if either cannot be met.

### 13.2 Provision and verify artifacts

1. Provision replacement infrastructure from the approved Deployment Design.
2. Restrict network access and disable all external side effects.
3. Retrieve backup through the recovery identity without exposing keys in commands/logs.
4. Verify catalog signature/authenticity, encrypted-object checksums and physical backup manifest before restore.
5. Keep source artifacts read-only; work from controlled copies.

### 13.3 Restore database and files

1. Restore the physical base backup with correct ownership/permissions.
2. Configure the exact approved WAL restore path and target timeline/time/restore point.
3. Replay only through the chosen cutoff; record achieved timestamp/LSN/timeline.
4. Start PostgreSQL isolated and confirm crash/PITR completion without accepting application traffic.
5. Restore protected files to a quarantine/recovery namespace, then reconcile manifest/checksums.
6. Restore roles/grants through the approved least-privilege procedure without restoring stale secrets blindly.
7. Deploy the compatible immutable application image/configuration for the restored schema.

### 13.4 Verify business integrity

Required checks must have zero unexplained difference:

- PostgreSQL system identifier/version, expected schema/Alembic version and migration history;
- database connectivity through runtime role and denial through prohibited privileges;
- constraints, indexes and expected extensions;
- critical table/entity row counts by safe aggregate;
- no orphan/missing protected-file metadata or required bytes;
- complete two-workspace isolation suite, including jobs/files/reports/audit/AI preparation;
- canonical financial-event reconciliation and representative income/expense/cash totals;
- farming cost allocations, harvest/sales, debt and receivable balances;
- audit references/correlation and required historical states;
- session invalidation/secret rotation decision after incident;
- application readiness, authentication and critical synthetic smoke flow; and
- monitoring, backup scheduling and alert delivery on the replacement environment.

Sampled checks use authorised operators and do not copy workspace content into the recovery record. Any unexplained difference blocks return to service.

### 13.5 Cut over and close

1. Obtain recovery-lead approval from recorded verification evidence.
2. Rotate/revoke compromised or source-host secrets; do not reuse temporary restore credentials.
3. Move canonical traffic/storage references through the Deployment runbook.
4. Re-enable writes first, then optional external integrations after separate verification.
5. Monitor an explicit observation window and preserve the old source read-only until disposal approval.
6. Record actual RPO/RTO, lost/unavailable window, selected backup, verification result and follow-up issues.

## 14. Point-in-time and logical recovery

PITR is used for confirmed logical corruption or destructive action when the cutoff can be identified. Recovery creates a new PostgreSQL timeline. The operator preserves history files/WAL, never overwrites the original timeline and tests candidate cutoffs in isolation. If the exact corrupting event is uncertain, several isolated attempts may be required and all remain non-public.

Logical restore is considered when physical recovery is unavailable, selective inspection is authorised, or a version/architecture transition requires it. It restores roles/schema/data in a controlled order, verifies ownership/extensions/constraints/sequences and runs the same full business reconciliation. It is not assumed to meet the 4-hour RTO until measured.

## 15. Restore drills

A complete drill uses replacement/isolated infrastructure and a protected production backup when authorised, or an equivalent production-scale encrypted synthetic set. Provider side effects remain disabled. The drill measures every RTO segment and newest recovered point.

The signed safe drill record includes:

- date, operators/reviewer, environment and change trigger;
- backup ID/copy selected, cutoff, age, versions and size/count classes;
- key-recovery result without key material;
- provision, transfer, restore, replay, verification and total durations;
- achieved RPO and RTO;
- each reconciliation item and result;
- failures/manual steps, residual risk, owner and due date; and
- teardown/destruction evidence for the restore environment.

The first complete restore, every quarterly restore and any post-change restore is `PASS` only if all required checks pass. `BLOCKED`, `PARTIAL` and `NOT RUN` are never reported as success.

## 16. Retention, deletion and restored stale state

Expiry jobs use the dependency graph so a base backup, WAL segment, manifest, file snapshot or key needed by a retained recovery set is not deleted. The operation is idempotent, bounded, separately authorised and audited with backup IDs only.

Backups are append-only recovery history, not edited record by record. When live-data deletion is required, normal backup expiry eventually removes older copies. A restore must replay an approved post-backup deletion/suppression ledger or reapply required deletion before returning service, so expired/revoked data is not silently resurrected. Legal/privacy review defines exceptions and notification obligations.

At retention end, every copy, staging artifact and obsolete wrapped key is deleted or crypto-erased as designed. Deletion protection is temporarily changed only through approval and restored afterward. Safe deletion evidence remains for 365 days.

## 17. Threat and failure review

| Scenario | Required defense |
| --- | --- |
| Production host loss | Independent off-host copies, external key custody and replacement-server runbook |
| Provider/account deletion | Secondary administrative failure boundary and deletion-protected copy |
| Ransomware/credential compromise | Immutable/create-only copy, separate delete/decrypt authority and secret rotation |
| Silent corruption | Manifest/checksums, prior retained sets, real restore and business reconciliation |
| Failed/incomplete backup | Never eligible; prior known-good set cannot expire |
| Missing WAL/link in chain | Dependency graph, archive monitoring and pre-expiry recovery validation |
| Attached Volume absent from server snapshot | Explicit protected-file/database backup independent of snapshot |
| Lost encryption key | Alternate custodian and quarterly key-access test |
| Leaked encryption key | Independent storage controls, key rotation/rewrap and incident response |
| Malicious/accidental restore | Restricted authority, new target, evidence preservation and approval before cutover |
| Restored stale sessions/deletions | Session revocation decision and deletion/suppression replay before service |
| Backup logs leak records/secrets | Allowlisted metadata, canary tests and restricted retention |

## 18. Tabletop and validation scenarios

| Scenario | Exercise inject | Expected decisions/evidence | Pass condition |
| --- | --- | --- | --- |
| Total server/Volume loss | Host and attached storage unavailable | Declare recovery, use independent copy/key, provision replacement, full restore | RPO <=24h, RTO <=4h, all reconciliation passes |
| Accidental destructive change | Known approximate corruption time | Freeze writes, preserve timeline, choose PITR cutoff, compare candidates | Correct pre-event state with no unexplained difference |
| Latest backup corrupt | Manifest/checksum failure | Quarantine newest, retain/restore prior set, alert and investigate | Prior set restores within objective or risk is explicitly escalated |
| Primary backup account compromised | Attacker can delete/modify primary copy | Revoke credential, protect evidence, recover from independent copy | Secondary copy/key works and production secret rotation is complete |
| Key custodian unavailable | Primary recovery-key path unavailable | Invoke alternate custody procedure | Authorised recovery proceeds without exposing key material |
| Restore starts providers | Synthetic test detects email/AI attempt | Network/policy blocks side effect and drill fails pending correction | Zero external side effects |

Tabletop review does not replace the executed quarterly restore. Findings become owned issues with deadlines and are retested.

## 19. Release gates and deferred decisions

Production is blocked until:

- provider/tool/version and both backup-copy failure domains are approved;
- database/file schedules meet the 24-hour full-system RPO with headroom;
- encryption, key custody and alternate access are tested;
- retention/expiry dependency logic and capacity/cost are reviewed;
- backup/integrity/copy/age alerts reach the responsible operator;
- a complete replacement-infrastructure restore finishes within 4 hours;
- every database/file/financial/isolation verification passes; and
- the Operations Runbook has actionable owners, contacts and incident procedures.

Deferred: exact backup software and version; off-host providers/accounts/regions; immutability mechanism; encryption/KMS/key-custody implementation; compression/deduplication; schedule times; transfer bandwidth; growth/cost budget; legal retention; PITR service claim; automatic recovery; cross-region architecture; and validated production commands.

Issue #16 backup/recovery acceptance is satisfied when restore testing is required before backup success, RPO/RTO/copy/schedule/retention/key assumptions are explicit, database and files form a reconciled recovery set, logs exclude secrets/content, full and PITR restore sequences are actionable, quarterly and tabletop evidence is defined, and no live job or production change is added.
