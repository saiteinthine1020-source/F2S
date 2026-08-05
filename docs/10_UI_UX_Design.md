# F2S Shan-First Mobile UI/UX and Accessibility Design

## 1. Purpose and scope

This document defines the future F2S user-experience contract for mobile-first layouts, navigation, internationalisation, accessibility, forms, feedback, connectivity, privacy, and honest data states.

It follows the [Product Requirements](02_Product_Requirements.md), [Functional Requirements](03_Functional_Requirements.md), [Non-Functional Requirements](04_Non_Functional_Requirements.md), [Use Cases](06_Use_Cases.md), [System Architecture](07_System_Architecture.md), [REST API Design](09_API_Design.md), and [Farming Investment Design](11_Farming_Investment_Design.md).

This document does not create React components, CSS, design tokens, locale files, translations, routes, or visual implementation. Example labels are English specification text, not approved user-facing translations. Shan copy requires linguistic review before release.

## 2. Experience principles

1. Shan is the initial interface language; Myanmar, English, and Japanese are planned without redesigning components.
2. Every user-facing string and locale-sensitive value uses the approved internationalisation layer.
3. The smallest supported mobile experience is complete, not a reduced afterthought.
4. Verified records, missing information, forecasts, and unavailable calculations are visually and textually distinct.
5. Empty space is honest; F2S never invents projects, transactions, totals, charts, trends, or recommendations.
6. Every task remains understandable and operable by touch, keyboard, screen reader, zoom, and reflow.
7. Actions expose consequences before commitment and preserve recoverable input after failure.
8. Offline, loading, stale, synchronising, failed, and saved states are explicit.
9. Colour, position, motion, icon shape, and placeholder text never carry meaning alone.
10. The frontend communicates authority but never replaces backend authentication, authorisation, validation, or calculations.

## 3. Users and operating context

F2S supports Admins, Contributors, and Advisors using phones in household, farm, and small-business settings. Expected conditions include narrow screens, touch input, sunlight, intermittent connectivity, limited bandwidth, text magnification, shared-device risk, and differing financial or technical familiarity.

The reference-device matrix remains `TBD-VALIDATE` until representative member devices are recorded. Until then, every critical flow must satisfy the documented 320 CSS-pixel reflow, constrained-network, keyboard, screen-reader, zoom, and translation-expansion tests.

The interface must not assume:

- a desktop pointer or hover;
- continuous connectivity;
- high literacy in financial terminology;
- familiarity with icons;
- perfect colour perception or vision;
- that a workspace has existing records; or
- that a visible action is authorised merely because it appeared previously.

## 4. Information architecture and navigation

### 4.1 Primary destinations

The mobile shell exposes at most five persistent destinations for the current role. The
role-specific sets below are canonical; the union of possible destinations is:

| Destination | Purpose |
| --- | --- |
| Home | Current workspace, role-safe summary/launcher, attention items, and connection state |
| Transactions | Permitted income, expenses, transfers, farming activity, and history |
| Add | Permitted Admin creation or Contributor submission entry |
| Submissions / Activity | Contributor-owned Pending history and status without restricted totals |
| Status | Contributor submission outcomes and required corrections |
| Reports | Admin/Advisor permitted Approved datasets and generated outputs |
| More | Planning, remittances, debts, receivables, AI advice, workspace management, settings, and help according to phase and capability |

Before a later-phase destination exists, it is absent rather than represented by a dead control. Navigation labels use translation keys and pair icons with visible text. Icon-only primary navigation is prohibited. The Basic dashboard is the only MVP dashboard level.

Role-specific mobile navigation follows the workspace identity contract:

- Admin: Home, Transactions, Add, Reports, and More;
- Contributor: submissions/activity, Add, status, and More, with no totals or Reports; and
- Advisor: Home, Transactions, Reports, review/flag, and More, with no Add.

### 4.2 Mobile navigation

- A bottom navigation region is the preferred persistent pattern for the primary destinations.
- The current destination exposes selected state programmatically and visually without colour alone.
- The bar respects device safe areas and never covers content, validation, or the primary action.
- Scrolling does not hide the only route back or the only save action.
- `More` opens a titled, grouped destination list; it is not an unlabeled icon grid.
- Back behavior returns to the previous meaningful location and does not discard a draft without warning.
- Deep links restore workspace context only after current authentication and authorisation checks.

### 4.3 Larger layouts

At wider viewports, the same destination hierarchy may use a navigation rail or sidebar. Information order, names, permissions, and task outcomes remain consistent with mobile. Wider space may reveal supporting panels, but it must not make a mobile-required action desktop-only.

### 4.4 Page hierarchy

Each page provides, in reading order:

1. current workspace context when relevant;
2. one clear page title;
3. concise status or guidance;
4. the primary action when authorised;
5. filters or secondary actions;
6. verified content or an honest state; and
7. help, provenance, data-quality, or audit context where required.

Breadcrumbs are optional on mobile and must not be the only back mechanism. On desktop they may supplement, not replace, clear page titles and navigation.

### 4.5 Workspace and capability changes

- Workspace selection is an explicit named control, never inferred from colour or avatar alone.
- Switching workspace clears workspace-specific filters, selections, cached protected views, and unsaved context only after an appropriate warning.
- A stale bookmark or lost capability receives a safe state with a permitted next action; it never reveals foreign-workspace names or records.
- Hiding a control improves clarity but is not security. The backend reauthorises every request.
- Contributor clients never receive restricted totals to hide, mask, or replace with zero.

## 5. Responsive layout system

### 5.1 Baseline behavior

- Critical content and actions reflow at a 320 CSS-pixel-wide viewport without two-dimensional page scrolling.
- Content remains usable at 200 percent text zoom.
- Layouts tolerate at least 30 percent text expansion without clipping, overlap, hidden actions, or loss of meaning.
- Mobile forms use a single reading column. Related short fields may share a row only when they reflow cleanly and retain meaningful order.
- Content order follows DOM/reading order; visual repositioning must not create a contradictory focus order.
- Fixed heights are avoided for translated text, validation, cards, buttons, tabs, and navigation.
- Long identifiers and user-entered text wrap or truncate only with an accessible way to inspect the complete value.

### 5.2 Responsive transitions

Breakpoints are based on available content space, not device brand. A pattern changes only when its content no longer remains usable:

| Narrow behavior | Wider enhancement |
| --- | --- |
| Single-column page | Constrained content column or supporting side panel |
| Stacked form actions | Inline actions with preserved primary/secondary order |
| Card/list representation | Data table when comparison materially benefits |
| Bottom navigation | Navigation rail/sidebar |
| Full-page task flow | Dialog only when focus, zoom, keyboard, and text expansion remain safe |

Orientation changes preserve the current task, entered values, focus intent, and scroll context where practical.

### 5.3 Overflow exceptions

Documented data tables may scroll horizontally when a card/list alternative would destroy comparison meaning. The table must have a visible scroll cue, labelled region, sticky context only when it does not obscure zoomed content, and a non-table summary or export where appropriate. The whole page must not scroll in two dimensions.

## 6. Internationalisation and Shan-first content

### 6.1 Supported language plan

| Language | Locale identifier | Delivery state |
| --- | --- | --- |
| Shan | `shn` | Initial interface; linguistic review required for every critical flow |
| Myanmar | `my` | Planned extension |
| English | `en` | Planned extension and safe specification fallback where approved |
| Japanese | `ja` | Planned extension |

Language availability must reflect completed translation and review, not unfinished keys. Locale fallback behavior is explicit, tested, and never exposes raw translation keys in production.

### 6.2 Translation-key contract

Every visible or assistive user-facing string uses a stable semantic key, including:

- navigation and page titles;
- buttons, links, menus, tooltips, and accessible names;
- field labels, instructions, units, and required/optional indicators;
- validation, API error, session, permission, and offline messages;
- empty, loading, data-quality, forecast, warning, success, and confirmation text;
- status labels, table headings, chart summaries, legends, and export descriptions;
- dates, relative time, numbers, currencies, quantities, percentages, and plurals; and
- document titles, download names, notifications, and screen-reader-only text.

Key examples define intent rather than English wording:

| Intent | Example key |
| --- | --- |
| Farming empty-state title | `farming.investments.empty.title` |
| Add-investment action | `farming.investments.actions.add` |
| Required-field error | `validation.required` |
| Offline draft state | `sync.draft.saved_on_device` |
| Concealed not-found error | `errors.resource_not_found` |
| Chart unavailable reason | `analytics.unavailable.insufficient_data` |

Keys are not assembled from fragments. Complete sentences use variables and plural/select formatting so translators can reorder content. Variables are named by meaning, escaped safely, documented with context, and never contain markup that translators must repair.

### 6.3 Locale-sensitive formatting

- Dates, times, numbers, currencies, percentages, and quantities use approved locale formatters.
- Stored/API decimal strings remain exact; formatting changes presentation only.
- Currency code or unambiguous symbol remains visible where confusion is possible.
- Units are explicit and localised without changing canonical unit meaning.
- User input accepts only documented locale patterns and provides an unambiguous normalised review before consequential submission.
- Time-zone context is visible where a date or timestamp could change meaning.

### 6.4 Translation quality and layout

- No machine-generated or unreviewed Shan copy is treated as approved production content.
- Translators receive screenshots, key descriptions, variables, character limits where genuinely necessary, and financial/domain context.
- Critical flows receive linguistic review on reference devices before release.
- Pseudo-localisation tests at least 30 percent expansion, long words, mixed numerals, missing glyphs, and variable substitution.
- Fonts must contain complete glyph coverage for enabled languages and remain legible at supported sizes/weights.
- Language choice persists per approved account/device policy and remains reachable without understanding the current language through a recognisable, accessible language control.

## 7. Content and visual communication

- Use short, direct sentences and everyday language before specialist financial terminology.
- A technical term that cannot be avoided receives concise contextual help.
- Actions use specific verbs such as Add, Save draft, Record payment, Cancel investment, or Download report.
- Destructive/corrective actions state the object and consequence; generic `OK` is avoided.
- Facts, user-entered plans, deterministic forecasts, AI explanations, and unavailable results have explicit text labels.
- Advice never guarantees yield, price, profit, or financial outcome.
- Status uses text plus icon/shape where useful; colour is supplementary.
- Decorative imagery carries no required meaning and is hidden from assistive technology.
- Motion is nonessential, respects reduced-motion preference, and never blocks task completion.

## 8. Accessibility system

F2S targets WCAG 2.2 Level AA for all supported critical flows.

### 8.1 Structure and semantics

- Pages use one meaningful primary heading and a logical heading hierarchy.
- Landmarks identify header, navigation, main content, and complementary content where applicable.
- A skip mechanism moves keyboard focus to the main content.
- Native semantic controls are preferred; custom controls must reproduce name, role, value, state, focus, and keyboard behavior.
- Lists, tables, field groups, definitions, and status messages use semantics matching their meaning.
- Page title and main heading identify the current task and workspace context safely.

### 8.2 Keyboard and focus

- Every interactive control is operable without touch or pointer.
- Focus order follows reading/task order and never enters hidden or inert content.
- Visible focus has sufficient contrast and is not obscured by sticky regions.
- Opening a modal task moves focus to its title/first meaningful control, contains focus appropriately, supports Escape when safe, and returns focus to its trigger.
- Route and state changes move or preserve focus deliberately; they do not leave focus on removed content.
- No keyboard trap exists, including charts, tables, date controls, upload regions, and offline dialogs.

### 8.3 Touch and pointer

- Primary touch targets are at least 44 by 44 CSS pixels.
- Any smaller exception must be documented, meet WCAG 2.2 target-size requirements through size or spacing, and have an equivalent accessible action.
- Adjacent consequential actions have enough separation to prevent accidental activation.
- Hover reveals no unique required content; the same information is available by focus and touch.
- Dragging, swiping, or multi-touch gestures always have a simple control alternative.

### 8.4 Visual access

- Normal text contrast is at least 4.5:1 and large text at least 3:1; interactive boundaries and meaningful graphics meet applicable non-text contrast.
- Text is real text rather than text embedded in images, except essential logos.
- Meaning remains available in high contrast, grayscale, reduced motion, 200 percent text zoom, and 320 CSS-pixel reflow.
- Focus, errors, required state, selection, profit/loss, data quality, and chart series never rely on colour alone.
- Users can dismiss, move past, or avoid content that obscures focused controls.

### 8.5 Announcements

- Validation summaries, async completion, offline transitions, saved-draft state, and critical failures use appropriately timed live announcements.
- Routine loading does not repeatedly interrupt screen readers.
- Progress exposes a name and determinate value when known; otherwise it states that work continues.
- Toasts are not the sole source of important information and remain available long enough to perceive.

## 9. Forms and data entry

### 9.1 Field design

- Every field has a persistent visible label associated programmatically with its control.
- Placeholder text is an optional example, never the label or only instruction.
- Required and optional status is conveyed in text and programmatically before submission.
- Instructions precede the input or are programmatically referenced; character/unit limits remain available while editing.
- Related controls use a labelled group and meaningful order.
- Appropriate input purpose and virtual keyboard hints may improve entry but never replace validation.
- Money, rate, quantity, unit, currency, and date meaning remain explicit.
- Defaults come only from verified workspace settings or clear user choices; no fabricated financial values are prefilled.

### 9.2 Validation

- Client validation provides timely assistance; the server remains authoritative.
- Validation normally occurs on submit and after a visited invalid field changes, avoiding disruptive errors on each keystroke.
- Errors appear in a focusable summary and beside the affected field using the same translated message/code mapping.
- Error text states what happened and how to correct it without exposing internals or foreign data.
- Focus moves to the error summary after failed submission; links may move to each invalid field.
- Entered values remain available after validation, network, or server failure unless security requires clearing a secret.
- Correcting one field does not silently alter another field or derived backend result.

### 9.3 Submission and drafts

- The primary submit action has a specific label and remains distinguishable from Save draft, Cancel, and Back.
- Submission prevents accidental duplicate activation but does not trap the user in an indefinite disabled state.
- In-progress state identifies the action and preserves a safe retry path.
- Leaving a dirty consequential form requires a translated unsaved-changes warning.
- Successful submission shows the resulting authoritative record/state, not only a transient toast.
- Offline queueing is offered only for approved operations with idempotency and conflict handling.

## 10. Standard page and component states

Every data-bearing page defines applicable states before implementation:

| State | Required behavior |
| --- | --- |
| Initial loading | Retain title/navigation; expose progress without fake data or noisy announcements |
| Refreshing | Keep safe existing content, label staleness/refresh, avoid destructive layout shift |
| True empty | Explain that no verified records exist and offer an authorised next action |
| Filtered empty | State that no records match and offer clear/reset filters; do not imply no records exist |
| Insufficient data | Name the unavailable calculation/chart and the missing requirement |
| Permission unavailable | Provide a safe explanation and permitted navigation without protected details |
| Offline | Show connection state, freshness, local-draft/queue scope, and unavailable operations |
| Partial/stale | Identify which data is stale or unavailable and its last verified time when safe |
| Validation error | Preserve input; summary plus field messages; actionable correction |
| Request failure | Safe translated message, correlation/reference ID when useful, and valid retry/exit action |
| Success | Confirm the specific outcome and show resulting authoritative state |
| Conflict | Preserve local intent, explain newer server state, and require an explicit resolution |

### 10.1 Honest empty states

A true empty state may include a non-data illustration, title, explanation, and authorised action. It must not include:

- sample transactions, investments, workspace members, debts, or receivables presented as real;
- zero KPI cards that imply calculations occurred;
- fabricated charts, trends, profit, yield, forecasts, alerts, or recommendations;
- filters that have no records to filter; or
- success language before a record exists.

Demo or educational data, if introduced later, belongs in an explicitly isolated mode and is never mixed with workspace records.

### 10.2 Loading and skeletons

Skeletons approximate layout only and are hidden from assistive technology. They contain no plausible amounts, names, or chart patterns. A delayed or long-running request exposes meaningful progress and a safe cancel/leave option where possible.

### 10.3 Errors and recovery

Stable backend error codes map to translated messages; raw server English, stack traces, provider payloads, and internal identifiers are not displayed. A correlation ID may be shown with an accessible copy action when it helps support. Retry is shown only when safe and must respect idempotency, authorisation, and current connectivity.

## 11. Confirmation and consequential actions

Confirmation is required when an action is destructive, difficult to reverse, financially consequential, changes workspace access or ownership, discards a draft, transmits data externally, or changes authoritative lifecycle state.

A confirmation surface provides:

- a specific translated title;
- the affected record and workspace context without excess sensitive data;
- the consequence, reversibility, and downstream effect;
- any required reason or acknowledgement;
- a clearly named confirm action and a safe cancel action; and
- focus, keyboard, zoom, and screen-reader behavior equivalent to the underlying page.

Repeated low-risk actions should not create habituating confirmation dialogs. Typed confirmation is reserved for exceptional high-impact actions and cannot be the only protection.

## 12. Connectivity, offline, and synchronisation

- Connection status is visible when it changes task capability; browser `online` state alone is not proof that the service is reachable.
- Cached content shows freshness and workspace context and never appears as newly verified.
- Local drafts are labelled as saved on this device and distinguishable from server records.
- Queued actions show count, status, last attempt, safe retry/cancel behavior, and whether closing/signing out affects them.
- Synchronisation never silently overwrites newer financial records or creates duplicates.
- Conflict resolution presents local intent and current authorised server state without automatic financial merging.
- Signing out or switching workspace handles protected cached data and drafts according to the security design, with a clear warning before loss.
- Operations that are not approved offline are disabled with an explanation and a route to preserve a draft where safe.

Exact caching, queue, encryption, retention, and conflict mechanics are deferred to the PWA/offline and security issues.

## 13. Financial data, tables, and charts

### 13.1 Financial presentation

- Amounts always retain currency context; quantities retain units; rates state direction/basis.
- Negative, positive, zero, unavailable, and pending-calculation states use text/symbols in addition to colour.
- Source facts, calculated results, forecasts, and AI explanations are labelled distinctly.
- Rounding is presentational and does not change the authoritative value; expanded detail can expose required precision and formula/version context.
- Sensitive values may be masked by default according to role/context, with an accessible explicit reveal where authorised.

### 13.2 Tables and lists

- Mobile uses a prioritised list/card when row comparison is not essential.
- A data table has a caption, header associations, logical reading order, and translated sort/filter state.
- Sorting identifies field and direction in text/programmatic state.
- Pagination or load-more controls expose progress and result context without moving focus unexpectedly.
- Row actions are named for their record; a generic unlabeled overflow menu is insufficient for screen readers.

### 13.3 Charts and indicators

- A chart appears only when sufficient verified data exists.
- Every chart has a translated title, period, units/currency, data-quality/forecast context, text summary, and accessible table or equivalent values.
- Series differ by label and pattern/shape as needed, not colour alone.
- Tooltips are reachable by keyboard and touch or their information is available elsewhere.
- Missing/zero values are not plotted as each other.
- Forecast and historical series are visually and textually distinct; AI content is never blended into authoritative totals.

## 14. Security and privacy in the interface

- Authentication expiry, deactivation, and permission loss have distinct safe states and routes to sign in or exit.
- Session warnings identify remaining time accessibly and do not expose protected data on a lock screen.
- Secrets and full sensitive values are not placed in URLs, page titles, analytics labels, notifications, or clipboard by default.
- Reveal/copy/download controls are explicit, named, permission checked, and provide safe completion feedback.
- Screen content does not reveal another workspace through autocomplete, cached filters, recent items, error detail, or background requests.
- Contributor screens show submission status without official totals; Advisor screens expose only permitted reads, comments, and flags.
- External report/AI/file transmission identifies purpose and consequence before submission when consent/confirmation is required.
- The interface cannot promise that hidden controls prevent access; backend authorisation remains mandatory.

## 15. Component documentation requirements

Before a reusable component is implementation-ready, its specification records:

- semantic element and accessible name/description behavior;
- variants, sizes, states, and permitted combinations;
- keyboard, touch, focus, screen-reader, zoom, and reduced-motion behavior;
- translation keys, variables, expansion, wrapping, and locale formatting;
- loading, empty, disabled, read-only, error, success, offline, and permission behavior as applicable;
- contrast and non-colour cues;
- privacy/sensitive-data behavior; and
- automated and manual validation evidence.

Disabled controls are used only when the reason is apparent or available. If an action can be explained and safely attempted, an enabled control that yields guidance is preferred over an unexplained disabled control.

## 16. Validation matrix

| Area | Required future evidence |
| --- | --- |
| Responsive layout | Critical flows at 320 CSS pixels, wider breakpoints, portrait/landscape, and 200 percent text zoom |
| Translation expansion | Pseudo-localised screenshots at 30 percent or greater expansion; no clipping/hidden actions |
| Shan quality | Linguistic reviewer sign-off per critical flow on reference devices |
| Translation coverage | Static/runtime audit finds no planned hardcoded user-facing strings or raw keys |
| Keyboard | Complete task walkthrough, logical order, visible/unobscured focus, no trap |
| Screen reader | Names, roles, states, headings, errors, announcements, tables, charts, dialogs |
| Touch | Primary targets at least 44 by 44 CSS pixels; documented WCAG-compliant exceptions |
| Contrast/non-colour | Text, focus, controls, charts, status, errors, profit/loss, and grayscale review |
| Forms | Labels, instructions, required state, summary/inline errors, preserved input, duplicate prevention |
| Honest states | True/filtered empty, loading, unavailable, stale, offline, failure, conflict, and success fixtures |
| Connectivity | Disconnect/reconnect, local draft, queued action, retry, idempotency, conflict, workspace switch/sign-out |
| Privacy | Shared-device, session expiry, autocomplete/cache, reveal/copy/download, cross-workspace substitution, Contributor aggregate omission |
| Performance | Constrained-network usable content and interaction checks on approved reference devices |

Automated accessibility scanning is required but cannot replace keyboard, screen-reader, zoom, touch, translation, linguistic, and cognitive walkthroughs.

## 17. Deferred decisions and Issue #10 acceptance

Deferred to implementation or later design issues: exact visual tokens, approved fonts, concrete breakpoints beyond behavior requirements, animation timings, reference devices, locale library, translation-management workflow, PWA queue mechanics, protected-cache policy, notification delivery, and module-specific component schemas.

Issue #10 is satisfied when review confirms that:

- every planned user-facing and assistive string uses a translation key/locale formatter;
- Shan is the initial language with Myanmar, English, and Japanese extensibility;
- mobile and wider navigation cover critical modules without hidden mobile-only gaps;
- WCAG 2.2 AA, keyboard, screen-reader, touch, contrast, zoom, 320-pixel reflow, and 30-percent expansion responsibilities are explicit;
- true empty states never fabricate records, totals, charts, forecasts, or advice;
- loading, error, offline, confirmation, conflict, permission, and data-quality states have safe behavior;
- examples contain no real workspace data; and
- no React, CSS, locale file, visual implementation, or application code is created.
