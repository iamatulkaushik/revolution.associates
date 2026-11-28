# TRACK AI-2 — DIRECT COMPANY ENGINE
Branch `capp_upgrades/ai2-direct`. Read `00_MASTER_PLAN.md` and `01_COMMON_RULES.md` first.

## Role
Give a DIRECT company everything the associate normally does for it: statutory setup, payroll batch lifecycle, challans and returns, month-end control, FNF. All of it appears only in DIRECT mode, behind `@capp_perm`.

## Capabilities you need
Strong reading of a large legacy Django codebase (Aapp ≈ 18k lines), safe refactoring with golden tests, Indian statutory knowledge (EPF/ESIC/LWF/PT, ECR, Wage Code), PDF/Excel generation via `pdf_engine`, careful permission handling.

## Read first
`Aapp/app/salary_processing.py` (batch status `DRAFT → PROCESSED → APPROVED → PAID`), `Aapp/app/statutory_gates.py`, `Aapp/app/statutory/`, `Aapp/app/ecr_generator.py`, `esi_generator.py`, `lwf_generator.py`, `phase2..5_generator.py`, `pow_generator.py`, `fnf_settlement.py`, `Aapp/app/pdf_views.py`, `Aapp/app/batch_job*.py`, `Sapp/app/company.py` (`company_statury`), `Capp/views.py`, `Capp/bank_views.py`.

## Work packages
| ID | Package | Deliverable |
|---|---|---|
| **D0** | **Inventory (checkpoint C1, before any coding)** | `docs/capp_upgrade/INVENTORY.md`: table of every Aapp function you will reuse: file, name, signature, pure (yes/no), request-bound (yes/no), plan to call or extract. Owner approves before you extract anything. |
| **D1** | Statutory setup | Screens to edit `company_statury`: EPFO, ESIC, LWF, PT, GST/other registrations, with format validation and clear help text. `statutory.edit`. Saving must keep `get_company_gates()` correct (fail-closed). Audit every change. |
| **D2** | Payroll batch lifecycle | Screens: create batch for a month, process, review exceptions, **finalize (approve)**, mark paid, reopen DRAFT/PROCESSED. Wrap Aapp functions. Guards: attendance complete, loans applied, no unlimited reprocess after APPROVED. Permissions `payroll.process`, `payroll.finalize`. |
| **D3** | Challans and returns | One page per month listing every generator the company is entitled to (gated by registrations): ECR, ESI contribution file, LWF, PT, forms already in Aapp. Download buttons call the existing generators. ESIC rounds up **in the challan file only**. `challan.download`. |
| **D4** | Month-end checklist | One page: attendance complete? loans/advances applied? batch status? challans generated? bank file generated? due dates. Links to the right screen. Read-only logic, no new data. |
| **D5** | Direct reports | Statutory reports PDFs that Aapp already produces, exposed for the company with the same permission and tenant scoping. (Salary sheet, slips, abstracts are **AI-3's downloads**, link to them, do not rebuild.) |
| **D6** | FNF / relieving (stretch) | Relieve an employee and run full and final using `fnf_settlement.py`. Only after D1–D5 are accepted. |

## Aapp extraction rule
You may add **new files only** under `Aapp/app/services/` and change the original Aapp view to call them in the same commit. Each extraction needs a **golden test**: run old path and new path on the same fixture, assert byte-identical or value-identical output. No other Aapp edits.

## Must-haves
- Everything DIRECT-only: `capp_perm` plus a mode guard through `Capp/access.py`. In ASSOCIATE mode these URLs return 302 with a message.
- Tenant isolation test for every endpoint.
- Finalize is irreversible except by the documented reopen rule; confirmation page before it.
- Every state change calls `log_action`.
- Nothing is generated for a statutory scheme the company is not registered for.
- Long downloads (bulk) use `BatchJob`.

## Acceptance tests
1. Full month: fixture company → batch create → process → finalize → paid; status transitions and guards.
2. Challan files equal Aapp's output for the same company (golden).
3. Unregistered ESIC: no ESI file offered, no ESI deducted (fail-closed).
4. ASSOCIATE company hits every `direct/` URL → blocked.
5. Operator in DIRECT mode cannot process/finalize/edit statutory.
6. Other-tenant 404 on every detail URL.

## Deliverable
Models (if any, with prefix `ca_dir_`) in `Capp/direct/models.py`; URLs in `Capp/direct/urls.py` (`capp_dir_*`); menu in `Capp/direct/nav.py`; templates in `templates/Capp/direct/`; tests `Capp/tests_direct_*.py`; handoff report.
