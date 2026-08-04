# F2S Data Dictionary

## 1. Purpose and conventions

This dictionary defines canonical F2S business terms, entities, fields, classifications, lifecycle states, numeric/unit semantics, and prohibited ambiguous language. It is shared by requirements, database/API design, code, tests, reports, translations, audit events, and AI preparation.

The [Database Design](08_Database_Design.md) defines relationships/constraints; [ADR-008](adr/ADR-008-safe-financial-numeric-storage.md) defines decimal behavior. New meanings must update this dictionary before implementation.

- **Canonical term:** approved English engineering meaning; display labels are translated separately.
- **Code:** stable uppercase machine value; display-text changes never alter stored meaning.
- **Source fact:** authorised input/evidence corrected only through approved workflow.
- **Derived value:** versioned backend output, never manually edited.
- **Protected:** requires authenticated purpose and household or controlled identity/operations boundary.
- Null means absent/not applicable/unknown per field contract; never silently zero, false, or empty.

## 2. Data classifications

| Code | Meaning / examples | Default handling |
| --- | --- | --- |
| `PUBLIC` | Published non-household docs/reference | Approved publication only |
| `INTERNAL` | Safe codes/operational metadata | Maintainer/application need-to-know |
| `CONFIDENTIAL` | Household, location, transaction, buyer/lender, report metadata | Household-authorised; protected backup; no broad logs |
| `RESTRICTED` | Login/contact, token digest, payment/bank, attachment, unmasked AI source | Strongest least privilege; purpose limitation; minimal retention/redaction |

Password, raw token, secret, API key, authorisation header, and production credential are never valid business-data fields.

## 3. Common fields

| Field | Meaning | Format / rule |
| --- | --- | --- |
| `id` | Opaque immutable entity ID | UUID v4; no embedded business meaning |
| `household_id` | Direct protected-row owner | Required/immutable on every household-protected table |
| `created_at` / `updated_at` | Server creation/last mutation instant | UTC `TIMESTAMPTZ`; updated >= created |
| `created_by_membership_id` | Household-context creating actor | Membership retained after deactivation |
| `updated_by_membership_id` | Last approved editor | Nullable only for controlled system action with attribution |
| `version` | Optimistic concurrency number | Positive BIGINT; increment on mutation |
| `status` | Entity-specific bounded lifecycle | Stable uppercase code, not free text |
| `occurred_on` | Business calendar date of event | `DATE`; distinct from creation time |
| `archived_at` / `archive_reason` | Archive instant/explanation | Archive retains history |
| `correlation_id` | Safe request/work trace ID | Contains no sensitive data |
| `idempotency_key` | Retry identity | Household+operation scoped; not credential |
| `currency_code` | Currency of money | Approved uppercase 3-letter code |
| `unit_code` | Unit of quantity | Stable code with compatible dimension |
| `notes` | Optional user context | Bounded Confidential text; not logs/AI by default |
| `reason_code` | Stable unavailable/failed/denied reason | Localisable message mapping; no sensitive detail |

## 4. Identity and household terms

| Term | Definition / owner | Key rule |
| --- | --- | --- |
| User account | Global authentication identity / Identity | May have multiple/no memberships; Restricted |
| Session | Revocable authenticated continuity / Identity | Token digest only; active household is request context |
| Household | Tenant, family-decision, authorisation, isolation boundary / Access | Protected through active membership |
| Membership | Account-household role/lifecycle / Access | Historical actor reference; direct household owner |
| Owner | Unique highest household role | Exactly one active under transaction policy |
| Administrator | Delegated manager | Cannot transfer ownership/exceed policy |
| Family Member | Granted contributor | No implied administration |
| Viewer | Granted read-only participant | Backend denies mutations |
| Invitation | Expiring household/role invitation | Token digest only; inviter authority checked |
| Active household | Explicit selected request context | Never inferred solely from record ID |
| Household settings | Currency/timezone/language/year/unit/profile preferences | Versioned/audited; no historical rewrite |
| Farm location | Household field/farm reference | Confidential, archivable, household-local name |

States: user account `INVITED`, `ACTIVE`, `DEACTIVATED`, `LOCKED`; membership `INVITED`, `ACTIVE`, `DEACTIVATED`; household `ACTIVE`, `SUSPENDED`, `ARCHIVED`.

## 5. Finance terms

| Term | Definition | Key rule |
| --- | --- | --- |
| Financial event | One canonical posted cash inflow/outflow | Positive magnitude+direction+currency; immutable after posting |
| Income / Expense | Ordinary inflow/outflow not already represented by another workflow | Counts once |
| Cash direction | `INFLOW` or `OUTFLOW` | Negative ordinary amount does not encode direction |
| Event kind | Stable source/reason classification | Manual income/expense, farm cost, debt payment, etc. |
| Finance category | Household finance classification | Archivable; historical references remain |
| Reversal | New opposite event neutralising original | Original retained; same household/currency |
| Replacement event | Corrected posting after reversal | Explicit link; new history |
| Canonical event link | Unique domain-source to financial-event relationship | Prevents duplicate cash counting |
| Recognised revenue | Sale value recognised under sale policy | Not cash received |
| Cash received | Sum of approved canonical receipt events | Each event once |
| Outstanding amount | Original receivable less payments/adjustments | Derived; not freely editable |

Financial-event states: `POSTED`, `REVERSED`. A local/client `DRAFT` is not a committed event.

## 6. Farming terms and states

| Term | Definition | Key rule |
| --- | --- | --- |
| Crop category | Reusable household crop classification | Creating/selecting never creates investment |
| Farming investment | Distinct crop/season/year/location/planting-cycle project | Separate identity for repeated cycles |
| Planned budget | User-entered expected spending | Source fact; not actual investment |
| Actual investment | Eligible direct/shared allocated costs | Derived by Calculation |
| Direct/shared cost | Cost allocated to one/multiple investments | One canonical outflow when paid; allocations conserve total |
| Cost allocation | Documented investment share of cost | Basis, ratio/amount, deterministic residual |
| Harvest | Production event for one investment | Quantity/unit/date/loss/quality context |
| Total/usable harvest | Eligible harvest total/after loss | Derived unless explicit source contract says otherwise |
| Crop sale | Recognised crop sale from one project | Revenue distinct from cash/payment |
| Buyer reference | Minimal protected buyer identifier/label | Confidential; no logs/AI by default |

| Investment state | Meaning |
| --- | --- |
| `PLANNED` | Project exists; work not started |
| `ACTIVE` | Farming/cost activity in progress |
| `HARVESTING` | Harvest recording in progress |
| `COMPLETED` | Ordinary cycle closed; controlled corrections |
| `CANCELLED` | Will not continue; reason/actor/time; history retained |
| `ARCHIVED` | Hidden from active views; authorised history/restoration |

## 7. Remittance, debt, and receivable terms

| Term | Definition / rule |
| --- | --- |
| Remittance | Transfer across source/destination money for household purpose; cash effect once |
| Source/destination amount | Money before/after conversion, each with currency |
| Exchange rate | Destination units per exactly one source unit; positive with date/provenance |
| Quoted-rate mode | Source amount+rate authoritative; destination derived/quantised |
| Settled-amount mode | Settled source+destination authoritative; effective rate derived if source non-zero |
| Remittance allocation | Purpose share reconciling exactly; never duplicate income |
| Debt | Household obligation; original principal source, balance derived |
| Debt repayment | One debt + one canonical event; reduces balance once |
| Receivable | Amount owed, standalone or sale-linked; outstanding derived |
| Receivable payment | One receivable + one canonical event; reduces balance/increases cash once |
| Overpayment | Payment beyond approved outstanding amount; explicit rejection/workflow |
| Write-off | Approved uncollectible recognition; not cash payment |

Debt states: `ACTIVE`, `PAID`, `DEFAULTED`, `CANCELLED`, `ARCHIVED`. Receivable states: `OPEN`, `PARTIALLY_PAID`, `PAID`, `OVERDUE`, `WRITTEN_OFF`, `CANCELLED`, `ARCHIVED`.

## 8. Numeric, currency, unit, and calculation terms

| Term | Canonical meaning/representation |
| --- | --- |
| Money | Exact `NUMERIC(24,4)` plus currency; API decimal string |
| Currency accounting scale | Final posting fractional digits (0-4; initially MMK/JPY 0, USD 2) |
| Ratio / percentage | `NUMERIC(18,10)` ratio; stored `0.075` displays 7.5% |
| Exchange rate | `NUMERIC(24,12)`, destination per source |
| Quantity | `NUMERIC(24,8)` plus unit |
| Unit price | `NUMERIC(24,8)` plus currency and quantity unit |
| Rounding | Round half to even at explicit boundary |
| Smallest accounting unit | `10^-currency_scale`, used for allocation residuals |
| Zero denominator | Unavailable with reason; never zero/NaN/infinity |
| Source fact / assumption / estimate | Evidence / explicit hypothetical input / deterministic output; never interchangeable |
| Verified result | Backend value with formula/source/unit/currency/period/rounding/quality/version context |

Unit dimensions include `AREA`, `MASS`, `VOLUME`, and `COUNT`. Conversion is only within compatible dimensions using versioned exact factors. Source value/unit remain historical; normalized comparison is derived.

| Calculation | Definition / unavailable condition |
| --- | --- |
| Profit/loss | Recognised revenue minus eligible actual investment |
| Margin | Profit/loss divided by recognised revenue; unavailable at zero revenue |
| ROI | Profit/loss divided by actual investment; unavailable at zero investment |
| Break-even price | Cost basis per eligible quantity; unavailable at zero quantity |
| Unit cost | Eligible cost per usable quantity; unavailable at zero quantity |
| Yield | Usable harvest per field area; unavailable at zero/missing area |
| Funding gap | Required pre-harvest funds minus approved available funds for scenario |

Calculation availability: `AVAILABLE`, `PENDING`, `INCOMPLETE`, `UNRELIABLE`, `UNAVAILABLE`. Data quality: `COMPLETE`, `MOSTLY_COMPLETE`, `INCOMPLETE`, `UNRELIABLE`. Non-complete states require reason codes.

## 9. Planning, output, AI, and evidence terms

| Term | Definition / key rule |
| --- | --- |
| Planning scenario | Household hypothetical workspace; never creates real project/event |
| Scenario version | Immutable inputs/assumptions/source refs at a point in time |
| Conservative/Expected/Optimistic | Explicit deterministic cases; none is a guarantee |
| Recommendation | Transparent advisory status/reasons; no action execution |
| Verified dataset | Authorised versioned read model with household/purpose/filter/period |
| Dashboard | View of verified dataset; no independent formulas/fake empty charts |
| Report request / artifact | Generation intent / validated expiring temporary file |
| Protected file | Household/purpose/type/size/access/expiry-controlled file |
| AI advice request | Authorised purpose-limited request from masked verified data |
| Masked dataset | Verified data after prohibited identifiers/details removed |
| AI explanation | Validated advisory text; never authoritative value/action |
| Fallback | Safe deterministic response on provider failure; source unchanged |
| Audit event | Append-only safe action/result evidence |
| Operational log | Redacted diagnostics; not audit/business truth |
| Idempotency record | Retry evidence; matching fingerprint, current auth rechecked |
| Conflict | Proposed mutation incompatible with newer state; no silent overwrite |
| Outbox event | Minimal durable post-commit intent; not financial truth |

States: report `QUEUED/RUNNING/SUCCEEDED/FAILED/CANCELLED/EXPIRED`; file `PENDING/AVAILABLE/QUARANTINED/EXPIRED/DELETED/FAILED`; AI `VALIDATING/MASKED/SENT/SUCCEEDED/FALLBACK/FAILED/CANCELLED`; outbox `PENDING/PROCESSING/SUCCEEDED/FAILED/DEAD_LETTER/CANCELLED`.

## 10. Historical and retention terms

| Term | Meaning |
| --- | --- |
| Archive | Hide from active views; retain history |
| Cancel | End workflow with reason; preserve facts |
| Reverse | Append opposite financial posting |
| Correct | Preserve original and record replacement/new state |
| Deactivate | Deny future use/access; preserve attribution |
| Expire | Make time-limited session/invitation/file/key/artifact unusable |
| Delete | Removal under approved retention/privacy procedure, not archive |
| Anonymise | Irreversibly remove/replace identity while preserving approved integrity |
| Retention owner | Design/role responsible for approved retention period |

Legal periods are not guessed. Issues #11, #13, #14, and #16 own the retention matrix.

## 11. Prohibited ambiguity

| Avoid | Use instead |
| --- | --- |
| Transaction | Financial event, database transaction, sale, payment, or remittance |
| Amount | Money amount, quantity, unit price, ratio, with currency/unit |
| Profit | Profit/loss with period/currency/formula/availability |
| Revenue | Recognised revenue or cash received |
| Balance | Debt balance, receivable outstanding, or cash balance with date/currency |
| Rate | Exchange/interest/ROI/loss rate with direction/period/basis |
| Delete project | Cancel or archive farming investment |
| User | User account, membership, or actor |
| Current household | Active household |
| AI result | AI explanation or fallback |
| Empty | No records, not applicable, incomplete, unavailable, or verified zero |
| Total | Named total with source/period/currency/unit/filter/formula |

## 12. Entity ownership and isolation register

| Entity | Owner | Isolation |
| --- | --- | --- |
| `user_accounts`, `auth_sessions` | Identity | Global protected identity boundary; not ordinary household queries |
| `households`, `household_memberships`, `household_invitations`, `household_settings`, `farm_locations` | Household Access | Direct household ownership or membership-gated household row visibility |
| `finance_categories`, `financial_events`, `financial_event_files` | Household Finance | Direct household; correction/category/file parents same household |
| `crop_categories`, `farming_investments` | Farming Investments | Direct household; crop/location relationships same household |
| `farm_costs`, `farm_cost_allocations`, `harvests`, `crop_sales` | Farm Operations | Direct household; cost/project/event parents same household |
| `remittances`, `remittance_allocations`, `debts`, `debt_payments`, `receivables`, `receivable_payments` | Funds | Direct household; all source/event/target relationships same household |
| `planning_scenarios`, `planning_scenario_versions`, `planning_assumptions` | Planning | Direct household; parent chain same household |
| `protected_files` | File Protection | Direct household; purpose/resource access rechecked |
| `report_requests`, `report_artifacts` | Reporting | Direct household; request/file/dataset same household |
| `ai_advice_requests` | AI Advice | Direct household; authorised dataset/purpose and masked outbound |
| `audit_events` | Audit | Direct household; separately permissioned queries |
| `idempotency_records`, `outbox_events` | Application Support | Direct household; operation/payload purpose-limited |

Adding a protected entity without updating this register and the Database Design is prohibited.

## 13. Governance and acceptance

Machine codes remain stable and are not reused for new meaning. Each implemented field must define purpose, type/scale, null meaning, source/derived status, classification, audience, retention owner, export/AI/log rules, and module owner. Translations map labels without changing semantics. Formula terms reference the one Calculation rule/version. Examples use synthetic data only.

Issue #8 is complete when this dictionary and Database Design agree on ownership, isolation, canonical events, states, numeric/unit meaning, historical preservation, sensitive-data limits, and terminology, with no models, migrations, API contracts, or seed data.
