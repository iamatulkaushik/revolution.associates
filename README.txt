Revolution Associates update (copy over repo root, same paths)

1. Copy all folders over the repo.
2. Migrations are gitignored: git add -f Capp/migrations/0002_*.py Sapp/migrations/0002_*.py
   (delete any earlier Capp 0002 you applied before, then:)
3. python manage.py migrate
4. Run tests: python manage.py test Capp   (33 tests)

Included:
- Capp billing: billing_models, billing_engine (ESI basic/gross, OT no ESI, ceil rupee bank)
- Capp masters: company+bank, branch, department, designation
- Bank formats per company + bank payment file download (Capp/bank_views.py)
- Billing clients, employee deductions (loan/advance recurring, selective once), Mark month paid button
- Invoices: salary + OT bills from payroll slips, client-employee mapping, PDF with annexure, Excel, issue/cancel, payment + TDS tracking, FY numbering INV/2026-27/0001
- Excel employee import: upload, preview, confirm (Capp/importer.py). requirements.txt adds xlrd for .xls (pip install -r requirements.txt)
- Sapp fix: districts dropdown URL (create/alter company templates)
- revolution/error_views.py: custom 400/403/403-CSRF/404/500 pages.
  Wire handlers in each urls.py and CSRF_FAILURE_VIEW in settings
  (see chat notes).
NOT included: Cxapp/middleware.py Resolver404 fix, handler wiring.
