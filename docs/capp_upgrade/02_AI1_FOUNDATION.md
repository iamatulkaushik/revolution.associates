# TRACK AI-1 — FOUNDATION & GOVERNANCE
Branch `capp_upgrades/ai1-foundation`. Read `00_MASTER_PLAN.md` and `01_COMMON_RULES.md` first.

## Role
You own the shared skeleton: company mode, plan limits, roles, menu, audit, migrations, integration. The other two tracks code against your frozen contracts, so your first deliverable is making the Phase 0 stubs real **without changing any signature**.

## Capabilities you need
Django models/migrations, middleware and context processors, template refactor, Sapp admin screens, test design (matrix tests), careful merging. You must be able to run Django tests and git.

## Read first
`Capp/access.py`, `Capp/views.py` (`owner_required`, `access_required`), `Capp/middleware.py`, `Capp/models.py` (`CompanyOwnerProfile`), `templates/Capp/base.html`, `Sapp/app/company.py` (`Company`, forms), `templates/Sapp/company/*`, `Aapp/app/employee.py` (create path), `Capp/import_views.py`, `Capp/importer.py`, `revolution/app/plan_gate.py`.

## Work packages
| ID | Package | Deliverable |
|---|---|---|
| **F1** | Company mode | `Company.management_mode` (`DIRECT`/`ASSOCIATE`, default `ASSOCIATE`) in `Sapp/app/company.py`. Field on Sapp create/alter company forms and templates (superadmin). Associate-created companies are always `ASSOCIATE`. Mode-change guard per D5. |
| **F2** | Employee limit on the licence | Add `License.max_employees` (positive int, null = unlimited) in `Sapp/app/license.py`, shown and required-or-blank on the Sapp **issue/edit licence** form (this is where the owner defines it). Leave `max_users` alone. Management command `backfill_license_max_employees`: sets existing licences from the plan default (copper 150, else null), dry-run first. `plan_limits.py` already reads `max_employees` when present: keep every signature and the `PlanLimitExceeded` message. Hooks: Aapp employee create path (one-line `check_can_add`), reactivation path, and `Capp/importer.py`/`import_views.py` (rows beyond `remaining()` become "Plan limit reached" in the preview and are skipped). Show usage "132 / 150" (or "132 / unlimited") on the Capp dashboard. |
| **F3** | Roles | `CompanyOperator` model (`user`, `company`, one boolean per permission group, `is_active`, `created_by`). Middleware sets `request.capp_mode / capp_role / capp_perms`. Real `has_perm` implements the section 4 matrix exactly; owner `can_view_*` flags still restrict owners. Capp login accepts owner or operator. Owner screens: list/add/edit/suspend operator, reset password (`operators.manage`). Associate-side suspend of operator (Sapp or Aapp list, minimal). |
| **F4** | Menu | Context processor `capp_nav`: merges `NAV` from `Capp/foundation/nav.py` (convert today's menu: dashboard, employees, attendance, wages, masters, billing, import) + `Capp.entry.nav` + `Capp.direct.nav`, filtered by `perm` and `modes`. Refactor `base.html` to render from it. Header shows mode badge (Direct / Under associate) and the plan. |
| **F5** | Audit | `CappAuditLog` (`company`, `user`, `role`, `action`, `model`, `object_id`, `detail`, `at`, `ip`). Real `log_action`. Owner read-only screen with filters (operator, date, action). Add `log_action` to existing masters/billing/import writes. |
| **F6** | Integration | Merge tracks at C2/C3, run `makemigrations` once per checkpoint, resolve conflicts, write matrix tests, regression, final docs. |

## Frozen API you must keep
`get_mode`, `has_perm(request, perm)`, `capp_perm(*perms)`, `PERMISSIONS`; `employee_limit`, `active_employee_count`, `remaining`, `check_can_add`, `PlanLimitExceeded`; `log_action(request, action, obj, detail="")`; request attributes in master plan section 5.
You may **add** permissions only through the master plan (tell the owner).

## Must-haves
- Existing companies keep working unchanged after migration (all `ASSOCIATE`, copper limit applies; companies already over 150 keep their employees).
- Plan-limit message names the plan, the limit, the count, and says "Upgrade the plan to add more".
- Suspended operator or inactive owner profile cannot log in or hit any view.
- `capp_perm` denial redirects with a message for pages; returns 403 JSON/empty for POST-only endpoints.
- Matrix test covers every permission × (DIRECT/ASSOCIATE) × (owner/operator, flag on/off) = expected allow/deny.
- No behaviour change to Aapp beyond the one-line hook.

## Acceptance tests (write them)
1. Matrix: all cells in master plan section 4.
2. Limit from licence: licence `max_employees=3` beats plan default; no licence → copper 150 / others unlimited; at 149 active, adding 1 passes; adding 2 fails; relieving then re-adding respects the count; import with 10 rows and 3 remaining imports 3 and flags 7.
3. Mode change blocked while a batch is PROCESSED or APPROVED-not-PAID.
4. Operator suspended → login fails; owner can re-enable.
5. Menu: operator without `attendance` flag sees no attendance entry; DIRECT-only entries absent in ASSOCIATE.
6. Existing 38 tests green.

## Deliverable
Files + handoff report (`01_COMMON_RULES.md` section 8). Migrations are yours: one migration per checkpoint, `git add -f`.
