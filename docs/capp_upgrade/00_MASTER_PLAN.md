# CAPP UPGRADE — MASTER PLAN
Branch: `capp_upgrades`  |  Repo: iamatulkaushik/revolution.associates  |  Read this first, every AI.

## 1. Goal
Capp (the company-owner portal, `capp.<domain>`) must support two kinds of company.

| | DIRECT company | UNDER-ASSOCIATE company |
|---|---|---|
| Who runs payroll | Company itself | The associate (Aapp) |
| Statutory setup (EPF/ESIC/LWF/PT) | Company edits it | Associate only |
| Bank details | Company edits | Associate only |
| Challans, returns | Company handles and downloads | Company downloads (associate files them) |
| Employees, attendance, loans, advances | Company enters | Owner and operators **help enter** data |
| Payroll batch process / finalize | Company | Associate only |
| Salary sheet, slips, abstracts | Download any time after finalize | Download after batch is finalized |
| Employee limit | Set by Sapp on the licence | Set by Sapp on the licence |

Mode is a property of the company, set by Sapp superadmin: `Company.management_mode` = `DIRECT` | `ASSOCIATE` (default `ASSOCIATE`; all existing companies stay ASSOCIATE).

## 2. Decisions
### Decided by the owner
- **A.** Direct mode is a **separate new build inside Capp**. Cxapp is not reused and not touched.
- **B.** Employee limit is **set when the licence is issued** (stored on the company's licence). `Company.plan` only supplies the default: copper = 150. Other plans have no default cap.
- **C.** Over the limit: **only adding is blocked**. Existing employees stay. Reactivating a relieved employee counts as adding.

### Assumed defaults (owner may change before Day 0 freeze; each is cheap to change now, costly later)
| ID | Question | Default used in all task files |
|---|---|---|
| D1 | Where the limit lives | **Decided:** on the licence at issue time. New field `License.max_employees` (None = unlimited). `License.max_users` (login-user seats, defaults 5/10) is left untouched. No licence: plan default (copper 150, else unlimited) |
| D2 | Who finalizes a batch in ASSOCIATE mode | Associate only |
| D3 | Who are "operators" | New Capp `CompanyOperator`, created by the owner. Separate from Aapp `SubUser`. Associate can suspend them |
| D4 | Challans / returns in ASSOCIATE mode | **Decided:** company may download them (read-only; the associate generates and files). Same gate as salary sheet: batch `APPROVED` or `PAID` |
| D5 | Changing a company's mode | Sapp superadmin only; blocked while any batch is PROCESSED or APPROVED-not-PAID |
| D6 | What counts toward the limit | Employees with `is_working=True` |
| D7 | Entry lock | In ASSOCIATE mode attendance/loan entry for a month is locked once its batch is PROCESSED. Associate unlocks. In DIRECT mode owner may reopen while batch is DRAFT/PROCESSED |
| D8 | Relieve (exit) employee | DIRECT: allowed. ASSOCIATE: associate only |

## 3. Architecture principles
1. **Reuse, never copy.** Capp reads and writes the existing Aapp models (`employee`, `salary_slip`, `salary_processing`, `designation`, …). No parallel model trees. New tables live only in Capp.
2. **Aapp stays behaviour-identical.** Allowed Aapp edits: (a) one-line plan-limit hook in the employee create path (AI-1), (b) extraction of view-bound logic into pure functions under `Aapp/app/services/` with a golden test proving identical output (AI-2, approval at C1).
3. **Tenant safety.** Every query is scoped to `request.owned_company`. Another company's record is a 404, never a 403.
4. **Fail-closed statutory gates.** No registration on file means no deduction and no challan. `get_company_gates()` is the single source.
5. **Mode and role are checked in one place**: `Capp/access.py`. Views never compare mode strings themselves.

## 4. Permission matrix (AI-1 implements; everyone codes against names only)
`O`=owner, `Op`=operator (flag-controlled by owner). `—` = never.

| Permission | DIRECT O | DIRECT Op | ASSOC O | ASSOC Op |
|---|---|---|---|---|
| employees.view | ✔ | ✔ | ✔ | ✔ |
| employees.add / edit | ✔ | flag | ✔ | flag |
| employees.relieve | ✔ | — | — | — |
| attendance.view / edit | ✔ | flag | ✔ | flag |
| loans.view / edit | ✔ | flag | ✔ | flag |
| payroll.process / finalize | ✔ | — | — | — |
| payroll.download | ✔ | flag | ✔ | flag |
| statutory.edit | ✔ | — | — | — |
| challan.download | ✔ | flag | ✔ | flag |
| bank.edit | ✔ | — | — | — |
| masters.edit | ✔ | flag | ✔ | — |
| billing.manage | ✔ | flag | ✔ | — |
| operators.manage | ✔ | — | ✔ | — |

Existing `can_view_*` flags on `CompanyOwnerProfile` keep working for owners (they further restrict).
`payroll.download` additionally requires batch status `APPROVED` or `PAID` in ASSOCIATE mode. In DIRECT mode the same gate applies (one rule, one code path).

## 5. Frozen contracts (do not change signatures; ask first)
Phase 0 already contains working stubs — code against them today.

| Contract | File | Owner |
|---|---|---|
| `get_mode`, `has_perm`, `@capp_perm(*perms)`, `PERMISSIONS` | `Capp/access.py` | AI-1 (internals), all (callers) |
| `employee_limit`, `active_employee_count`, `remaining`, `check_can_add`, `PlanLimitExceeded` | `revolution/app/plan_limits.py` | AI-1 |
| Request attributes: `request.owned_company`, `request.capp_mode`, `request.capp_role` (`OWNER`/`OPERATOR`), `request.capp_perms` (set) | middleware | AI-1 |
| Menu: each track exposes `NAV = [{"label","url_name","perm","modes"}]` in its `nav.py`; AI-1 renders it | `Capp/entry/nav.py`, `Capp/direct/nav.py` | tracks fill, AI-1 renders |
| URLs: `Capp/entry/urls.py` and `Capp/direct/urls.py` are already included by `Capp/urls.py`. **Nobody else edits `Capp/urls.py`** | | |
| URL prefixes / names: ENTRY `entry/`, `downloads/` → `capp_ent_*`. DIRECT `direct/` → `capp_dir_*` | | |
| DB tables: ENTRY `ca_ent_*`, DIRECT `ca_dir_*`, FOUNDATION `ca_*` | | |
| Audit: `Capp.audit.log_action(request, action, obj, detail="")` | `Capp/audit.py` | AI-1 (stub no-op until delivered) |
| Models: tracks put models in their own `models.py`; `Capp/models.py` already imports both | | |

## 6. Tracks and file ownership
| Track | File | Branch | Owns (may edit) |
|---|---|---|---|
| **AI-1 Foundation & Governance** | `02_AI1_FOUNDATION.md` | `capp_upgrades/ai1-foundation` | `Capp/access.py`, `Capp/audit.py`, `Capp/middleware.py`, `Capp/models.py`, `Capp/context_processors.py`, `templates/Capp/base.html`, `Capp/foundation/*`, Sapp company and licence screens, `Sapp/app/license.py`, `revolution/app/plan_limits.py`, all migrations |
| **AI-2 Direct company engine** | `03_AI2_DIRECT_ENGINE.md` | `capp_upgrades/ai2-direct` | `Capp/direct/*`, `templates/Capp/direct/*`, `Aapp/app/services/*` (new files only) |
| **AI-3 Entry & downloads** | `04_AI3_ENTRY_DOWNLOADS.md` | `capp_upgrades/ai3-entry` | `Capp/entry/*`, `templates/Capp/entry/*` |

Everything else is **read-only for all tracks**. A needed change in someone else's file is requested in the handoff report, not made.

Workload split (balanced by surface area, not by title): AI-1 = 6 work packages, 4 touch shared code. AI-2 = 6 packages, heaviest in Aapp reading. AI-3 = 6 packages, heaviest in UI, validation and generator wrappers. **All file downloads (salary sheet, slips, abstract, challan files, statutory reports) are AI-3's single code path for both modes.**

## 7. Schedule (relative days; start Day 0 when you say go)
| Day | AI-1 | AI-2 | AI-3 | You |
|---|---|---|---|---|
| 0 | Freeze contracts (this doc) | read, inventory | read, inventory | answer D1–D8, create 3 sub-branches |
| 1 | F1 mode field, F2 licence employee limit | **C1:** `INVENTORY.md` of reusable Aapp functions | employees CRUD | **C1 review (30 min)** |
| 2 | F3 operators + real `has_perm` | batch lifecycle | attendance entry | |
| 3 | F4 nav refactor, F5 audit | statutory setup, challans | loans/advances entry | **C2: merge AI-1, smoke test (1 h)** |
| 4 | support merges | month-end checklist, reports | downloads + operator dashboard | |
| 5 | F6 integration, matrix tests | hardening | hardening, ATT import | **C3: merge all, UAT (2 h)** |
| 6 | regression, docs | buffer | buffer | release decision |

Your real bottleneck is review time (about 3.5 h total), not AI speed. Do not skip C1: it is where a wrong Aapp assumption is cheapest to catch.

## 8. Risks
| Risk | Mitigation |
|---|---|
| Three AIs edit one file | Ownership table above; stub seams already in place |
| Migration number clash | Only AI-1 runs `makemigrations`. Tracks deliver models; AI-1 generates one migration per checkpoint |
| Aapp logic is view-bound, not reusable | C1 inventory; extraction with golden tests |
| Licence limit missing or wrong | Limit is a licence field editable in Sapp; backfill command covers existing licences; no code change needed |
| Direct mode rebuilds half of Aapp | Principle 1 plus C1 inventory; stretch items (FNF) are optional |
| Three vocabularies (`Company.plan` copper..platinum, `License.license_type` trial..enterprise, `CxPlan`) | Capp reads only `License.max_employees` and `Company.plan`; never `CxPlan`, never `license_type` |

## 9. Definition of done
- `python manage.py test Capp` green (38 tests exist today; none may be deleted).
- `manage.py check` clean; `makemigrations --check` clean; `migrate --plan` shows only expected steps.
- Mode × role matrix test passes for every cell in section 4.
- UAT script in `05_INTEGRATION_AND_UAT.md` passes with one DIRECT and one ASSOCIATE company.
- No Aapp behaviour change (golden tests).
