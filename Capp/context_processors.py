"""
Capp/context_processors.py
===========================
Injects `owned_company`, `owner_profile`, and `nav_categories` into
every template rendered within the Capp (owner) portal.

Add to TEMPLATES context_processors in settings.py:
    'Capp.context_processors.owner_context',
"""


def owner_context(request):
    profile = getattr(request, 'owner_profile', None)
    company = getattr(request, 'owned_company', None)

    if not profile or not company:
        return {}

    flags = profile.get_access_flags()

    nav_categories = []

    nav_categories.append({
        'label': 'Dashboard',
        'icon': 'dashboard',
        'url_name': 'capp_dashboard',
        'items': [],
    })

    if flags['employees']:
        nav_categories.append({
            'label': 'Employees',
            'icon': 'employees',
            'items': [
                {'label': 'All Employees',  'url_name': 'capp_employee_list'},
                {'label': 'Employee Detail','url_name': 'capp_employee_detail', 'needs_pk': True},
            ],
        })

    if flags['attendance']:
        nav_categories.append({
            'label': 'Attendance',
            'icon': 'attandance',
            'items': [
                {'label': 'Attendance Register', 'url_name': 'capp_attendance_list'},
                {'label': 'Overtime Register',   'url_name': 'capp_overtime_list'},
            ],
        })

    if flags['wages']:
        nav_categories.append({
            'label': 'Wages & Payroll',
            'icon': 'statuary',
            'items': [
                {'label': 'Wage Register',  'url_name': 'capp_wages_list'},
                {'label': 'Salary Slip',    'url_name': 'capp_salary_slip'},
                {'label': 'Salary Sheet',   'url_name': 'capp_salary_sheet'},
                {'label': 'Salary Abstract','url_name': 'capp_salary_abstract'},
            ],
        })

    if flags['statutory']:
        nav_categories.append({
            'label': 'Statutory',
            'icon': 'statuary',
            'items': [
                {'label': 'EPF ECR',           'url_name': 'capp_epf_ecr'},
                {'label': 'ESI Returns',        'url_name': 'capp_esi_returns'},
                {'label': 'Gratuity Register',  'url_name': 'capp_gratuity'},
                {'label': 'Bonus Register',     'url_name': 'capp_bonus'},
                {'label': 'Maternity',          'url_name': 'capp_maternity'},
                {'label': 'Labour Welfare Fund','url_name': 'capp_lwf'},
            ],
        })

    if flags['compliance']:
        nav_categories.append({
            'label': 'Compliance',
            'icon': 'statuary',
            'items': [
                {'label': 'Compliance Calendar', 'url_name': 'capp_compliance'},
            ],
        })

    if flags['reports']:
        nav_categories.append({
            'label': 'Reports & Documents',
            'icon': 'statuary',
            'items': [
                {'label': 'Company Profile PDF',    'url_name': 'capp_company_profile_pdf'},
                {'label': 'Quotation',              'url_name': 'capp_letterhead', 'kwargs': {'doc_type': 'quotation'}},
                {'label': 'Appointment Letter',     'url_name': 'capp_letterhead', 'kwargs': {'doc_type': 'appointment_letter'}},
                {'label': 'Show Cause Notice',      'url_name': 'capp_letterhead', 'kwargs': {'doc_type': 'show_cause'}},
                {'label': 'Office Notice',          'url_name': 'capp_letterhead', 'kwargs': {'doc_type': 'notice'}},
            ],
        })

    return {
        'owned_company':  company,
        'owner_profile':  profile,
        'nav_categories': nav_categories,
        'access':         flags,
    }
