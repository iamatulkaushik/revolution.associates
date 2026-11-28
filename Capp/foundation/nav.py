"""Capp/foundation/nav.py — the base menu (frozen NAV schema, see master plan section 5).

group : {"id","label","css", "url_name"?, "perm"?, "modes"?, "items"?}
item  : {"label","url_name","perm","modes","kwargs"?}
`perm` None = always shown. `modes` omitted = both modes.
A group with `items` shows only when at least one item is visible.
"""
BOTH = ('DIRECT', 'ASSOCIATE')

NAV = [
    {'id': 'dash', 'label': 'Dashboard', 'css': 'dashboard', 'url_name': 'capp_dashboard'},
    {'id': 'emp', 'label': 'Employees', 'css': 'employees', 'items': [
        {'label': 'All Employees', 'url_name': 'capp_employee_list', 'perm': 'employees.view'},
        {'label': 'Import from Excel', 'url_name': 'capp_import_employees', 'perm': 'employees.add'},
    ]},
    {'id': 'att', 'label': 'Attendance', 'css': 'attandance', 'items': [
        {'label': 'Attendance Register', 'url_name': 'capp_attendance_list', 'perm': 'attendance.view'},
        {'label': 'Overtime Register', 'url_name': 'capp_overtime_list', 'perm': 'attendance.view'},
    ]},
    {'id': 'wages', 'label': 'Wages & Payroll', 'css': 'statuary', 'items': [
        {'label': 'Wage Register', 'url_name': 'capp_wages_list', 'perm': 'wages.view'},
        {'label': 'Bank Payment Files', 'url_name': 'capp_bank_file', 'perm': 'wages.view',
         'feature': 'bank_file'},
    ]},
    {'id': 'stat', 'label': 'Statutory', 'css': 'statuary', 'items': [
        {'label': 'EPF ECR', 'url_name': 'capp_epf_ecr', 'perm': 'statutory.view'},
        {'label': 'ESI Returns', 'url_name': 'capp_esi_returns', 'perm': 'statutory.view'},
        {'label': 'Gratuity', 'url_name': 'capp_gratuity', 'perm': 'statutory.view'},
        {'label': 'Bonus', 'url_name': 'capp_bonus', 'perm': 'statutory.view'},
        {'label': 'Maternity', 'url_name': 'capp_maternity', 'perm': 'statutory.view'},
        {'label': 'Labour Welfare Fund', 'url_name': 'capp_lwf', 'perm': 'statutory.view'},
    ]},
    {'id': 'comp', 'label': 'Compliance Calendar', 'css': 'statuary',
     'url_name': 'capp_compliance', 'perm': 'compliance.view'},
    {'id': 'rep', 'label': 'Reports & Docs', 'css': 'statuary', 'perm': 'reports.view', 'items': [
        {'label': 'Company Profile', 'url_name': 'capp_company_profile_pdf', 'perm': 'reports.view'},
        {'label': 'Quotation', 'url_name': 'capp_letterhead', 'kwargs': {'doc_type': 'quotation'}, 'perm': 'reports.view'},
        {'label': 'Appointment Letter', 'url_name': 'capp_letterhead', 'kwargs': {'doc_type': 'appointment_letter'}, 'perm': 'reports.view'},
        {'label': 'Show Cause Notice', 'url_name': 'capp_letterhead', 'kwargs': {'doc_type': 'show_cause'}, 'perm': 'reports.view'},
        {'label': 'Office Notice', 'url_name': 'capp_letterhead', 'kwargs': {'doc_type': 'notice'}, 'perm': 'reports.view'},
    ]},
    {'id': 'mast', 'label': 'Masters', 'css': 'employees', 'items': [
        {'label': 'Company & Bank', 'url_name': 'capp_company_details', 'perm': 'masters.edit'},
        {'label': 'Branches', 'url_name': 'capp_branch_list', 'perm': 'masters.edit'},
        {'label': 'Departments', 'url_name': 'capp_department_list', 'perm': 'masters.edit'},
        {'label': 'Designations', 'url_name': 'capp_designation_list', 'perm': 'masters.edit'},
        {'label': 'Bank Formats', 'url_name': 'capp_bankformat_list', 'perm': 'masters.edit',
         'feature': 'bank_file'},
    ]},
    {'id': 'bill', 'label': 'Contractor Billing', 'css': 'employees', 'items': [
        {'label': 'Billing Clients', 'url_name': 'capp_client_list', 'perm': 'billing.manage'},
        {'label': 'Invoices', 'url_name': 'capp_invoice_list', 'perm': 'billing.manage'},
        {'label': 'Deductions', 'url_name': 'capp_deduction_list', 'perm': 'billing.manage'},
    ]},
    {'id': 'admin', 'label': 'Administration', 'css': 'employees', 'items': [
        {'label': 'Operators', 'url_name': 'capp_operator_list', 'perm': 'operators.manage'},
        {'label': 'Audit Log', 'url_name': 'capp_audit_list', 'perm': 'operators.manage'},
    ]},
]
