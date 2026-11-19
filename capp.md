# Capp Functionalization Plan

## Purpose

Turn `Capp` from a read-only company-owner portal into a functional HR and manpower-contractor portal. The target owner is a contractor who supplies manpower to departments and needs to manage company records, workers, attendance, payroll, statutory files, and department bills without an associate handling day-to-day work.

Sapp registers the company and provides the owner with login credentials. Capp must operate only on the company attached to the authenticated `CompanyOwnerProfile`.

## Scope and constraints

1. **Company:** update statutory and bank details only. Company creation stays in Sapp.
2. **Branches:** add, update, disable. No hard delete.
3. **Departments:** add, update, disable. No hard delete.
4. **Designations:** add, update, disable. No hard delete.
5. **Employees:** individual and bulk addition, update, disable, and retire. Preserve payroll/history records.
6. **Attendance:** add and update attendance.
7. **Payroll processing:** process owner-company payroll and provide relevant results/reports.
8. **Department billing:** the owner is a manpower contractor who presents bills to departments where they provide workers. Create, review, update, finalize, and produce a department-ready bill, based on the appropriate work/attendance and rate data.
9. **EPF/ESI:** generate and download EPF and ESI challan/return files for the owner’s company and selected period.
10. **Bank outputs:** generate a bank payment file and bank letter from the intended processed payroll batch.

Billing does **not** mean Capp subscription or plan billing. Do not implement subscription invoicing as this task’s Billing feature.

## Architecture and reuse

- Keep implementation changes within `Capp` by default. Reuse Aapp models, forms, validation, calculations, generators, and services where appropriate; do not duplicate payroll or statutory rules.
- Aapp often scopes data using a selected-company session. Capp must instead derive company scope from the authenticated owner profile on every query and write. Never rely on an Aapp session company for Capp authorization.
- Preserve Capp’s established owner context (`CompanyOwnerMiddleware`, `owner_profile`, `owned_company`), decorators, registry, and generated-form conventions where they fit.
- Existing `CompanyOwnerProfile` flags mostly grant section-level view access. Extend permissions to cover actions (view/create/update/disable/process/download/finalize) as needed. Check permissions in views as well as navigation; hidden links are not authorization.
- Use POST for state-changing operations. Keep disabled/retired records and finalized bills rather than deleting history.
- `Capp` and `Cxapp` are distinct portals and ownership models. This work targets Capp only.

## Phased task plan

### Phase 0 — Discovery and safety boundaries

- Map existing Capp read-only URLs, views, templates, registry entries, and owner access flags.
- Trace Sapp company registration and owner-credential/profile provisioning.
- Map each requested workflow to Aapp models and existing logic, including contractor/payment models for department billing.
- Identify the company foreign-key lookup and related-object scoping needed for every create/update form.
- Agree action-level permission semantics and identify migrations required before implementation.

**Completion:** a verified Capp-to-Aapp reuse map, ownership boundary, and list of required schema/permission changes.

### Phase 1 — Owner provisioning, permissions, and company details

- Ensure Sapp can provision credentials and associate the active Capp owner profile with the registered company.
- Add Capp edit workflows for company statutory and bank details only.
- Extend owner permissions to the actions required by the roadmap; set sensible permissions for the primary owner and future restricted users.
- Enforce active-account checks and owner-company scoping on every route and object lookup.

**Completion:** provisioned owner signs in, sees their company only, edits permitted details, and cannot access unauthorized actions or another company’s records.

### Phase 2 — Branches, departments, and designations

- Implement scoped list/create/update/disable flows.
- Reuse Aapp models and validation; scope related dropdowns to the owner’s company.
- Prevent hard deletion and avoid assigning disabled masters to new records where appropriate.

**Completion:** all three master types have the requested lifecycle with history retained.

### Phase 3 — Employee management

- Implement individual employee create/update, disable, and retire workflows.
- Add bulk import using established Aapp import conventions and provide useful row-level validation results.
- Scope all employee and related-record lookups to the owner’s company.

**Completion:** individual and bulk employee workflows preserve history and reject cross-company references.

### Phase 4 — Attendance

- Implement add/update attendance for employees belonging to the owner’s company and the selected period.
- Reuse Aapp attendance models, rules, and validation; assess bulk attendance only if the existing workflow can be safely reused.

**Completion:** attendance can be entered and corrected and is available to payroll processing.

### Phase 5 — Payroll processing

- Trace Aapp payroll batch prerequisites and processing lifecycle before exposing it in Capp.
- Implement owner-scoped review, processing, and result access, with separate permissions for viewing, processing, and reprocessing.
- Reuse shared calculation logic; do not fork statutory or salary calculations into Capp.

**Completion:** owner can process payroll for their company and inspect the resulting payroll records and reports.

### Phase 6 — Department billing (manpower contractor bills)

- Inspect existing contractor, contractor-worker, contractor-payment, attendance, and wage/rate models before designing any new schema.
- Define bill inputs: department, service/billing period, workers or work quantities, contract rates, adjustments, and supporting records as applicable.
- Implement draft creation and review/update, finalization, and department-ready output. Preserve finalized bill snapshots/history.
- Enforce owner-company scoping and appropriate action permissions throughout.

**Completion:** owner can prepare and finalize a bill for a department they supply, using the agreed source data and rates.

### Phase 7 — EPF and ESI files

- Identify the existing Aapp EPF/ESI generators and their payroll prerequisites and output formats.
- Add Capp-scoped period selection and downloads; validate prerequisites and restrict data to the owner’s company.

**Completion:** owner can generate the correct EPF and ESI outputs for an eligible company payroll period.

### Phase 8 — Bank file and bank letter

- Reuse Aapp bank batch/export and document-generation logic.
- Allow selection of the intended processed payroll batch, then generate the bank file and bank letter with company-scoped employee bank details.

**Completion:** both outputs correspond to the selected batch and the owner’s company.

### Phase 9 — End-to-end permission and workflow review

- Review every Capp route for authentication, active owner status, action permission, company-scoped queries, and company-scoped related-object validation.
- Confirm state changes use POST, no forbidden hard-delete actions exist, and disabled/retired/finalized history is retained.
- Review owner provisioning in Sapp and Capp navigation against actual server-side permissions.

**Completion:** the workflow from Sapp provisioning through masters, employees, attendance, payroll, department billing, statutory outputs, and bank outputs follows the agreed access boundaries.

## Collaboration notes

- Another developer is working in the same project. Before editing, inspect `git status` and the latest changes; do not overwrite or revert another person’s work.
- Keep changes limited to Capp-owned files when possible. Coordinate before modifying shared Aapp, Sapp, project settings, migrations, or shared templates.
- If shared code must change, identify the dependency and intended change before editing so concurrent work can be reconciled.
- Update this document as phases are completed or decisions change; record current phase, decisions, and unresolved questions here.

## Current status

- Roadmap agreed; implementation has not started as part of this planning document.
- Billing clarified as department-facing manpower contractor billing, not subscription billing.
- Existing repository has uncommitted changes in `Cxapp/middleware.py`, `revolution/settings.py`, `revolution/urls.py`, `templates/Sapp/company/alter_company.html`, `templates/Sapp/company/create_company.html`, and new `revolution/views.py`. These were present before this document request; preserve them.
