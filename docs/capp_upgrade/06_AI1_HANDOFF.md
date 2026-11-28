# AI-1 HANDOFF REPORT (Foundation & Governance)

```
TRACK: AI-1      PACKAGES DONE: F1, F2, F3, F4, F5      PACKAGES PARTIAL: F6 (see below)
```

## Files added
- `Capp/foundation/{__init__,models,views,nav}.py`
- `Capp/tests_foundation.py` (30 tests), `Capp/tests_integration.py` (9 tests: frozen signatures, nav schema, smoke of every menu URL for each mode x role, direct-only guard)
- `scripts/capp_gate.sh` (the full merge gate in one command)
- `Sapp/management/commands/backfill_license_max_employees.py`
- `templates/Capp/foundation/operator_list.html`, `audit_list.html`
- `templates/Sapp/operators/list_operators.html`
- Migrations: `Sapp/migrations/0003_company_management_mode_license_max_employees.py`, `Capp/migrations/0003_cappauditlog_companyoperator.py` (additive; apply after the existing 0002 files)

## Files changed
`Sapp/app/company.py` (mode field, mode guard) · `Sapp/app/license.py` (`max_employees`) · `Sapp/views.py`, `Sapp/urls.py` (licence field, operator list) · `templates/Sapp/company/{create,alter}_company.html`, `templates/Sapp/license/{issue_license,alter_licese,list_licenses}.html` · `Aapp/app/employee.py` (limit hook x3) · `Capp/access.py`, `audit.py`, `middleware.py`, `context_processors.py`, `models.py`, `urls.py`, `views.py` (login only) · `Capp/masters.py`, `billing_views.py`, `invoice_views.py`, `bank_views.py`, `import_views.py`, `importer.py` · `revolution/app/plan_limits.py` · `templates/Capp/base.html` · `Capp/tests_contracts.py`

## What each package does
- **F1** `Company.management_mode` (`DIRECT`/`ASSOCIATE`, default `ASSOCIATE`) on the Sapp create and alter company forms. Change is refused while any batch is open: `DRAFT` or `PROCESSED` (D5). `APPROVED` does not block, because Aapp never sets `PAID` (`INVENTORY.md` R1). Associate-created companies stay `ASSOCIATE`.
- **F2** `License.max_employees` (blank = unlimited) on issue and alter licence forms and the list. `plan_limits` reads the company's valid licence first, then plan default (copper 150, others unlimited). `License.max_users` untouched (Aapp sub-user seats). Hooks: Aapp single create, Aapp bulk import (per row), Aapp re-enable, Capp import preview (rows beyond room flagged). Dashboard badge shows "n / limit". Command `backfill_license_max_employees` (dry run by default, `--apply` writes).
- **F3** `CompanyOperator` model. Middleware sets `capp_mode`, `capp_role`, `capp_perms` and gives operators the same `owner_profile` interface as owners, so every existing view works for them. `has_perm` and `capp_perm` implement the matrix (POST denial = 403, page denial = redirect with message). Owner screens: list, add, edit flags, suspend/enable, password set. Capp login accepts owner or operator. Sapp superadmin list and suspend.
- **F4** Menu now data-driven: `Capp/foundation/nav.py` + `Capp.entry.nav` + `Capp.direct.nav`, filtered by permission and mode. A track URL that does not exist yet is hidden, never an error. Header shows mode and role badge and plan usage.
- **F5** Logins (owner and operator) are written to the audit log. `CappAuditLog` + real `log_action` (never raises). Owner screen with user, action and date filters, 50 per page. Calls added to masters, bank formats, billing, invoices, deductions month-paid, employee import, operators.

## Contracts used / kept
All frozen signatures unchanged. **Added:** four view permissions (`wages.view`, `statutory.view`, `compliance.view`, `reports.view`).
`masters_required` now means `capp_perm('masters.edit')`; new `billing_required` = `capp_perm('billing.manage')`; employee import now needs `employees.add`.

## Models added (migrated)
`CompanyOperator` (`ca_company_operator`), `CappAuditLog` (`ca_audit_log`). Fields added: `Company.management_mode`, `License.max_employees`.

## Tests
39 new. Full suite: **Ran 77 tests ... OK**, `scripts/capp_gate.sh` prints GATE PASSED. Gate: py_compile clean, `check` clean, `makemigrations --check` clean, duplicate URL names only the known `capp_login`.

## Decisions I made alone
1. **Bug fixed:** in the old menu, the Masters block sat inside the "attendance access" condition, so owners without attendance access lost Masters. The data-driven menu removes it.
2. Removed dead code in the old middleware (`process_request` never ran).
3. Masters/billing operator flags are forced off for ASSOCIATE companies (the matrix says never), with a note on the form.
4. Operators get no default write rights. View defaults: employees and attendance only.
5. Billing (`billing.manage`) is its own permission. Owners keep it through their existing `can_manage_masters` flag.
6. New migrations are `0003` on both apps, not a regeneration of `0002`, because 0002 may already be applied in your database.

## Correction made after the C1 inventory
My first F1 guard blocked a mode change while a batch was `APPROVED` and not `PAID`. Aapp never sets `PAID`, so that guard would have blocked every company with an approved batch forever. Fixed and tested.

## Added after the owner's answers
- Operators capped at 5 active per company; list shows "n / 5"; enabling a suspended operator respects the cap.
- New-operator form starts with add/edit employees, attendance, loans ticked.
- Associate screen (Aapp): list, suspend and enable a company's operators, with company membership checked.
- `challan.download` is DIRECT-only now (matrix and tests updated).
- Invoices only from `APPROVED` batches.
- Aapp `BatchJob` migration, bank-file plan gate, loan/advance employee scoping fix, migration-coverage guard test.

## Open questions for the owner (answered Nov 2026, see master plan section 10)
1. **Associate-side suspend (D3):** today associates have no screen for owners at all (only Sapp superadmin manages owners), so I added the suspend to the Sapp superadmin screen. Do associates need their own Aapp screen?
2. **Operator count:** nothing limits how many operators an owner creates. Use `License.max_users`? That field currently means Aapp sub-user seats.
3. **Owner flags vs operators:** an owner whose `can_view_wages` is off cannot download payroll. Intended?

## Known limits / for the next tracks
- `payroll.download` is a permission only. The "batch must be APPROVED or PAID" gate is AI-3 (E4).
- The three nav files for ENTRY and DIRECT are still empty; their items appear as soon as those tracks fill `nav.py`.
- Reactivation limit applies to the Aapp enable action. Capp reactivation (AI-3 E1) must call `check_can_add`.
- F6 remainder: merging tracks and the cross-track UAT happen at C2/C3.
