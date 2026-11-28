# AI-3 HANDOFF REPORT (Entry & Downloads)

```
TRACK: AI-3     PACKAGES DONE: E1, E2, E3, E5, E6 (attendance import)     PACKAGES PARTIAL: E4 (challan files wait for register verification)
```
E4 is done for salary sheet, abstract, single slip and all slips. **Challan files and statutory returns are not built** (blocked on owner answers: `INVENTORY.md` section 7, items 2 and 4).

## Files added
`Capp/entry/{gates,downloads,employees,attendance,loans,home,urls,nav}.py` · templates `Capp/entry/{downloads_hub,employee_form,employees_relieved,attendance_grid,attendance_import_preview,loans_list,loan_schedule,operator_home}.html` · tests `Capp/tests_entry_{downloads,employees,attendance,loans,home}.py`

## Files changed
`Capp/views.py` (old slip/sheet/abstract URLs redirect to the gated path; employee list passes add/edit rights; dashboard adds the operator block) · `Capp/access.py` (payroll.download also needs the owner's `can_download_pdf`) · `Capp/context_processors.py` (nav entries may carry a plan `feature`) · `Capp/foundation/nav.py` (three PDF items replaced by the Downloads entry) · `templates/Capp/employees/list.html` (Add/Edit links; real designation, department and joining-date columns, which were always blank) · `templates/Capp/masters/form.html` (cancel link with arguments) · `templates/Capp/dashboard.html`

## What each package does
- **E1** Add, edit, reactivate employees on the Aapp `employee` model. Validation: Aadhaar 12 digits, mobile 10, account 9-18, IFSC, PAN (blank stored as NULL), joining after birth, department inside branch, contract dates. Masters limited to the company. Code is locked after creation. Plan limit checked on add and reactivate. Relieved list with Reactivate. District dropdown follows state.
- **E2** Monthly attendance grid (one summary row per employee). Blank row = no record. Any bad row blocks the whole save. OT at double the ordinary rate, exactly as Aapp. Shows employees with no entry (payroll then assumes a full month). Lock rule D7 in `gates.entry_lock_reason`.
- **E3** Loans and advances on Aapp `Loan`/`Advance`, golden-tested against Aapp's own form. Employee list always company-scoped. Principal and employee locked after creation. Stop instead of delete. Schedule page and PDF. Plan feature `loans`.
- **E4** One gate for every download: batch must be `APPROVED` (`PAID` accepted for the future). Salary sheet, abstract, single slip, all slips (cap 150). Audited. Operators need `can_view_wages` and `can_download_payroll`.
- **E5** Operator home block on the dashboard: my work this month, missing attendance, lock state, plan usage, links only for held permissions.
- **E6** Attendance import from the owner's ATT sheet: ID No., ATT (or TATT), H. OT column only if ticked. Preview, confirm, re-import updates. Employee import limit was done by AI-1.

## Contracts used
`capp_perm`, `has_perm`, `log_action`, `check_can_add`, nav schema (one optional key added: `feature`). No frozen signature changed. **No models added, so no new migrations.**

## Tests
72 new in this track. Full gate: `Ran 137 tests ... OK`, GATE PASSED.

## Decisions I made alone
1. Background wages-slips file is back, now that `BatchJob` has a migration (R8 resolved). Instant all-slips stays for up to 150 slips.
2. Overtime fields hidden on plans without `overtime` (copper), as the plan gate defines.
3. Loans entry locks on the **deduction start month**, not the creation date.
4. A loan's principal and employee cannot be edited after creation; stop and re-enter instead.
5. Overtime follows the owner's rule (double the hourly rate from basic, as Aapp). The grid has no rate column; register rates derive from the designation basic; the import preview shows the payroll amount; the grid warns when no Shop Act registration exists (payroll then pays no overtime).
6. The old URLs `wages/sheet/`, `wages/abstract/`, `wages/slip/<id>/download/` redirect to the gated path.

## Found, not fixed (needs your word)
- **R10 Aapp bug:** `create_loan` and `alter_loan` restrict the employee list only on GET. On POST any employee id from another company is accepted. One-line fix in Aapp. Capp is not affected.
- **R11 plan bypass:** Aapp lists `bank_file` as a Gold feature. Capp's Bank Payment Files page (my earlier work) has no plan check.
- **R12 ATT sheet:** the sample's OT column reads 80 while the invoice used 40 hours, and the day cells were blank. Daily codes are not parsed. OT import is therefore off by default.

## Open questions for the owner
See the consolidated list in the chat message (items 9 to 18).
