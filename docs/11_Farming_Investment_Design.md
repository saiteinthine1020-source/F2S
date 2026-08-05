# F2S Farming Investment Design

## 1. Purpose

The Farming Investment module tracks one real crop project through planning, costs, harvest, sales, profitability, and historical analysis. This document establishes product and UX rules before application implementation.

## 2. Domain distinction

### Crop category

A crop category is a reusable catalogue item, such as Orange or Corn. A user may create, edit, archive, search, and reuse a category.

A crop category:

- describes a kind of crop;
- can be reused across seasons and locations;
- contains no project budget, cost, harvest, sale, or performance by itself; and
- never causes an investment to be created automatically.

### Farming investment

A farming investment is a distinct project for one crop, season, year, location, and planting cycle. Two cycles for the same crop are separate records and must not be combined automatically.

A farming investment owns or links the project-specific plan, status, direct costs, shared-cost allocations, harvests, sales, notes, attachments, calculations, data quality, and audit history.

```text
Crop Category: Orange
  |-- Farming Investment: 2026 / Rainy Season / North Field
  `-- Farming Investment: 2027 / Rainy Season / North Field
```

Creating `Orange` creates only the category. The user must explicitly choose `Add Farming Investment` before a project exists.

## 3. Initial blank page

For a new workspace, the Farming Investments page is initially blank. It must not automatically create:

- sample farming investments;
- crop categories;
- example projects;
- investment or revenue totals;
- fake workspace or farming data;
- charts with fabricated or zero-filled series; or
- forecasts or recommendations.

The page presents a focused empty state rather than an empty data table or dashboard.

Required copy:

```text
Farming Investments

No farming investments have been recorded yet.
Add a crop project to track its investment,
expenses, harvest, sales, profit, and performance.

[ + Add Farming Investment ]
```

A simple non-data illustration may support the message. It must not depict values, trends, or completed investments.

## 4. Add Farming Investment action

`Add Farming Investment` is the primary action. It must:

- be visible without searching through a menu;
- have an accessible name;
- open a mobile-friendly page, drawer, or step-by-step flow;
- remain available after investments exist; and
- never pre-populate fabricated financial or performance data.

The initial form includes:

| Field | Behaviour |
| --- | --- |
| Crop category | Select an existing active category or enter the explicit create-category flow. |
| Season | Required workspace-appropriate label or controlled value. |
| Year | Required and validated. |
| Farm location | Required selection or permitted create-location flow. |
| Planned field size | Optional or required according to the later detailed requirements; must be positive when entered. |
| Field-size unit | Required when field size is entered and selected from workspace-configured units. |
| Planting date | Optional during planning; validated against related dates when entered. |
| Expected harvest date | Optional; cannot contradict the planting date. |
| Planned budget | User-entered, non-negative, decimal-safe monetary value. |
| Currency | Defaults from the workspace but remains explicit and configurable. |
| Initial status | `Planned` or `Active`; no implicit completed state. |
| Notes | Optional, length-limited, and safely handled. |

Advanced forecast inputs do not belong in this initial flow. They are introduced later through progressive disclosure.

Creating a project is an explicit, authenticated, authorised, auditable action. Duplicate-submission protection must be considered before implementing offline queueing.

## 5. Responsive empty states

### Mobile

```text
+--------------------------------+
| Farming Investments            |
|                                |
|       [simple illustration]    |
|                                |
| No farming investments have    |
| been recorded yet.             |
|                                |
| Add a crop project to track    |
| its costs, harvest, sales,      |
| profit, and performance.       |
|                                |
| [ + Add Farming Investment ]   |
+--------------------------------+
```

Mobile requirements:

- single-column layout;
- readable Shan-first text;
- prominent full-width primary button;
- touch target of an accessible size;
- no empty filters, tables, KPI cards, or charts; and
- no floating action button until its meaning is unambiguous to the user.

After projects exist, a floating `+` action may supplement the page action, but it must have the accessible label `Add Farming Investment`.

### Desktop

```text
+------------------------------------------------------------------+
| Farming Investments                     [ + Add Farming Investment ] |
|                                                                  |
|                    [simple illustration]                         |
|                                                                  |
|          No farming investments have been recorded yet.          |
|     Add a crop project to track investment and performance.      |
|                                                                  |
|                    [ + Add Farming Investment ]                   |
+------------------------------------------------------------------+
```

Desktop requirements:

- retain the primary action in the page header;
- centre the empty-state explanation within a constrained readable width;
- omit disabled filters and data visualisations until records exist; and
- ensure keyboard navigation and visible focus.

## 6. Initial calculation states

Immediately after a farming investment is created, the UI distinguishes real zero values from unavailable calculations:

| Display | Initial state | Reason |
| --- | --- | --- |
| Planned Budget | User-entered value | This is an explicit plan, not a calculated actual. |
| Actual Investment | `0` with `No expenses recorded` context | A newly created project has no recorded direct or allocated shared costs. |
| Revenue | `0` with `No sales recorded` context | No recognised sale has been entered. |
| Profit/Loss | `Not available` | Zero is not a valid completed result before the required cost and sale lifecycle is understood. |
| ROI | `Not available` | The calculation lacks a valid investment/result basis and must handle a zero denominator. |
| Recommendation | `Insufficient data` | No evidence supports a recommendation. |
| Graphs | Not rendered | Empty or fabricated series would mislead. |

Other permitted explanatory states include:

- `Crop cycle in progress`
- `Calculation pending`
- `Incomplete data`
- `Unreliable data`

The UI must not show a zero profit, zero ROI, successful status, or trend line as if analysis had been completed.

## 7. Project record and relationships

A farming investment should support:

- crop category;
- season, year, location, and planting cycle;
- planting, expected-harvest, and actual-harvest dates;
- field size and field-area unit;
- production target, actual production, and production unit;
- planned budget and currency;
- lifecycle status;
- notes and attachments;
- creator and timezone-aware timestamps; and
- archive/cancellation metadata and audit history.

Related records include direct expenses, shared-cost allocations, harvest records, crop sales, receivables, notes, and documents. These relationships determine which calculations are available.

Calculated values are read-only outputs of the backend calculation service. They are not manually editable project fields.

## 8. Costs and calculation availability

Direct costs belong to one investment. Shared costs use a recorded allocation method and values; percentage-based allocation must total 100 percent. Every allocation change is auditable and recalculates affected investments.

The single backend calculation service will eventually provide:

- total direct cost;
- allocated shared cost;
- total investment;
- gross and net revenue;
- gross and net profit;
- profit margin and ROI;
- break-even amount and selling price;
- cost per production unit;
- profit per field-area unit; and
- capital recovery rate.

The service must use decimal-safe arithmetic, documented rounding, compatible units, and safe zero-denominator behaviour. The frontend and reports consume these verified results rather than reimplementing formulas.

## 9. Lifecycle

| Status | Meaning | Expected transitions and restrictions |
| --- | --- | --- |
| Planned | Project exists but farming work has not started. | May move to Active or Cancelled. |
| Active | Farming activity and costs are in progress. | May move to Harvesting or Cancelled. |
| Harvesting | Harvest recording is in progress. | May move to Completed or Cancelled according to documented rules. |
| Completed | Crop cycle is closed for ordinary entry and available for history. | Corrections require an auditable mechanism; may be Archived. |
| Cancelled | The project will not continue. | Remains visible; linked financial records are preserved; reason and actor are recorded. |
| Archived | Hidden from default active views but preserved for history, audit, and analysis. | Can be viewed by authorised users and restored only through a documented action. |

### Cancellation

Cancellation is a business event, not deletion. It requires confirmation and a reason. Existing expenses, allocations, notes, documents, harvests, sales, and audit records remain intact. A cancelled investment is excluded or clearly identified in forecasts and comparisons according to later calculation rules.

### Archive

Archiving is an organisational action for completed or otherwise inactive projects. It sets archive metadata and removes the record from default active lists without erasing it. Archived projects remain available to authorised users and retain their contribution to historical analysis where applicable.

### Deletion

A simple permanent-delete action is prohibited once linked financial or historical data exists. Any exceptional deletion or correction policy must be separately designed, authorised, audited, and tested.

## 10. Detail-page actions

According to role, status, and linked data, a detail page may expose:

- Edit Project
- Add Expense
- Add Shared Cost Allocation
- Add Harvest Record
- Add Sale
- Add Note
- Upload Receipt or Document
- View Investment Breakdown
- View Revenue
- View Profit or Loss
- View ROI
- View Graphs
- Compare Previous Seasons
- Generate Report
- Archive Project
- Cancel Project

Unavailable actions must be omitted or disabled with an understandable reason. Later-phase actions must not be presented before their supporting data and services exist.

## 11. Validation and error states

- Required and cross-field validation is performed at both appropriate frontend boundaries and the backend.
- Money and quantity values cannot be negative unless a separately documented correction mechanism applies.
- Units must be selected from compatible workspace-configured units.
- Backend errors use stable codes and a correlation ID.
- Failed creation preserves the user's input and never produces a partial, apparently successful project.
- Authorisation and workspace ownership are checked for the project and every related record.
- Retry or offline synchronisation must not create duplicate investments or overwrite newer financial data silently.

## 12. Accessibility and internationalisation

- All visible text, validation, empty states, status labels, and notifications use translation keys.
- Shan is the initial presentation language; layouts must tolerate translated text expansion.
- Buttons and icons have accessible names and visible focus.
- Status is not communicated by colour alone.
- Content remains understandable on narrow screens and with screen magnification.

## 13. Audit and security

Creation, update, status transition, cancellation, archive, restore, expense link, allocation, harvest, sale, and report actions are audited with safe metadata. Audit logs do not copy unnecessary raw financial values.

Backend authorisation enforces workspace isolation. Attachments and generated reports require authenticated, authorised access and safe file handling.

## 14. Initial acceptance criteria

Before implementation of this module is considered complete, automated tests must verify:

- a new authorised workspace receives a true blank state;
- no investment is created by creating or selecting a crop category;
- the Add action is discoverable and accessible on mobile and desktop;
- initial fields and calculation states match this design;
- no chart or recommendation is rendered without sufficient verified data;
- workspace isolation applies to list, detail, create, update, archive, and cancel operations;
- cancellation and archive preserve linked history; and
- duplicate or failed submissions do not silently create inconsistent financial records.

No application code is created as part of this Phase 0 design.
