# INVENTORY — AI-2 D0 (Checkpoint C1)
Read-only study of Aapp at `main` @ `09d35b0`. **No code extracted yet. Awaiting owner approval.**
Legend: **Pure** = takes model/args, no `request`. **Req** = reads `request` (session company, messages, redirect). Plan: **CALL** = use as is; **EXTRACT** = move logic to `Aapp/app/services/` (new file), old view calls it, golden test; **NEW** = nothing in Aapp, build in `Capp/direct/`.

## 1. The one finding that shapes everything
Every Aapp view resolves the company with `request.session['selected_company_id']` (`_get_selected_company` / per-module `_company`). Capp must use `request.owned_company`. So **no Aapp view can be called from Capp as is**. Pure helpers can be called directly; view-bound logic must be extracted (Principle 2b). I will **not** set the Aapp session key from Capp (it would leak Aapp state across portals).

## 2. Reusable as is (pure, CALL)
| File | Name | Signature | Pure | Req | Plan |
|---|---|---|---|---|---|
| `statutory_gates.py` | `get_company_gates` | `(company) -> dict` | yes | no | CALL (single source) |
| | `labour_required`, `lwf_allowed`, `shop_act_required` | `(gates, feature_name='')` | yes | no | CALL |
| `salary_processing.py` | `calculate_employee_salary` | `(employee_obj, desig, month, year, company=None) -> dict` | yes | no | CALL |
| `salary_pdf.py` | `salary_slip_pdf` | `(salary_slip_obj) -> bytes` | yes | no | CALL |
| | `salary_sheet_pdf` | `(company, month, year) -> bytes` | yes | no | CALL (AI-3 owns the download screens) |
| | `salary_abstract_pdf` | `(company, month, year) -> bytes` | yes | no | CALL (AI-3) |
| `pt_schedule.py` | `pt_schedule_pdf` | `(company, month, year) -> bytes` | yes | no | CALL (D3 PT) |
| `statutory/wages_act.py` | `grand_total_pdf`, `wages_register_pdf`, `form_x_wages_register_pdf` | `(company, slips, month, year) -> bytes` | yes | no | CALL (D5) |
| | `wages_slip_pdf` | `(company, slip) -> bytes` | yes | no | CALL (D5) |
| `fnf_settlement.py` | `FnFSettlement.compute()` | method | yes | no | CALL (D6) |
| `fnf_pdf.py` | `fnf_settlement_pdf(settlement)`, `fnf_certificate_pdf(settlement, cert_type)` | | yes | no | CALL (D6) |
| `ecr_generator.py` | `_member_lines(company, month, year)` | `-> (lines, skipped)` | yes | no | CALL (private name; see risks) |
| | `ecr_member_figures(...)` | | yes | no | CALL |
| `epf_esi.py` | `_compute_epf_ecr_totals(company, month, year)` | `-> dict` | yes | no | CALL (private name) |
| `esi_generator.py` | `_esi_slips(company, month, year)` | | yes | no | CALL |
| `pdf_engine.py` | `build_pdf`, `doc_styles`, `kv_table`, `INR`, `section_divider` | | yes | no | CALL |
| `batch_job.py` | `BatchJob` model; `tasks.queue_bulk_*` | `(company_id, month, year, requested_by_id)` | yes | no | CALL for bulk PDFs |

## 3. Models I will read/write (no copies)
`salary_processing` (batch; `status` DRAFT/PROCESSED/APPROVED/PAID; unique company+month+year), `salary_slip`, `employee`, `designation`, `company_statury` (table `sa_company_statury`), `EpfMonthlyEcr`, `EsiContributionReturn`, `LabourWelfareFundContribution`, `FnFSettlement`, `BatchJob`.

## 4. View-bound logic to EXTRACT (needs your approval)
| File | View today | Logic to pull out | Proposed service function | Golden test |
|---|---|---|---|---|
| `salary_processing.py` | `create_salary_batch` | get-or-create batch | `services/payroll_batch.py::create_batch(company, month, year, user)` | same fixture, same row |
| | `process_salary_batch` (POST body) | delete slips, loop employees, totals, status PROCESSED | `process_batch(batch, company, username) -> (processed, skipped, error_rows)` | slips and totals value-identical |
| | `approve_salary_batch` | PROCESSED→APPROVED | `approve_batch(batch, username)` | status and timestamps |
| | `delete_salary_batch` | delete guard | `delete_batch(batch)` | |
| `epf_esi.py` | `add_epf_ecr` | duplicate check + create ECR | `services/statutory_returns.py::create_epf_ecr(company, month, year, user)` | |
| `ecr_generator.py` | `download_ecr_text`, `download_epf_challan` | text build, PDF build | `build_ecr_text(company, ecr)`, `build_epf_challan_pdf(company, ecr)` | byte-identical |
| `esi_generator.py` | `download_esi_monthly_challan`, `_upload` | PDF and xlsx build | `build_esi_challan_pdf(company, month, year)`, `build_esi_upload_xlsx(...)` | byte-identical |
| `lwf_generator.py` | `download_lwf_challan` | PDF build | `build_lwf_challan_pdf(company, rec)` | byte-identical |
| `salary_processing.py` | `export_bank_advice` | file build | skip: Capp already has `Capp/bank_export.py` / `bank_views.py` | n/a |
| `fnf_settlement.py` | list/create/finalize | create+compute, finalize | `services/fnf.py::create_settlement`, `finalize_settlement` (D6 only) | |

Other generators (phase2–5, pow) follow the same shape (`@login_required` + session company + build PDF); extract only the ones D5 exposes, after you pick them (question 4).

## 5. Gaps and risks found (need your decision)
1. **`PAID` is never set anywhere in Aapp.** The status exists, nothing moves a batch to it. D2 "mark paid" is NEW code in `Capp/direct/`. ASSOCIATE-mode download (APPROVED or PAID) is unaffected.
2. **`process_salary_batch` only blocks APPROVED.** A PAID batch could be reprocessed (slips deleted and rebuilt). `delete_salary_batch` likewise blocks only APPROVED. Aapp stays untouched (Principle 2); my Capp wrapper will block PAID and APPROVED. Say if you want Aapp fixed separately.
3. **No reopen in Aapp.** D2 reopen (PROCESSED→DRAFT) is NEW. Master plan D7 says reopen DRAFT/PROCESSED only, so APPROVED stays irreversible.
4. **Gate not applied in generators.** `_member_lines` filters on UAN, `_esi_slips` on ESIC number; neither checks `get_company_gates()`. D3 must check the gate in Capp before offering or generating (fail-closed). LWF already checks.
5. **`require_feature` reads `request.selected_company`** (plan feature gating), which Capp never sets. Capp must not depend on it. D5 reports gated by Aapp plan features (`min_wages`, `bonus_act`, `payment_of_wages`, `overtime`) need `has_feature(company, feature)` called directly. Confirm that plan-feature gating should apply in Capp.
6. **Private helpers** (`_member_lines`, `_compute_epf_ecr_totals`, `_esi_slips`) are underscore-named. Calling them is safe today but could be renamed. Extraction into services removes the risk.
7. **Statutory model:** `company_statury` has `unique_together` over 7 fields; `epfo` max 15, `esic` max 17 characters. D1 validation: EPFO 15, ESIC 17 characters, PT/GST/shop act ≤15. There may be several rows per company; `get_company_gates` uses `.first()`. D1 will edit that same first row (create one if none).
8. **Gate source for income tax** is `company.tan`, a Company field, not `company_statury`. D1 edits `company_statury` only; TAN stays in the Sapp company master.
9. **ESIC rounding:** challan ceil per slip lives in `esi_generator.py` and stays there (challan file only), consistent with plan section 2.
10. **Environment:** Django is not installed in this session, so I cannot run tests here. Golden tests and the 38 contract tests must be run by you locally until that changes.

## 6. Questions for you (C1)
1. Approve the extraction list in section 4? (Reply "approve all" or strike items.)
2. Reprocess/delete guard (risk 2): Capp-side block only, or also fix Aapp?
3. Reopen from APPROVED: keep irreversible (default) or allow back to PROCESSED?
4. D5 reports: which of phase2–5 / pow / wages-act reports should DIRECT companies see? Default: wages-act reports (grand total, wages register, wages slip, Form X), fines, deductions and OT registers, PT schedule.
5. Plan-feature gating in Capp (risk 5): apply Aapp plan features, or ignore them for DIRECT companies?

## 7. C1 decisions (owner, 22-11-2026)
1. **Extraction list (section 4): approved.** Mark-paid, reopen and every new DIRECT screen are new Capp code (the company runs payroll itself).
2. **Approved batch is locked.** Reprocess and delete are blocked in Capp once a batch is APPROVED (or PAID). Only a Sapp superadmin can move a batch back from APPROVED, and must give a reason.
   - **Needs AI-1 / owner action:** Sapp screens are AI-1's files. AI-2 will not edit Sapp. Request for AI-1: a superadmin-only Sapp screen "Change batch status" (batch, new status, mandatory reason), writing the reason, old and new status, user and time to an audit row. AI-2 only reads `status`, so no contract change.
   - Capp reopen from APPROVED does not exist (irreversible in Capp). Reopen PROCESSED to DRAFT stays in Capp.
3. **D5 report list:** default list approved (wages-act reports, fines, deductions, OT registers, PT schedule).
4. **Gates:** statutory registration decides deduction and availability. EPF number on file = EPF deduction and ECR; no number = none. Same for ESIC, Labour (LWF needs Shop Act too), Shop Act, PT, TAN. This is the existing `get_company_gates()` rule. D3 applies it before offering any file. Aapp plan-feature gating (`require_feature`) is **not** applied in Capp.
5. **Final check before finalize:** the D4 month-end checklist is the last step of the batch flow and is shown on the Finalize confirmation page, so the owner can review attendance, loans, gates, batch totals and challans before approving.

## 8. C1 answers, round 2 (owner, 22-11-2026)
- **D5 reports:** default list **plus** any other Aapp return the company needs per its statutory registrations (shown only when the registration is on file, via `get_company_gates()`). AI-2 will list the extra returns in the D5 handoff for confirmation before building them.
- **Final check:** the checklist is shown on the Finalize confirmation page, before approval.
- **Sapp "change approved batch status" screen:** AI-1 builds it. AI-2 stays out of Sapp.
- **Plan gating:** statutory gates only; no Aapp `require_feature` in Capp.
