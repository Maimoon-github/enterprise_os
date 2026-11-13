# Tables: end-to-end checklist

Every operation a person does in a Clay-style enrichment spreadsheet, as a
manual test plan for Tables. Run it in a browser against a throwaway workbook
named `ZZ QA …`, and delete it afterwards. Each line is one operation and the
result that counts as a pass.

Paid steps are marked **$**. Keep them to two or three rows. The local dev
server pauses the grid worker (`PAUSE_GRID_WORKER`), so run columns are
filled by whichever deployment's worker is live — test those after a deploy.

## A. Files: folders and workbooks

| # | Operation | Pass when |
|---|---|---|
| A1 | Create a folder, rename it, nest a folder inside it | Shown in the list and breadcrumbs; survives reload |
| A2 | Create a blank workbook | Opens with one empty table |
| A3 | Create a workbook from a CSV/XLSX | Mapping screen, then rows and typed columns |
| A4 | Rename a workbook | New name in the list and the header |
| A5 | Move a workbook into a folder and back (menu and drag) | Appears in the right folder |
| A6 | Search the list | Only matching workbooks show |
| A7 | Delete a workbook and a folder | Gone after reload; nothing else affected |

## B. Tables (tabs inside a workbook)

| # | Operation | Pass when |
|---|---|---|
| B1 | Add a table | New tab, selected |
| B2 | Rename a table (menu and double-click) | Tab shows the new name |
| B3 | Reorder tabs (drag, Move left/right); Esc mid-drag | Order persists; Esc restores the old order |
| B4 | Duplicate a table | Same columns, rows and values; no spinners copied |
| B5 | Move a table to another workbook | Appears there, gone here |
| B6 | Delete a table; try deleting the only table | Deleted; the only table cannot be deleted |
| B7 | Switch tabs repeatedly | Each opens fast with its own data |

## C. Getting data in and out

| # | Operation | Pass when |
|---|---|---|
| C1 | Import CSV with quotes, commas, unicode, blanks, duplicates | Every value lands in the right cell |
| C2 | Import mapping: rename, retype, skip, map to existing | Applied exactly |
| C3 | Import a number column holding "N/A" | "N/A" kept as text, not dropped |
| C4 | Import XLSX | Same as CSV |
| C5 | Paste a block from Google Sheets/Excel | Cells fill; new rows/columns created as needed |
| C6 | Add rows (1 and many) | Appear at the end |
| C7 | Delete rows (one, several, all matching a filter) | Gone; counts update |
| C8 | Export CSV (all and filtered) | File opens; values and quoting correct |
| C9 | Dedupe on a column | Duplicates removed, first kept |

## D. Editing cells

| # | Operation | Pass when |
|---|---|---|
| D1 | Type into text, number, currency, date, URL, email cells | Saved; survives reload |
| D2 | Type "1,200" into a number cell; type "abc" | 1200 stored; "abc" kept as typed |
| D3 | Toggle a checkbox; choose a select / multi-select value | Saved and rendered as such |
| D4 | Edit a JSON cell | Opens as JSON text, saves as JSON, never `[object Object]` |
| D5 | Copy/paste a cell and a range (mouse and keyboard) | Values land where the focus is |
| D6 | Fill handle drag down | Value copied down |
| D7 | Delete/Backspace on a selection; Backspace inside an editor | Clears cells; editor still deletes characters |
| D8 | Undo / redo an edit | Restores the previous value |
| D9 | Arrow keys, Tab, Enter, Shift+arrow | Focus and selection move as in a spreadsheet |
| D10 | Open the cell details panel | Shows value, status, run history |

## E. Columns

| # | Operation | Pass when |
|---|---|---|
| E1 | Add each data type: Text, Number, Currency, Date, URL, Email, Image, Checkbox, Select, Multi-select, JSON | Created with the right icon and editor |
| E2 | Add the same type twice | Second is named "Text 2" |
| E3 | Rename; rename onto an existing name; rename to blank | Saved; duplicate and blank refused with a message |
| E4 | Change type (text→number with "1,200" and "abc") | 1200 converted, "abc" kept |
| E5 | Change a formula/HTTP column to a data type | Asks first; setup is lost only if confirmed |
| E6 | Insert column left / right | Lands there immediately |
| E7 | Drag to reorder; reload | Order persists |
| E8 | Resize; change page | Width kept |
| E9 | Hide / show; pin / unpin | Applied and persisted |
| E10 | Duplicate a data column | Copy has the values |
| E11 | Delete a column; delete one a formula uses | Deleted; referenced one refused with "used by" |
| E12 | Text to columns (split by delimiter) | New columns with the parts |
| E13 | Every column type opens the header menu, run columns with an Edit entry | Menu opens, Edit opens the dialog |

## F. Views: sort, filter, search, select

| # | Operation | Pass when |
|---|---|---|
| F1 | Sort asc/desc on text, number, date; multi-sort | Order correct |
| F2 | Filter each operator (is, contains, empty, >, <, before/after) per type | Correct rows |
| F3 | Filter "contains %" and "contains _" | Only literal matches |
| F4 | Filter groups AND/OR; disable a condition | Correct rows |
| F5 | Type quickly into a filter value | No dropped characters |
| F6 | Search box | Matches across columns |
| F7 | Reload | Sort and filters persist |
| F8 | Select rows, select all matching, clear | Counts right; actions apply to the selection |
| F9 | Paginate | Next/previous pages load; counts right |

## G. Formula column

| # | Operation | Pass when |
|---|---|---|
| G1 | `{{first_name}} + " " + {{last_name}}` | Full names |
| G2 | Number math, FormulaJS, lodash, moment | Correct values |
| G3 | Preview before saving | Shows row 1's result |
| G4 | Syntax error; unknown token; circular reference | Refused with a clear message |
| G5 | `LOOKUP("Other table", {{domain}}, "Domain", "Name")` | Value from the other table; blank key → blank |
| G6 | Generate a formula with AI **$** | Working expression |
| G7 | Edit an input cell | Formula recomputes (auto-run) |
| G8 | Run controls in the header; error cell shows its message | Run all / selected / first 10 work |

## H. Use AI (content)

| # | Operation | Pass when |
|---|---|---|
| H1 | Pick a model, write a prompt with `{{company}}` via the `/` picker | Token inserted; preview of tokens shown |
| H2 | One text output; save and run 3 rows **$** | Sensible answers in 3 rows |
| H3 | Several typed outputs (text, number, boolean) **$** | Each lands in its own column with the right type |
| H4 | JSON-schema output **$** | Fields extracted |
| H5 | Rename an output and save | Same column renamed, no orphan |
| H6 | Remove one output and add a new one | New column created; the old one keeps its data |
| H7 | Duplicate output names; blank output name; prompt using its own output | Refused, message next to Save |
| H8 | Row with all inputs blank **$** | Skipped, no answer invented |
| H9 | "Only run if" condition **$** | Rows failing it are not run |
| H10 | Rerun only empty / rerun all / run one row **$** | Only the chosen cells run |
| H11 | Stop a run | Queued cells return to idle |
| H12 | Model error (bad model or provider failure) | Error shown on the source and its outputs |

## I. Use AI (web research)

| # | Operation | Pass when |
|---|---|---|
| I1 | Web research use case, prompt "find {{company}}'s HQ city and employee count" **$** | Real, current facts for 2–3 known companies |
| I2 | Structured outputs from web research **$** | City and number in their own columns |
| I3 | Obscure / fake company **$** | Says it couldn't find it, does not invent |
| I4 | Sources in the cell details | Visible in run history |

## J. Enrichment providers

| # | Operation | Pass when |
|---|---|---|
| J1 | Open Add enrichment; browse providers | Connected ones usable, others prompt to connect |
| J2 | Map inputs (domain, name, LinkedIn URL); pick outputs | Saved; outputs become columns |
| J3 | Each connected provider on 2 rows **$** — Apollo, Hunter, FindyMail, Icypeas, Snov, Lusha, RocketReach, ContactOut, FullEnrich, Cleanlist (finders); MillionVerifier, ZeroBounce, Hunter verify (verifiers) | Real values in output columns; misses marked as such; costs recorded |
| J4 | Row missing a required input | Not run, no credit spent |
| J5 | Edit the enrichment: add an output | New column backfilled from the last successful run |
| J6 | Delete an output column; delete the source with its outputs | Output gone from the source; source deletion asks first |
| J7 | Async provider (waiting for provider) | Cell shows waiting, then the result |
| J8 | Provider error (bad key / rate limit) | Clear error on the cell |
| J9 | Chain: enrichment output feeds an AI column (auto-run) **$** | AI runs only after the email arrives |

## K. HTTP API column

| # | Operation | Pass when |
|---|---|---|
| K1 | GET with `{{token}}` in the URL, response path | Value extracted |
| K2 | Value with `&` or spaces | Sent encoded (one parameter, not two) |
| K3 | POST JSON body with tokens | Valid JSON sent |
| K4 | 404 / 500 response | Error on the cell |
| K5 | `authEnvVar` not starting with `GRID_HTTP_SECRET_` | Refused on save |
| K6 | Private or metadata address | Refused when run |

## L. Running, auto-run and progress

| # | Operation | Pass when |
|---|---|---|
| L1 | Table auto-run off, edit an input | Dependents do not run |
| L2 | Auto-run on, edit an input | Dependents run |
| L3 | Run first 10 with a filter matching nothing | Nothing queued, message shown |
| L4 | Progress while running | Spinners, then values without reload |
| L5 | Leave the page open for minutes during a run | Stays responsive |

## M. Hand-off

| # | Operation | Pass when |
|---|---|---|
| M1 | Create campaign from selected rows (open dialog only) | Dialog lists the right rows and fields |

## Not in Tables yet (Clay parity gaps)

Shown in the menu but disabled, or absent:

- **Find people / companies** sources that build a list from a search.
- **Waterfall** enrichment (try providers in order until one hits).
- **Merge columns**, **Functions**, **Message** column types.
- **Write to another table** / lookups that write, and CRM sync columns.
- **Scheduled re-runs** (refresh a column on a schedule) and webhooks into a table.
- Credit usage per workbook ("View credit usage" is disabled).
