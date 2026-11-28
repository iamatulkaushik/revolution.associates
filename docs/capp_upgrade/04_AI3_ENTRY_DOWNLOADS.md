# TRACK AI-3 — ENTRY & DOWNLOADS
Branch `capp_upgrades/ai3-entry`. Read `00_MASTER_PLAN.md` and `01_COMMON_RULES.md` first.

## Role
Data entry and outputs, used in **both** modes: employees, attendance, loans/advances, and the downloads (salary sheet, slips, abstract). In ASSOCIATE mode this is the owner's and operators' "helping hand". It is the track the most real users will touch daily, so validation and clarity matter more than features.

## Capabilities you need
Form/validation design, spreadsheet import (xls/xlsx) with preview-confirm, bulk PDF generation, permission gating, UI for fast keyboard entry.

## Read first
`Aapp/app/employee.py`, `Aapp/app/attandance.py`, `Aapp/app/loans_advances.py`, `Aapp/app/salary_processing.py`, `Aapp/app/salary_pdf*.py` and PDF views, `Capp/views.py`, `Capp/importer.py`, `Capp/import_views.py`, `Capp/bank_views.py`, `Capp/masters.py`, owner's workbook layout (ATT sheet: employee rows × days, codes and OT hours).

## Work packages
| ID | Package | Deliverable |
|---|---|---|
| **E1** | Employees | Add, edit, reactivate in Capp (relieve is DIRECT-only via AI-2/D6). Same validation as the importer (Aadhaar 12 digits and unique, mobile, account, IFSC, dates). Call `check_can_add(company)` before create and reactivate; show the plan message with remaining count. Permissions `employees.add/edit`. |
| **E2** | Attendance entry | Month grid: employees × days, codes (P, A, HD, WO, holiday, OT hours). Fast keyboard entry, save per month, per-row totals. Respects **D7 lock** (ASSOCIATE: locked once batch is PROCESSED; DIRECT: reopen rule). Writes through Aapp's attendance model, never a copy. |
| **E3** | Loans and advances | Create loan/advance for an employee with EMI schedule using Aapp's logic and models; list, view schedule, stop. No change to Aapp deduction logic. (Billing custom deductions in `Capp/billing_*` are a different feature; do not merge them.) |
| **E4** | Downloads | Salary sheet, salary slips (single and bulk zip via `BatchJob`), salary abstract, as PDF/Excel using existing Aapp generators. **One gate for both modes:** only when batch status is `APPROVED` or `PAID`; otherwise a clear "Batch not finalized yet" message. `payroll.download`. |
| **E5** | Operator home | Simple dashboard for operators: employees added this month, attendance days pending, loans entered, batch status, plan usage "n / limit". Shown when role is OPERATOR. |
| **E6** | Imports | Employee import keeps working with the plan limit (coordinate with AI-1's hook). **Attendance import** from the owner's ATT grid (xls/xlsx) with preview and confirm, same pattern as `Capp/importer.py`. |

## Must-haves
- All writes go through `@capp_perm(...)` and call `log_action` (who entered what).
- Entry screens obey the mode and the lock rule. A locked month is read-only with a visible reason.
- Imports never write on upload; preview first; bad rows are skipped and explained.
- Bulk slips run in background with a progress page; no request timeouts.
- Every download is tenant-scoped and permission-checked; a guessed URL for another company's slip is 404.
- No new copies of employee, attendance, or loan data.

## Acceptance tests
1. Employee create at the limit is blocked with the plan message; at limit−1 it passes; reactivation counts.
2. Attendance: save, edit, lock after PROCESSED (ASSOCIATE), operator without flag denied.
3. Loan creation produces the same schedule as Aapp for identical inputs (golden).
4. Downloads: DRAFT/PROCESSED batch → blocked; APPROVED/PAID → file; other tenant → 404.
5. ATT import: preview counts match the sheet; re-import updates, never duplicates.
6. Operator home shows only permitted blocks.

## Deliverable
Models (if any, prefix `ca_ent_`) in `Capp/entry/models.py`; URLs in `Capp/entry/urls.py` (`capp_ent_*`, prefixes `entry/` and `downloads/`); menu in `Capp/entry/nav.py`; templates in `templates/Capp/entry/`; tests `Capp/tests_entry_*.py`; handoff report.
