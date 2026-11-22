# COMMON RULES — every AI follows these, no exceptions

## 0. Before you write code
1. Read `00_MASTER_PLAN.md`, then your own track file.
2. Scan existing models, views, urls for what you touch. Verify URL routing from `urls.py` imports. Active views are in `Aapp/app/<module>.py`, **not** `Aapp/views.py` (dead duplicates).
3. Duplicate URL-name check: `grep -oP "name='\K[^']+" Capp/urls.py Capp/*/urls.py | sort | uniq -d` must print nothing except `capp_login`, a known intentional alias (root `''` and `login/` share one name).
4. Work only on your sub-branch. Never push to `capp_upgrades` directly.

## 1. Architecture rules
- Multi-tenant: every queryset filtered by `request.owned_company`. Other company's object → `get_object_or_404` → 404.
- No cross-app model copies. Reuse Aapp models. New tables only in Capp, with your table prefix.
- Fail-closed statutory gates via `get_company_gates()`. No registration = no deduction, no challan, no menu item.
- EPF wage base is Basic + DA (Wage Code), not total allowances.
- Signal receivers only at module level, never nested in classes or forms.
- Seed data through explicit management commands. No `post_migrate` seeding.
- Adding an FK to a table with data: nullable FK → backfill → NOT NULL (three steps).
- Table that already exists outside Django history: `SeparateDatabaseAndState`.
- No custom cryptography. AES-256-GCM / Fernet only. Exact-match lookups on encrypted fields use an HMAC-SHA256 hash column.
- Mode and permission checks only through `Capp/access.py`. Never `if company.management_mode == ...` in views.

## 2. Money, dates, rounding
- `Decimal` only. Never `float`.
- Indian currency (₹), Indian grouping in PDFs via the engine's `INR()`.
- Dates shown `dd-mm-yyyy`.
- Bank payout: round **up** to whole rupee, in one place (`rupee_up`). ESIC rounds up in challan files only. Bills keep full precision; round the invoice total once, half-up.
- Overtime never enters ESI wages.

## 3. UI
- Reuse `templates/Capp/masters/list.html`, `form.html`, `confirm_delete.html` and helpers in `Capp/masters.py` (`_list`, `_edit`, `_delete`). Do not invent a second look.
- Menu entries go in your `nav.py`. Do not edit `base.html` (AI-1 only).
- Every form validates server-side; show field errors. State-changing actions are POST + CSRF only.
- Messages: short, plain. Say what to do next.

## 4. PDF engine gotchas
- Use `Aapp/app/pdf_engine.py` (`build_pdf`, `doc_styles`, `table_style`, `INR`, `amount_in_words`).
- Blank second page was a double letterhead draw after `showPage()`; already fixed. Do not reintroduce.
- Aapp and Cxapp salary PDF generators differ; do not merge them.
- Bulk PDF/email work goes through the existing `BatchJob` (django-q2) path.

## 5. Tests and checks (merge gate)
Run, in this order, before every handoff:
```
python -m py_compile $(git ls-files '*.py')
python manage.py check
python manage.py makemigrations --check --dry-run      # tracks: expect "new models" only if you added any
python manage.py test Capp
```
- Existing 38 tests must still pass. Never delete or weaken a test to go green.
- New code needs tests: happy path, permission denied, other-tenant 404, validation error, and (where relevant) plan-limit and mode differences.
- Tests build their own data (see `Capp/tests_masters.py::make_company`). No dependence on a real database or real employee data.

## 6. Migrations
- **Only AI-1 creates migrations.** Tracks ship models and say so in the handoff. Never hand-edit a generated migration.
- Migrations folders are gitignored; use `git add -f`.

## 7. Delivery format
- Individual files, directory structure preserved, plus one zip of changed files. Copy files flat to `/mnt/user-data/outputs/` as well.
- One commit per work package. Message: `capp(<track>): <package id> <what>` e.g. `capp(ent): E2 attendance grid entry`.
- Do not mention file names you did not change.

## 8. Handoff report (required, at every checkpoint)
```
TRACK: AI-n      PACKAGES DONE: ...      PACKAGES PARTIAL: ...
FILES ADDED: ...         FILES CHANGED: ...
MODELS ADDED (for AI-1 to migrate): ...
CONTRACT USED: ...        CONTRACT CHANGE REQUESTS: ... (or none)
TESTS: N new, all green? yes/no   (paste the final "Ran N tests ... OK" line)
DECISIONS I MADE ALONE: ...        OPEN QUESTIONS FOR OWNER: ...
KNOWN LIMITS: ...
```

## 9. Stop-and-ask triggers
Stop and report instead of guessing when: a frozen contract must change; Aapp behaviour would change; a statutory rule is unclear; a requirement conflicts with another track; tests would need weakening.

## 10. Style
Terse code comments that explain *why*. No dead code, no TODO left without an owner. Short functions. Names in plain English.
