# ADR-008: Use Decimal-Safe Financial Numeric Storage and Calculation

- **Status:** Accepted
- **Date:** 2026-08-04
- **Decision owners:** F2S maintainers
- **Applies from:** Phase 1 for shared numeric primitives; Phase 2 for financial records

## Context

F2S records and derives money, exchange rates, percentages, quantities, allocations, harvest loss, unit price, debt/receivable balances, profit/loss, margin, ROI, break-even values, and forecasts. A small numeric inconsistency can change a family decision, prevent reconciliation, or make dashboards and exports disagree.

Binary floating-point values cannot represent many decimal fractions exactly. Allowing `float`, PostgreSQL `REAL`, JavaScript `number`, or uncontrolled library coercion into an authoritative path would create artifacts and inconsistent rounding across the backend, frontend, database, reports, and AI preparation.

The product also uses currencies with different minor-unit conventions, including MMK and JPY, and may record conversions and prices requiring greater precision than a final cash amount. One generic scale is therefore insufficient for every numeric concept.

## Decision

F2S will use exact decimal semantics from input boundary through persistence, calculation, dataset generation, reports, and AI preparation.

- PostgreSQL uses `NUMERIC(precision, scale)` for verified financial, rate, percentage, and quantity values.
- Python uses `decimal.Decimal`, created from validated decimal strings or integers, never from a binary float.
- API contracts represent authoritative decimals as JSON strings with a documented scale/range, never JSON floating-point numbers.
- TypeScript treats authoritative decimal fields as validated strings or an approved exact-decimal type. JavaScript arithmetic is not used for financial formulas.
- The Calculation and Data Quality module defined by the [System Architecture](../07_System_Architecture.md) is the only owner of authoritative formulas, rounding, unit conversion, zero-denominator, and verified-result rules.
- PDF, Excel, CSV, dashboards, forecasts, and AI preparation consume verified backend values; they do not recalculate them independently.

`FLOAT`, `REAL`, `DOUBLE PRECISION`, Python `float`, JavaScript `number`, and spreadsheet binary numeric formulas are prohibited as sources of authoritative money, rates, percentages, quantities, or verified results. A renderer may convert a final display-only coordinate to a graphics-library float after the numeric value and label are fixed, but that value cannot return to a business calculation.

## Canonical numeric categories

The detailed schema may impose a smaller range or stricter scale. It may not weaken these semantics without a superseding ADR.

| Category | Canonical meaning | PostgreSQL baseline | Input/output convention |
| --- | --- | --- | --- |
| Money amount | Signed monetary magnitude paired with one currency | `NUMERIC(24,4)` | Decimal string; maximum 20 integer digits and 4 stored fractional digits |
| Exchange rate | Destination-currency units per exactly 1 source-currency unit | `NUMERIC(24,12)` | Strictly positive decimal string; direction and currency pair required |
| Ratio / percentage | Dimensionless ratio, where `0.15` means 15 percent | `NUMERIC(18,10)` | Decimal ratio string; UI may accept/display percent only through explicit conversion |
| Physical quantity | Amount paired with a compatible unit | `NUMERIC(24,8)` | Decimal string plus unit; domain determines whether zero/negative is permitted |
| Unit price | Money per declared compatible unit | `NUMERIC(24,8)` plus currency/unit context | Strictly non-negative where used for ordinary sale input |
| Derived calculation intermediate | Internal exact value before boundary quantisation | Python `Decimal` context with at least 50 significant digits | Never exposed as an unlabeled authoritative result |

These types do not imply that every field permits negative values. PostgreSQL can store signed values so profit/loss, corrections, and approved reversals are expressible; domain rules still reject negative ordinary transaction amounts and invalid states.

## Money and currency representation

A money value is the pair `(amount, currency)`.

1. Currency is an uppercase three-letter code from the approved currency registry, initially aligned with ISO 4217 codes needed by the household.
2. Amount without currency is invalid at module, persistence, dataset, report, and API boundaries.
3. Addition, subtraction, comparison, allocation, and aggregation require the same currency unless an explicit conversion produces a new money value.
4. Multi-currency lists and reports show separate totals by currency unless an explicit dated exchange-rate policy and conversion basis is selected.
5. Household base-currency changes do not rewrite historical currency or amounts silently.
6. Every currency has an approved accounting scale from 0 through 4. The registry records its standard minor-unit scale and any documented F2S accounting override.
7. Final ledger/cash amounts are quantised to the currency accounting scale. The database's four fractional digits preserve a consistent storage envelope; unused digits are zero.
8. Ordinary direct money input with more fractional digits than the currency accounting scale is rejected rather than silently rounded. A specifically documented calculated/conversion flow may quantise using the rounding rules below.

Examples of initial registry behavior:

| Currency | Standard accounting scale | Valid ordinary inputs | Invalid ordinary input example |
| --- | --- | --- | --- |
| MMK | 0 | `125000` | `125000.50` |
| JPY | 0 | `4500` | `4500.25` |
| USD | 2 | `10`, `10.5`, `10.50` | `10.235` |

The data dictionary and API design must identify the registry source and whether an exceptional cash-rounding rule applies. No exception is assumed by this ADR.

## Rounding policy

### Default mode

Authoritative decimal calculation uses **round half to even** (`ROUND_HALF_EVEN`). This reduces systematic upward bias over repeated calculations and is available consistently in Python Decimal and PostgreSQL numeric operations when implemented explicitly.

At two decimal places:

- `2.345` becomes `2.34` because the retained hundredths digit is even.
- `2.355` becomes `2.36` because the retained hundredths digit is odd.
- `-2.345` becomes `-2.34` under the same magnitude rule.

### Rounding boundaries

1. Parse and validate exact decimal input without first converting through float.
2. Maintain at least 50 significant decimal digits for calculation intermediates.
3. Do not round each intermediate step unless the formula or business event explicitly defines that step as a posting/allocation boundary.
4. Quantise a final money posting to its currency accounting scale.
5. Quantise a stored/displayed rate, ratio, unit price, or quantity only at its documented contract scale.
6. A displayed value may use fewer decimals, but reconciliation and exports must state whether they contain stored, calculated, or presentation-rounded values.
7. Changing a rounding rule or scale creates a new formula/rule version and must not silently alter historical verified results.

PostgreSQL's default `round()` behavior must not be assumed to implement every F2S boundary. The Calculation module applies and tests the approved mode explicitly.

## Allocation and residual conservation

Allocations must conserve the original amount exactly at the currency accounting scale.

For percentage or equal-share allocation:

1. Validate permitted recipients and allocation weights.
2. Calculate exact unrounded shares with Decimal.
3. Quantise each share downward to the smallest accounting unit for residual analysis.
4. Compute the integer number of remaining smallest units.
5. Distribute residual units to the largest fractional remainders.
6. Break equal remainders using a stable documented key, never database-return order or UI position alone.
7. Verify that final shares sum exactly to the source amount before commit.

Examples:

- `100 MMK` split equally across three stable recipients becomes `34`, `33`, and `33 MMK`.
- `10.00 USD` split equally becomes `3.34`, `3.33`, and `3.33 USD`.
- Repeating the same amount, weights, currency, and stable recipient identifiers produces the same shares.

A user-specified percentage allocation must reconcile to exactly `1.0` (100 percent) under the contract scale before confirmation. The system does not hide a missing or excess residual by arbitrary rounding.

## Exchange-rate representation and conversion

An exchange rate is always stored and labeled as:

`destination currency units per 1 source currency unit`

For example, `JPY per 1 USD` is different from `USD per 1 JPY`. Currency pair, direction, rate timestamp/date, source/provenance, and rule version accompany a rate wherever the detailed data design requires conversion evidence.

Conversion uses:

`unrounded destination amount = source amount * destination-per-source rate`

The result is then quantised once to the destination currency accounting scale using `ROUND_HALF_EVEN`.

Example:

- Source: `100.00 USD`
- Rate: `154.275000000000 JPY per 1 USD`
- Unrounded destination: `15427.500000000000 JPY`
- Final destination at JPY scale 0: `15428 JPY`

An exchange workflow must declare its authority mode:

- **Quoted-rate mode:** source amount and quoted rate are authoritative; destination amount is derived and quantised.
- **Settled-amount mode:** source and destination settled amounts are authoritative; an effective rate is derived when source is non-zero.

The database/API design must not accept an inconsistent authoritative triplet of source amount, destination amount, and rate. If all three are supplied for verification, the derived destination must equal the submitted destination after the approved quantisation or validation fails.

When source amount is zero, an effective exchange rate is unavailable; the system does not divide by zero or invent a rate.

## Percentage, ratio, and rate rules

- Percentages are stored and calculated as ratios: `0.075` means 7.5 percent.
- A UI accepting `7.5%` converts the decimal string exactly to `0.075` at the boundary and labels the unit.
- API field names and documentation state whether a field is a ratio, percent display, annual rate, periodic rate, or exchange rate.
- ROI, margin, loss percentage, interest rates, and allocation weights are distinct semantic types even when they share a numeric envelope.
- Rates are never added, compared, or applied without compatible period and basis metadata.
- A value outside its domain range is rejected; for example, ordinary allocation weights cannot be negative and their confirmed total must equal `1.0`.

## Zero-denominator and unavailable results

Division by zero never produces `0`, `NaN`, positive/negative infinity, an empty string, or an invented replacement denominator.

The Calculation contract returns an explicit unavailable result containing at least:

- stable reason code such as `ZERO_DENOMINATOR`;
- the affected calculation identifier;
- period/currency/unit context;
- data-quality or missing-input context; and
- no authoritative numeric value.

Examples:

| Calculation | Denominator | Zero-denominator result |
| --- | --- | --- |
| ROI = profit / actual investment | Actual investment | Unavailable; not `0%` |
| Profit margin = profit / revenue | Revenue | Unavailable; not `0%` |
| Loss percentage = loss / total harvest | Total harvest | Unavailable unless a separately documented empty-harvest rule applies |
| Yield = usable harvest / field area | Field area | Unavailable and identify missing/zero area |
| Effective FX rate = destination / source | Source amount | Unavailable; do not infer rate |

Dashboards, reports, forecasts, and AI explanations preserve the unavailable state and reason rather than replacing it with zero.

## Formula and result versioning

Each authoritative calculated result identifies or can be reproduced from:

- formula/rule identifier and version;
- exact source values and their currencies/units or a stable source snapshot reference;
- calculation precision and final quantisation scale;
- rounding mode;
- period/time context;
- availability and data-quality state; and
- assumptions for deterministic planning outputs.

Calculated outputs are not manually editable. Corrections change authorised source facts, after which the Calculation module produces a new versioned result.

## Persistence and API constraints

- Database columns use explicit precision and scale; unconstrained `NUMERIC` is prohibited for approved financial schema fields unless a separate justification defines its bounds.
- Money columns have a same-record or enforceable relational currency association.
- Check constraints support known scale/range/state rules where appropriate, but application/domain validation remains required.
- SQL expressions that coerce `NUMERIC` to floating point are prohibited in migrations, queries, aggregates, views, and reports.
- API decimal schemas accept/return canonical decimal strings, reject exponent form unless explicitly approved, reject locale separators, and document maximum digits/scale.
- CSV exports use plain decimal text and separate currency/unit columns.
- Excel exports write verified numeric values and formats carefully but do not make spreadsheet formulas the source of truth; a hidden binary representation difference must not feed back into F2S records.
- AI payloads label decimal values with currency/unit, period, availability, and data-quality context and never ask Gemini to calculate the authoritative result.

## Validation examples

The detailed test strategy must include at least these cases:

| Area | Example | Expected outcome |
| --- | --- | --- |
| Float prohibition | Attempt to create Decimal from Python float `0.1` in a verified path | Static/runtime guard or test failure |
| Decimal exactness | `0.1 + 0.2` using approved Decimal construction | Exactly `0.3` |
| Money scale | Ordinary `10.235 USD` input | Rejected; not silently rounded |
| Currency mismatch | Add `1000 MMK` to `5.00 USD` without conversion | Rejected |
| Half-even | Quantise `2.345` and `2.355` to 2 places | `2.34` and `2.36` |
| Allocation | Split `10.00 USD` equally among 3 stable IDs | Deterministic `3.34`, `3.33`, `3.33`; sum `10.00` |
| Percentage | Store/display 7.5 percent | Ratio `0.075`; display `7.5%` |
| Exchange direction | `100.00 USD` at `154.275 JPY/USD` | `15428 JPY` after one final half-even quantisation |
| Inconsistent FX triplet | Source/rate derives a different quantised destination than submitted | Rejected atomically |
| Zero denominator | ROI with zero actual investment | Unavailable with `ZERO_DENOMINATOR`; no numeric value |
| Negative ordinary event | Create ordinary expense `-1.00 USD` | Rejected; approved reversal uses separate workflow |
| Boundary | Largest valid amount at defined precision/scale | Accepted exactly; one digit beyond range is rejected safely |
| Cross-output reconciliation | Same filters across API, dashboard, PDF, Excel, CSV, and AI-preparation dataset | Values and availability states reconcile at documented precision |

## Fitness criteria

This decision remains fit when implementation evidence shows:

1. Static/dependency checks and tests find no binary floating-point value in verified numeric paths.
2. Database schema inspection finds no `REAL`, `DOUBLE PRECISION`, `FLOAT`, or unconstrained numeric field for approved financial concepts.
3. Boundary matrices cover maximum/minimum values, scales, signs, currencies, units, rates, percentages, allocations, and zero denominators.
4. Golden formula tests are shared by every consumer through the Calculation contract.
5. Equivalent API, dashboard, PDF, Excel, CSV, forecast, and AI-preparation datasets reconcile exactly at the declared output scale.
6. Allocation tests conserve the source amount and remain deterministic under reordering, retry, and concurrency.
7. Exchange tests prove direction, authority mode, provenance, quantisation, and inconsistent-triplet rejection.
8. Historical results retain their rule/version context when formula, currency registry, or display policy changes.

## Consequences

### Positive

- Financial results are deterministic and reproducible across storage and consumers.
- Currency, unit, period, availability, and data-quality context prevents unlabeled numeric meaning.
- Explicit scale and rounding rules support reconciliation and trustworthy exports.
- One Calculation owner prevents frontend, report, forecast, and AI divergence.
- Zero-denominator results remain honest instead of appearing as misleading zeros.

### Negative

- Decimal arithmetic and string-based API values require more deliberate code and validation than native floats.
- Currency scales, exchange direction, allocation residuals, and formula versions add domain metadata and tests.
- Some charting, spreadsheet, and provider libraries use binary floats, requiring a strict one-way display adapter boundary.
- Large exact precision can cost more CPU/storage than approximate types, so database design and performance tests must select indexes and ranges carefully.
- Changing a scale or rounding policy requires compatibility and historical-result decisions rather than a trivial formatting change.

### Risks and mitigations

| Risk | Mitigation |
| --- | --- |
| Float enters through JSON, ORM, library, or fixture | Decimal-string contracts, strict validation, static rules, schema inspection, representative integration tests |
| Multiple modules round differently | Single Calculation owner, versioned rule contract, golden shared tests |
| Allocation loses or creates a smallest unit | Deterministic largest-remainder method and exact conservation assertion |
| FX rate applied backwards | Mandatory source/destination labels and direction-specific field naming/tests |
| UI/export hides unavailable state | Typed result containing value-or-reason, cross-output reconciliation tests |
| Currency registry changes historical meaning | Version registry/rules and retain historical currency/scale context |
| Database accepts out-of-domain signed or scaled value | Domain validation plus explicit precision/scale and selected check constraints |

## Alternatives considered

### Binary floating point

Rejected for authoritative values because common decimal fractions are approximate and repeated arithmetic/rounding can diverge across Python, PostgreSQL, JavaScript, and spreadsheet tools.

### Store every money value as an integer smallest unit

Not selected as the universal representation. It works well for fixed minor-unit currencies but becomes awkward for four-decimal accounting values, exchange rates, unit prices, historical currency-rule changes, and intermediate calculations. Integer minor units may still be used inside a documented allocation algorithm after exact quantisation.

### Store decimals as text only

Rejected for persistence because it weakens database numeric constraints, ordering, aggregation, range checks, and indexing. Decimal strings remain the API transport representation.

### One `NUMERIC` type for all numeric concepts

Rejected because money, exchange rates, ratios, quantities, and unit prices have different scale, range, label, and validation semantics.

### Round half up everywhere

Rejected as the default because repeated half cases can create systematic upward bias. A legally or operationally required exception must be explicit, versioned, and tested for its narrow boundary.

## Revisit conditions

Review this ADR if a required currency, regulation, payment rail, accounting practice, quantity range, exchange workflow, or performance measurement cannot be represented safely within the selected envelopes. Any change must preserve deterministic reconciliation and include historical compatibility/versioning evidence.

## Scope note

This ADR defines numeric semantics and future storage/API constraints only. It adds no model, column, migration, formula implementation, endpoint, frontend component, report, or production configuration.
