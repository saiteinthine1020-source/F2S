# ADR-019: Include Reversed Originals in the Official Finance Ledger

- **Status:** Accepted
- **Date:** 2026-08-29
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 2 - Household Finance
- **Supersedes:** The official-dataset predicate in
  [ADR-018](ADR-018-approval-gated-canonical-financial-events.md)

## Context

ADR-018 separates approval state from posting state. An Admin reversal changes the original
from `APPROVED/EFFECTIVE` to `APPROVED/REVERSED` and creates an equal,
opposite-direction `APPROVED/EFFECTIVE` reversal. It also requires the signed original and
reversal to reconcile exactly to zero.

ADR-018 nevertheless described the official dataset as containing only
`APPROVED/EFFECTIVE` rows. Applying that predicate after the state transition removes the
original but retains its opposite reversal. Instead of producing zero, the selector reports
the reversal as a new cash effect. That contradicts append-only conservation and would make
monthly summaries, balances, reports, and later consumers disagree.

The posting lifecycle state and inclusion in the append-only finance ledger therefore need
distinct, explicit meanings.

## Decision

The Calculation/Data Quality owner exposes one reusable official-ledger selector equivalent
to:

`workspace matches AND approval = APPROVED AND posting IN (EFFECTIVE, REVERSED)`

Authorised period, currency, category, kind, direction, activity, payment-method, and later
domain filters are applied in addition to that predicate. Routes, dashboards, reports,
exports, forecasts, AI preparation, and frontend code must not redefine it.

`EFFECTIVE` identifies an Approved posting that has not itself been neutralised. `REVERSED`
identifies an Approved original that remains a signed ledger component and has exactly one
linked opposite `APPROVED/EFFECTIVE` reversal. The state provides lifecycle evidence; it
does not delete the original's signed contribution.

Each selected row contributes exactly once:

- `INFLOW` contributes its positive magnitude;
- `OUTFLOW` contributes its negative magnitude; and
- no consumer negates, subtracts, or joins a `REVERSED` original a second time.

The original and its reversal have the same workspace, currency, and magnitude and opposite
directions. Selecting both therefore reconciles the pair to zero at the currency accounting
scale. A correction's optional replacement is a separate `APPROVED/EFFECTIVE` row and
contributes once.

`PENDING`, `REJECTED`, and `NOT_EFFECTIVE` rows remain outside every official dataset.
Archive changes discoverability only and never changes official-ledger eligibility.

### Period semantics

Each ledger row belongs to the period containing its own `occurred_on` business date. A
later-period reversal does not rewrite the original period. It creates an equal opposite
effect in the reversal period, and the cumulative balance reconciles to zero as of that
later date.

For example, an original JPY 10,000 inflow dated July that is reversed in August produces:

| Period | Selected ledger component | Net effect |
| --- | --- | ---: |
| July | Original `APPROVED/REVERSED` inflow | `10000` |
| August | Reversal `APPROVED/EFFECTIVE` outflow | `-10000` |
| Through August | Both components | `0` |

If the same correction creates a JPY 12,000 August replacement, the through-August result
is JPY 12,000 because the original and reversal net to zero and the replacement contributes
once. Same-period original/reversal pairs net to zero within that period.

Retroactively restating a prior closed period would be a different reporting policy and
requires a later accepted decision with explicit versioning and audit behavior.

## Consequences

### Positive

- Reversal and correction conservation are mathematically consistent with their persisted
  lifecycle states.
- Monthly summaries and later official consumers can share one deterministic selector.
- Historical periods retain the business dates actually assigned to the original and
  reversal.
- Append-only evidence remains available without double counting.

### Negative

- The name `REVERSED` cannot be interpreted as "exclude this row" by query authors.
- Current-position queries that need only unneutralised postings require a separately named
  selector and must not be substituted for the official ledger.
- Cross-period reversals can make a later month's net negative even though the cumulative
  balance is correct; the UI and reports must explain this rather than rewrite history.

## Alternatives considered

### Exclude the original and include the reversal

Rejected because it changes a neutralising reversal into a new opposite cash effect.

### Exclude both the original and reversal

Rejected because it requires relationship-aware omission, erases the dated ledger effects,
and conflicts with the append-only canonical-event model.

### Keep the original in `EFFECTIVE`

Rejected because it discards the persisted lifecycle distinction already established by
ADR-018 and the implemented one-effective-reversal invariant.

### Move the reversal into the original period automatically

Rejected because it overwrites the Admin-supplied business date and silently restates prior
periods.

## Fitness criteria

This decision remains fit when tests prove:

1. only same-workspace `APPROVED/EFFECTIVE` and `APPROVED/REVERSED` rows enter the official
   ledger;
2. Pending, Rejected, and NotEffective rows contribute nothing;
3. an original and exact opposite reversal reconcile to zero in one currency;
4. a replacement contributes exactly once after the original/reversal pair nets to zero;
5. same-period and cross-period reversal buckets follow each row's `occurred_on` date;
6. archive does not change ledger results;
7. all official consumers use the shared selector and produce the same filtered result; and
8. workspace, role, currency, and authorised filters cannot leak or combine restricted data.

Changing ledger inclusion, signed contribution, or period-restatement semantics requires a
superseding ADR.
