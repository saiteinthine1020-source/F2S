# F2S Verified Reports and Secure Export Design

## 1. Purpose and status

This document defines the future F2S report and export contract: authorised verified datasets, report types, filters, previews, print behavior, PDF, Excel, CSV, charts, asynchronous generation, protected artifacts, failure fallback, audit, retention, and cleanup.

It follows the [Product Requirements](02_Product_Requirements.md), [Functional Requirements](03_Functional_Requirements.md), [Non-Functional Requirements](04_Non_Functional_Requirements.md), [System Architecture](07_System_Architecture.md), [Database Design](08_Database_Design.md), [REST API Design](09_API_Design.md), [UI/UX Design](10_UI_UX_Design.md), [Security Design](15_Security_Design.md), [Test Strategy](17_Test_Strategy.md), [Data Dictionary](21_Data_Dictionary.md), and accepted numeric ADRs.

This document creates no report generator, renderer, template, download endpoint, storage resource, chart, workbook, database schema, or application code. Exact report layouts and field lists are approved with their feature/report implementation issues.

## 2. Reporting principles

1. Dashboard, preview, PDF, Excel, CSV, forecast, and AI preparation consume the same versioned verified dataset contracts.
2. Report renderers format verified results; they never query source-module tables, own formulas, or widen authorised fields.
3. Every request is authenticated, workspace scoped, capability checked, filter allowlisted, idempotent, auditable, and bounded.
4. Facts, calculated results, forecasts, assumptions, data quality, unavailable values, and warnings remain distinct in every format.
5. Missing data produces an honest empty/limited report, never fabricated totals, zero-filled charts, or sample records.
6. Currency, units, period, timezone, formula/rule version, dataset version, and generation time remain explicit.
7. Chart failure cannot block available verified tabular output.
8. Partial or invalid files are never published; a degraded but valid artifact identifies omitted/failed presentation sections.
9. Temporary artifacts are non-public, short lived, reauthorised at download, and deleted by policy.
10. Shan is the initial user-facing report language; all template text uses translation keys and supports Myanmar, English, and Japanese later.

## 3. Ownership and architecture boundaries

| Owner | Owns | Must not own |
| --- | --- | --- |
| Source modules | Authoritative finance/farming/funds records and read contracts | Cross-module report layouts or calculations |
| Calculation and Data Quality | Exact formulas, rounding, units, availability, quality and rule versions | File rendering or report access |
| Query and Dashboard | Authorised composition of immutable `VerifiedReportDataset` contracts | Source mutation or format rendering |
| Reporting and Exports | Request lifecycle, report registry, render orchestration, format validation, artifact metadata, expiry | Direct source-table queries or business recalculation |
| File Protection | Generated storage keys, protected bytes, checksums, safe delivery, expiry/deletion interface | Report fields, filters, or workspace capability decisions |
| Audit | Required safe request/generation/download/cleanup evidence | Raw report contents or access decisions |
| UI | Filter selection, preview/status display, accessibility, download initiation | Authoritative totals, permissions, or file truth |

Rendering and storage happen after the verified dataset snapshot is produced. They do not remain inside a core financial transaction and cannot roll back or mutate committed source facts.

## 4. Report definition registry

Each report type is a versioned definition with a stable uppercase code, required capability, supported formats, permitted filters, dataset schema, sections, columns, charts, orientation, limits, translation namespace, and retention class.

Initial report families are:

| Report code | Primary purpose | Initial supported outputs | Delivery phase |
| --- | --- | --- | --- |
| `HOUSEHOLD_FINANCIAL_SUMMARY` | Period income, expense, cash-flow and category summary | Preview/print, PDF, Excel | Phase 8 |
| `FINANCIAL_EVENT_DETAIL` | Authorised filtered event ledger | Preview, Excel, CSV | Phase 8 |
| `FARMING_INVESTMENT_PERFORMANCE` | Project costs, harvest, sales, payments and profitability | Preview/print, PDF, Excel, CSV detail | Phase 8 |
| `CROP_COMPARISON` | Historical crop/project comparison with quality context | Preview/print, PDF, Excel, CSV detail | Phase 8 after Phase 5 data |
| `PLANNING_SCENARIO` | Versioned hypothetical inputs, assumptions and outcomes | Preview/print, PDF, Excel | Phase 8 after Phase 5 planning |
| `FUNDS_AND_OBLIGATIONS` | Remittance allocations, debts, receivables and payment status | Preview/print, PDF, Excel, CSV detail | Phase 8 after Phase 6 data |

A requested format not registered for that report returns safe validation failure before dataset work. Adding a report/format is an explicit versioned design change, not a generic arbitrary-query export.

## 5. Request and filter contract

### 5.1 Request intent

A report request identifies:

- `report_type` and one `format` (`PDF`, `XLSX`, or `CSV`);
- workspace path context and current actor/capability;
- period start/end or explicit `as_of` date as defined by the report;
- workspace timezone and requested supported locale;
- report-specific allowlisted filters;
- archived/cancelled inclusion policy where permitted;
- currency presentation/conversion mode where the report supports it;
- report-definition version or current-compatible intent;
- idempotency key and correlation ID; and
- optional accessible title/description choices from allowlisted fields, never arbitrary template code.

Preview uses the same canonical request/filter model even when it returns synchronously.

### 5.2 Filter rules

- Period semantics state whether start/end are inclusive and use workspace business dates; generation timestamp remains UTC.
- Date ranges are validated for order and report-specific maximum span.
- IDs for investment, crop, category, location, payment method/status, member scope, debt, receivable, and other filters are verified against the same workspace.
- Unknown, duplicate, conflicting, or unsupported filters fail safely rather than being ignored.
- Filter order is canonicalised for idempotency/fingerprint comparison; user-visible order does not change meaning.
- Archived/cancelled/reversed records are included only when the definition and capability allow them, with status/context preserved.
- Free text is never a route to unrestricted source search or dynamic SQL/report expressions.

### 5.3 Currency, unit, and time policy

- Amounts always retain currency; quantities retain unit; rates state direction, basis, source and applicable time.
- Different currencies are grouped separately unless an approved conversion mode supplies versioned rates and one named reporting currency.
- No renderer sums unlike currencies or units.
- Exact decimal strings remain authoritative through the dataset; presentation quantisation follows the accepted numeric ADR and report definition.
- Workspace timezone defines period boundaries/display, while source/audit/generation instants remain timezone-aware UTC.
- `data_as_of` and `generated_at` are distinct.

## 6. Verified report dataset contract

The dataset is immutable and format neutral. Conceptually it contains:

| Group | Required content |
| --- | --- |
| Identity | Dataset/report type and schema versions; safe internal request/dataset ID |
| Scope | Workspace ID internally, authorised purpose/capability, canonical filters, period/as-of, timezone |
| Provenance | Source snapshot/as-of, calculation/formula/data-quality/rule/currency-unit registry versions |
| Locale context | Requested locale, fallback used, formatting policy; canonical values remain locale neutral |
| Summary | Typed KPIs/results with value-or-unavailable reason, currency/unit/period and quality |
| Tables | Stable table code, schema/column definitions, ordered typed rows, totals/subtotals from calculation owner |
| Charts | Stable chart code, title/summary keys, approved series/category references, units, display hints, availability |
| Context | Assumptions, warnings, missing inputs, data-quality limitations, forecast/fact classification |
| Integrity | Canonical dataset fingerprint/checksum and row/result counts |

### 6.1 Typed values

Dataset fields distinguish:

- exact money: decimal string plus currency;
- quantity: decimal string plus unit;
- ratio/rate: exact decimal string plus basis/direction;
- date and instant;
- stable state/code plus translation key;
- verified value with quality/provenance;
- forecast value with scenario/assumptions/uncertainty;
- unavailable result with stable reason; and
- safe display text/reference explicitly allowed for the report.

Null, zero, unavailable, not applicable, not yet calculated, and redacted are never interchangeable.

### 6.2 Snapshot consistency

1. The request is authenticated, authorised, rate/limit checked and canonicalised.
2. Query and Dashboard composes the dataset under one documented consistent read/snapshot boundary.
3. Source-module facts and Calculation/Data Quality results are captured with versions and `data_as_of`.
4. The immutable dataset is validated and fingerprinted before rendering.
5. Rendering consumes that exact snapshot even if source records later change.
6. The artifact identifies the dataset/version/as-of used; regeneration after source change creates a new dataset/artifact.

The implementation may use protected temporary serialized data or another approved snapshot mechanism. It may not rebuild each format independently from live tables.

### 6.3 Shared-source reconciliation

For equivalent workspace, period, filters, rules and as-of:

- dashboard/preview summary matches PDF and Excel summary exactly at declared scale;
- Excel/CSV detail rows correspond to the same authorised table rows/order/columns;
- charts reference series derived from those exact dataset values;
- unavailable/data-quality/warning states are preserved; and
- AI preparation, when applicable, receives a purpose-limited projection of the same verified version rather than a renderer output.

Any unexplained smallest-unit or availability difference is a correctness failure, not an acceptable formatting variance.

## 7. Honest empty, limited, and forecast states

### 7.1 True empty

An authorised request with no source records may return a valid empty dataset/report containing title, period/filters, explanation, permitted next action in preview, generation metadata, and no fabricated content. It must not include zero KPI cards implying calculation, sample rows, fake charts/trends, forecasts, or recommendations.

### 7.2 Filtered empty

The report states that no records match the selected filters and lists safe canonical filter context. It does not claim the workspace has no records.

### 7.3 Limited or unavailable

- A calculation/section states the missing input, quality limitation, incompatible unit/currency, or zero-denominator reason.
- Available tables/results continue without converting unavailable content to zero.
- Assumptions and warnings are near the affected output and included in a report-level limitations section.

### 7.4 Forecasts and plans

Hypothetical values are labelled `FORECAST`/scenario, separated from verified historical facts, and identify scenario version, inputs, period, assumptions, quality, uncertainty and generation time. No report promises yield, price, profit, or recommendation outcome.

## 8. Asynchronous request lifecycle

Persisted states follow the data dictionary exactly:

| State | Meaning |
| --- | --- |
| `QUEUED` | Request accepted/idempotency recorded; work not yet started |
| `RUNNING` | Dataset preparation, rendering or validation is active |
| `SUCCEEDED` | A complete validated artifact is available; completion quality may carry warnings |
| `FAILED` | No downloadable artifact; safe failure code/context available |
| `CANCELLED` | Cancel accepted before successful publication; no artifact available |
| `EXPIRED` | Retention elapsed; artifact is unavailable and cleanup is complete/pending safely |

Internal progress phases may be exposed as non-authoritative safe metadata but do not add undocumented persisted states. Percentage is shown only when measurable; otherwise the UI states that generation continues.

### 8.1 Creation and idempotency

- `POST` validates auth, capability, filters, limits and idempotency before expensive work.
- A queued request returns `202 Accepted` with `Location` to its protected status resource.
- Same key/fingerprint returns the original request/outcome; changed fingerprint fails safely.
- Concurrency and timeout-after-accept create at most one intended request/artifact.
- One request has one format and at most one published artifact. Multiple formats use distinct requests that may reference/reuse the same approved dataset snapshot internally.

### 8.2 Cancellation and retry

- Cancellation is an explicit authorised subresource and best effort after rendering begins.
- A cancelled/failed request never exposes partial bytes.
- Retry policy is bounded and distinguishes transient storage/renderer failure from permanent validation/limit/data failure.
- Re-render retry uses the same immutable dataset when safe; rebuilding from current data creates a new request/version.

## 9. Completion quality and chart fallback

`SUCCEEDED` artifacts include `completion_quality`:

| Quality | Meaning |
| --- | --- |
| `COMPLETE` | All required sections and approved optional charts rendered and validated |
| `DEGRADED` | Core verified tabular/text output is complete and valid, but one or more non-core visual sections failed/unavailable; warnings identify them |

This quality is artifact/report metadata, not a new request state.

If a chart cannot render:

1. retain its title, accessible summary, units/period and verified alternative table when data exists;
2. add a safe translated warning such as chart unavailable while table data remains available;
3. continue other sections/formats independently;
4. validate the resulting file; and
5. mark `SUCCEEDED` with `DEGRADED` only if the report definition permits chart fallback.

If verified table data, required text, page/sheet structure, checksum, or file validation fails, the request is `FAILED` and no artifact is published. Chart failure never causes CSV data loss because CSV has no charts.

## 10. Preview and print behavior

- Preview is an accessible HTML representation of the same dataset/version and canonical filters.
- Preview does not become a second calculation implementation and does not silently refresh to different source data while representing a queued artifact.
- A visible `data_as_of`, generation/request state, locale, period, filters, quality and warning context distinguish preview from live dashboard state.
- True/filtered empty, unavailable, degraded, failure, expired and permission-lost states follow the UI/UX design.
- Print uses the approved PDF where exact paginated output is required. Browser-print preview may be offered only with a tested print stylesheet and the same dataset.
- Print actions do not expose browser navigation, hidden controls, secrets, internal IDs or unrelated workspace context.

## 11. PDF specification

PDF is backend generated with the planned WeasyPrint document renderer and Matplotlib charts unless a future ADR changes the stack.

### 11.1 Page and content

- A4 is mandatory; orientation is versioned per report/section and wide tables use an approved landscape page or repeated-column strategy.
- Margins reserve readable header/footer space and printable-device tolerance.
- The document includes report title/type, workspace-safe display context when allowed, period/as-of, canonical filters, generated UTC/local timestamp, locale, dataset/formula versions, and page numbers where relevant.
- Relevant KPIs, tables, graphs, assumptions, warnings, quality/unavailable reasons and data provenance are included.
- Repeated table headers, sensible row/page breaks and section keep rules prevent orphaned headings, clipped rows and unreadable fragments.
- No report is an image-only PDF; text is searchable/selectable.

### 11.2 Accessibility and language

- Document title, language, logical reading order, headings, lists, links, table headers and chart alternative text/summary are available to assistive technology to the capability required by the approved PDF accessibility profile.
- An accessible HTML preview and equivalent data tables remain available; this does not excuse an inaccessible PDF.
- Shan is initial; all labels/copy use translation keys and approved fonts with complete enabled-language glyph coverage.
- Fonts are embedded/subset safely; missing-glyph substitution, tofu boxes and font-dependent value changes fail validation.
- Text wraps/expands without clipping, overlap, hidden warnings or lost meaning.

### 11.3 Grayscale and charts

- Meaning never relies on colour; series use labels plus distinguishable line styles, markers, patterns or direct annotation.
- Grayscale output preserves contrast for text, focus-equivalent links, table boundaries, warnings and charts.
- Vector charts are preferred. Required raster charts render at a minimum 300 DPI at final print dimensions (**Provisional**) with fixed layout/fonts for reproducibility.
- Every chart includes title, period, unit/currency, legend/direct labels, data-quality/forecast context and a nearby/referenced data table.
- Missing and zero values are rendered differently; incomplete series are not bridged misleadingly.

### 11.4 Validation

Automated checks inspect page count/size, text/metadata, fonts, links, values, headings/tables where supported, and render every page to images. Visual review covers A4 print, clipping/overlap, page numbering, grayscale, glyphs, long translations and chart/table correspondence. The selected renderer/version must demonstrate the required accessible-PDF output or trigger a design/ADR decision before release.

## 12. Excel specification

Excel output is `.xlsx`, generated with XlsxWriter unless ADR-010 changes the decision.

### 12.1 Workbook structure

| Sheet family | Purpose |
| --- | --- |
| `Read Me`/metadata | Report type/version, period/filters, generated/data-as-of, currency/unit, assumptions, warnings, quality, definitions |
| `Summary` | Authoritative verified KPIs/totals and quality/unavailable context |
| `Dashboard` | Native Excel charts linked to workbook data when sufficient verified data exists |
| Detail sheets | Stable report-specific typed rows, totals/subtotals and filters |
| Lookup/context sheets | Explicit code/label/unit definitions when required; never hidden authority |

Sheet inclusion/order/names are versioned. Sheet names are translated or stable according to the report definition, remain within Excel limits, are unique after sanitisation, and exclude control/path characters.

### 12.2 Data and numeric integrity

- Summary totals and verified calculated outputs are written from the dataset, not independently recomputed by workbook formulas.
- Detail columns have stable meanings, data types, formats, currency/unit companions and documented null/unavailable behavior.
- Native charts reference visible or clearly documented worksheet data derived from the same dataset.
- Excel formulas may support transparent convenience/checks but are never the authoritative source and cannot feed back into F2S.
- Exact decimals are finally quantised by the backend. A numeric-cell adapter is allowed only for magnitudes/scales that round-trip in supported spreadsheet software at the declared display scale; tests compare opened values to exact dataset values.
- Values outside that safe numeric envelope are written as exact text with an explicit note and are excluded from numeric formulas/charts rather than silently losing precision.
- Currency/unit/rate direction stays visible; incompatible currencies/units are never summed.
- Date cells use unambiguous values/formats and the metadata sheet identifies timezone/period rules.

### 12.3 Usability, accessibility and safety

- Header rows, freeze panes, filters, widths, wrapping, number formats, print areas, repeated print headings and sensible page setup are applied by the report definition.
- Headings/labels and warnings are meaningful without colour; charts have titles, labels/legends and adjacent source data.
- Empty/unavailable sections state why; they do not contain invented rows/formulas/charts.
- No macros, VBA, external workbook links, external data connections, hidden executable content or password claim is included.
- User-controlled text beginning with spreadsheet formula/control prefixes is neutralised and tested so opening the workbook cannot execute it.
- Workbook properties contain no secret or unnecessary personal/internal path information.

### 12.4 Validation

Programmatic validation covers workbook open, expected sheets/cells/types, formulas, named ranges, tables, filters, charts/series references, styles, properties and no external links/macros. Supported spreadsheet-software review confirms no repair warning, usable filters/charts, print behavior, long translations, grayscale/non-colour meaning and exact value display.

## 13. CSV specification

CSV represents one registered raw tabular dataset per artifact. It contains no charts, merged cells, styling, presentation-only KPI cards or invented totals.

- Media type is `text/csv; charset=utf-8`.
- The initial download encoding is UTF-8 with BOM for intended Excel compatibility (**Provisional**, verified across supported consumers).
- Delimiter is comma, records use CRLF, fields follow consistent RFC 4180-style quoting, and embedded quote/newline/delimiter cases are tested.
- Header names are stable documented machine-oriented column codes; translations and schema definitions live in report metadata/documentation, not unstable headers.
- Dates are ISO 8601, instants RFC 3339 UTC, booleans/codes stable, UUIDs canonical, and decimals plain exact strings without locale separators/exponents.
- Money/currency, quantity/unit and rate/direction/basis use separate explicit columns.
- Null/unavailable/redacted meanings are documented and not silently written as numeric zero.
- Row order follows a stable documented sort with ID tie-breaker.
- User-controlled cells that could be interpreted as spreadsheet formulas/control content are prefixed/escaped by the documented spreadsheet-safe text policy; this transformation is tested and included in the export schema contract.

Multi-table reports expose separately registered CSV datasets/requests. A ZIP/archive bundle is not in the initial baseline.

## 14. Chart contract

Charts are projections of dataset series, not independent queries or calculations.

Each chart definition records:

- stable chart/definition version and translation keys;
- chart type and why it suits the comparison;
- source table/column/row selection and stable ordering;
- category/time axis, series, currency/unit, scale and zero-baseline policy;
- missing/zero/unavailable/outlier handling;
- history/forecast/plan distinction;
- minimum sufficient-data rule and quality threshold;
- colour-independent styles and accessible summary/table;
- legend/labels/annotation and number formatting; and
- format-specific renderer hints that cannot change values.

Pie/donut charts are avoided for negative values, too many categories or comparisons where precise difference matters. Dual axes require explicit evidence and labeling and cannot imply a relationship unsupported by data. Truncated axes, smoothing, interpolation or aggregation that can mislead require a versioned documented rule.

## 15. File naming, storage and delivery

### 15.1 Safe filename

The suggested download name is server generated from allowlisted ASCII components:

`<report-code>_<period-or-as-of>_<generated-utc>.<ext>`

Synthetic example:

`farm-performance_2026-01-01_2026-12-31_20260805T120000Z.pdf`

Rules:

- lowercase ASCII letters, digits, hyphen, underscore and period only;
- maximum 120 characters including extension (**Provisional**);
- no workspace/person name, secret, internal path, UUID unless explicitly required, control/bidi character, leading dot, trailing dot/space, path separator, drive prefix, traversal, shell metacharacter or reserved device name;
- extension comes from the server-selected format, never user input; and
- `Content-Disposition` uses a safely encoded `filename`/`filename*` policy with `nosniff`.

### 15.2 Storage and atomic publication

- Storage key is random/server generated and unrelated to the filename or workspace path.
- Dataset/intermediate/partial bytes remain in a protected work area inaccessible to download.
- A renderer writes to a unique temporary object, validates complete type/structure/size/checksum, then publishes metadata and availability atomically.
- PostgreSQL stores request/artifact metadata and protected-file reference, not large report bytes.
- Storage is outside public web roots/buckets and denies directory listing/public ACL.
- Failed/cancelled/partial bytes are deleted; cleanup failure is observable and retried safely.

### 15.3 Download

- Status and download recheck current session, Active membership, capability, workspace, request/artifact ownership, `AVAILABLE` file state and expiry.
- Lost permission prevents download even when the actor created the request.
- The initial unguessable download reference expires after 5 minutes (**Provisional**) or bytes stream through an authorised endpoint.
- Response uses HTTPS, exact media type, safe disposition/name, `X-Content-Type-Options: nosniff`, and `Cache-Control: no-store`.
- Reports are not stored in PWA/offline caches, browser local storage, analytics or notifications.
- Range/resume behavior, if enabled, repeats authorisation and cannot reveal size/existence across workspaces.

## 16. Authorisation and privacy

Authorisation occurs at request creation, dataset composition, async execution, status read, cancellation, artifact publication, every download/preview/print access, and protected cleanup/administration.

- Report capability is distinct from source mutation and from audit-administration capability.
- Definition/role field allowlists prevent a report from exposing more columns than the actor may view.
- Restricted names, contacts, addresses, payment/bank details, references, notes and attachments are excluded by default and included only for a documented purpose/capability/report.
- Cross-workspace path/body/filter/cursor/dataset/request/file substitutions return safe concealed behavior and cause no renderer/storage work.
- Preview/status/errors/logs/audit do not reveal another workspace's report existence, title, filters, row/page/byte count or expiry.
- Contributor report requests are denied and receive no restricted totals, counts, metadata, or artifacts; official report datasets contain only Approved records.
- No password, token, cookie, authorisation header, API key, private key, raw attachment, unmasked AI payload or internal storage path enters a report or metadata.
- Generated artifacts inherit the maximum classification of included data and are protected accordingly.

## 17. Limits, quotas and performance

Initial limits are **Provisional** until production-like measurement:

| Limit | Initial value |
| --- | --- |
| Report/export request rate | 5 per actor per 10 minutes; 10 per workspace per 10 minutes |
| Concurrent jobs | Maximum 2 per workspace |
| Standard PDF generation | 30 seconds p95 on reference dataset |
| Standard CSV generation | 30 seconds p95 on reference dataset |
| Standard Excel generation | 60 seconds p95 on reference dataset |
| PDF artifact | 500 pages and 25 MiB maximum |
| Excel artifact | 250,000 detail rows total and 50 MiB maximum |
| CSV artifact | 1,000,000 rows and 100 MiB maximum |
| Published artifact retention | 24 hours |
| Download reference | 5 minutes |

Report definitions may set lower span/row/page/size limits. Estimates reject clearly excessive requests before rendering; streaming/chunking and worker resource limits prevent memory/disk exhaustion. Crossing a limit returns safe validation or async failure with no partial artifact. Backpressure queues within a measured maximum and rejects excess rather than overcommitting the server.

The reference workspace dataset remains 100,000 finance events, 5,000 investments and 50,000 related records. Limits and timings are measured with declared filters, dataset distribution, worker concurrency, renderer versions, fonts, CPU/memory/disk and cache state.

## 18. Failure and recovery contract

| Failure | Required outcome |
| --- | --- |
| Authentication/capability/filter invalid | Reject before dataset/render/storage work; safe API error |
| Dataset composition/validation fails | `FAILED`; no renderer call or artifact |
| Required formula/result inconsistent | `FAILED`; never render a conflicting value |
| Optional chart unavailable/render fails | Valid table/text retained; `SUCCEEDED` + `DEGRADED` when definition permits |
| PDF/workbook/CSV structural validation fails | `FAILED`; partial file unavailable/deleted |
| Storage publish fails | `FAILED` or bounded retry; no available metadata pointing to partial bytes |
| Worker crash/timeout | Lease/retry policy detects; bounded retry or `FAILED`; idempotency prevents duplicate artifacts |
| Cancellation | Best effort; `CANCELLED` unless atomic publish already succeeded |
| Permission lost after request | Work may cancel/complete by policy, but status details/download remain protected |
| Cleanup fails | Artifact becomes unavailable at expiry; cleanup retries/alerts without extending user access |
| One format fails | Other independently requested formats remain unaffected and retain their own states |

Stable safe job failure codes include dataset unavailable, unsupported format, limit exceeded, render failed, validation failed, storage unavailable, cancelled and expired intents. Exact API code registration occurs with implementation and uses translation-key mappings rather than raw exception/provider text.

Core financial records are never changed, rolled back or locked for the duration of rendering. Retry does not silently change the dataset snapshot.

## 19. Audit, logs and monitoring

### 19.1 Audit events

Policy-required events include report requested, rejected, started, succeeded complete/degraded, failed, cancelled, downloaded, expired and artifact deleted/cleanup failed.

Safe audit metadata may include actor, workspace, report type/definition version, format, canonical safe filter summary, dataset/formula version, completion quality, row/page/byte counts, checksum reference, failure code, timestamps, correlation and request/artifact safe ID. It excludes report rows/values, raw free text, credentials, headers, filesystem/storage paths and unnecessary restricted fields.

### 19.2 Operational logs/metrics

- Structured logs use request/correlation/job IDs and safe stage/event codes without bodies/datasets/artifact bytes.
- Metrics cover queue depth/age, active jobs, dataset/render/validation/storage/download duration, success/degraded/failure/cancel/expiry, output size/pages/rows, retries, cleanup age/failure and resource use.
- Alerts cover stuck/old jobs, repeated renderer/storage failure, limit/abuse spike, cleanup backlog, disk threshold and expired-but-present bytes.
- Cardinality is bounded; workspace, filename, filter values and report contents are not metric labels.

## 20. Retention and cleanup

- Published report/export bytes expire 24 hours after successful publication (**Provisional**).
- Dataset snapshots, intermediate files and partial artifacts are deleted as soon as no longer required and no later than artifact expiry; failed/cancelled temporary bytes target deletion within 1 hour (**Provisional**).
- Request/audit metadata follows the security retention matrix independently from artifact bytes and stores no full dataset.
- Expiry makes download unavailable first, then cleanup deletes bytes using exact protected storage keys.
- Cleanup is idempotent, bounded, workspace/purpose scoped, safe against reused/missing keys and audited minimally.
- Failed deletion retries with backoff and alerts before storage risk; it never restores user-visible availability.
- Backup policy defines whether temporary artifacts are excluded; a backup must not unintentionally extend public/download access.
- Legal/business retention changes require classification, access, key, deletion and backup review; users are not promised immediate erasure from protected backups.

## 21. Validation matrix

| Area | Required future evidence |
| --- | --- |
| Dataset consistency | One `REPORT_GOLDEN` filter reconciles dashboard/preview/PDF/Excel/CSV and AI projection exactly |
| Numeric integrity | Decimal/rounding/currency/unit/FX/unavailable values and Excel round-trip safe envelope |
| Authorisation | Two-workspace request/filter/job/status/cancel/dataset/file/download/expiry substitutions; no side effects |
| PDF | A4, pages, metadata/text/fonts/glyphs, values, tables/charts, grayscale, accessibility, visual render |
| Excel | Opens without repair; sheets/types/formulas/tables/filters/native charts/references/print/safety/accessibility |
| CSV | UTF-8/BOM, delimiter/CRLF/quoting, stable columns/types/order, exact values, formula-injection safety |
| Empty/quality | True/filtered empty, missing/zero/unavailable, poor quality, forecast/assumption/warning fixtures |
| Chart fallback | Every chart failure point retains valid tabular output or fails safely per definition |
| Lifecycle | Queue/run/succeed complete/degraded/fail/cancel/expire, concurrency, idempotency and timeout-after-commit |
| Files | Safe name/key/path/type/size/checksum/atomic publish/no-store/download expiry/partial/cleanup |
| Limits/performance | Reference and maximum span/rows/pages/bytes/concurrency/time/resource/backpressure |
| Audit/privacy | Required safe events plus prohibited-value canaries absent from logs/audit/files/metadata |
| Localisation | Shan linguistic review, glyph/font embedding, translation keys, long expansion and locale formatting |
| Failure isolation | Renderer/storage failure never mutates or rolls back committed core records |

Tests use synthetic data only and follow `docs/17_Test_Strategy.md`. A check is reported passed only when it executes successfully; manual PDF/Excel/accessibility review records exact artifact/build/environment evidence.

## 22. Deferred decisions and Issue #13 acceptance

Deferred: exact per-report fields/layouts/charts, PDF accessibility conformance profile/tool, approved Shan/Myanmar/Japanese fonts, final orientations/page templates, CSV BOM after consumer testing, Excel safe numeric envelope, renderer/library versions, job runner/lease mechanism, snapshot serialization/storage, maximum limits after capacity tests, preview endpoint/schema, download streaming/range policy, cleanup schedule, and legal retention.

Issue #13 is satisfied when review confirms that:

- dashboard, preview, PDF, Excel, CSV and AI preparation use shared versioned verified sources without renderer calculations;
- report types, filter/period/currency/unit/as-of and immutable dataset contracts are explicit;
- PDF is A4, print-friendly, grayscale-readable, accessible and contains required context;
- Excel sheets, summaries, totals, native charts, filters, exact-value boundary and safety rules are explicit;
- CSV is raw tabular, UTF-8/Excel-compatible, stable, locale-neutral and formula-injection safe;
- every chart has an accessible table/summary and chart failure does not block available tabular output;
- workspace authorisation, field minimisation, safe filenames/keys, traversal resistance, limits, temporary storage, protected download, audit, expiry and cleanup are defined;
- failure/degraded behavior never publishes invalid/partial files or affects core records;
- examples contain no real workspace data; and
- no report generator, template, chart, endpoint, schema, storage resource or application code is created.
