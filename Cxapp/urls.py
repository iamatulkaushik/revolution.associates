from django.urls import path

from Cxapp.views import (
    cxapp_signup, cxapp_login, cxapp_logout, cxapp_dashboard,
    cxapp_company_profile, cxapp_districts_for_state,
)
from Cxapp.app.sub_user import (
    cxapp_sub_user_list, cxapp_sub_user_create, cxapp_sub_user_deactivate,
)
from Cxapp.app.designation import (
    cxapp_designation_list, cxapp_designation_create, cxapp_designation_edit,
    cxapp_designation_delete, cxapp_designation_components, cxapp_component_delete,
)
from Cxapp.app.employee import (
    cxapp_employee_list, cxapp_employee_create, cxapp_employee_detail,
    cxapp_employee_address_edit, cxapp_employee_contact_edit,
    cxapp_employee_statutory_edit, cxapp_employee_kyc_edit,
    cxapp_employee_banking_edit, cxapp_employee_employment_edit,
    cxapp_employee_nominee_add, cxapp_employee_nominee_delete,
)
from Cxapp.app.license import cxapp_plan_purchase
from Cxapp.app.attandance import (
    cxapp_attendance_list, cxapp_attendance_create, cxapp_attendance_edit,
    cxapp_attendance_detail, cxapp_attendance_delete, cxapp_attendance_maternity_edit,
)
from Cxapp.app.process import (
    cxapp_salary_list, cxapp_salary_process, cxapp_salary_bulk_process,
    cxapp_salary_detail, cxapp_salary_reprocess,
)
from Cxapp.app.compliance import (
    cxapp_compliance_dashboard, cxapp_epf_export, cxapp_esi_export, cxapp_labour_challan,
)
from Cxapp.app.statutory import cxapp_company_statutory

# NOTE: Cxapp/urls.py is the ROOT urlconf for the 'cxapp' host in django-hosts.
# Bare URL names (no namespace prefix) — same pattern as Aapp/Capp.

urlpatterns = [

    # ── Auth ──────────────────────────────────────────────────────────────────
    path('',           cxapp_login,   name='cxapp_login'),
    path('signup/',    cxapp_signup,  name='cxapp_signup'),
    path('login/',     cxapp_login,   name='cxapp_login'),
    path('logout/',    cxapp_logout,  name='cxapp_logout'),

    # ── Dashboard ─────────────────────────────────────────────────────────────
    path('dashboard/', cxapp_dashboard, name='cxapp_dashboard'),

    # ── Company profile ──────────────────────────────────────────────────────
    path('company/',   cxapp_company_profile, name='cxapp_company_profile'),
    path('company/statutory/', cxapp_company_statutory, name='cxapp_company_statutory'),

    # ── Shared cascading state/district filter ───────────────────────────────
    path('api/districts/', cxapp_districts_for_state, name='cxapp_districts_for_state'),

    # ── Sub-users (owner only) — Cxapp/app/sub_user.py ───────────────────────
    path('sub-users/',                        cxapp_sub_user_list,       name='cxapp_sub_user_list'),
    path('sub-users/new/',                    cxapp_sub_user_create,     name='cxapp_sub_user_create'),
    path('sub-users/<int:sub_user_id>/off/',  cxapp_sub_user_deactivate, name='cxapp_sub_user_deactivate'),

    # ── Designations & Wage-Code components — Cxapp/app/designation.py ──────
    path('designations/',                                  cxapp_designation_list,       name='cxapp_designation_list'),
    path('designations/new/',                               cxapp_designation_create,     name='cxapp_designation_create'),
    path('designations/<int:designation_id>/edit/',         cxapp_designation_edit,       name='cxapp_designation_edit'),
    path('designations/<int:designation_id>/delete/',       cxapp_designation_delete,     name='cxapp_designation_delete'),
    path('designations/<int:designation_id>/components/',   cxapp_designation_components, name='cxapp_designation_components'),
    path('designations/components/<int:component_id>/delete/', cxapp_component_delete,    name='cxapp_component_delete'),

    # ── Employees — Cxapp/app/employee.py ────────────────────────────────────
    path('employees/',                                    cxapp_employee_list,              name='cxapp_employee_list'),
    path('employees/new/',                                cxapp_employee_create,            name='cxapp_employee_create'),
    path('employees/<int:employee_id>/',                  cxapp_employee_detail,            name='cxapp_employee_detail'),
    path('employees/<int:employee_id>/address/',          cxapp_employee_address_edit,      name='cxapp_employee_address_edit'),
    path('employees/<int:employee_id>/contact/',          cxapp_employee_contact_edit,      name='cxapp_employee_contact_edit'),
    path('employees/<int:employee_id>/statutory/',        cxapp_employee_statutory_edit,    name='cxapp_employee_statutory_edit'),
    path('employees/<int:employee_id>/kyc/',              cxapp_employee_kyc_edit,          name='cxapp_employee_kyc_edit'),
    path('employees/<int:employee_id>/banking/',          cxapp_employee_banking_edit,      name='cxapp_employee_banking_edit'),
    path('employees/<int:employee_id>/employment/',       cxapp_employee_employment_edit,   name='cxapp_employee_employment_edit'),
    path('employees/<int:employee_id>/nominees/new/',     cxapp_employee_nominee_add,       name='cxapp_employee_nominee_add'),
    path('employees/nominees/<int:nominee_id>/delete/',   cxapp_employee_nominee_delete,    name='cxapp_employee_nominee_delete'),

    # ── License / Plan — Cxapp/app/license.py ────────────────────────────────
    path('plan/', cxapp_plan_purchase, name='cxapp_plan_purchase'),

    # ── Attendance — Cxapp/app/attandance.py ─────────────────────────────────
    path('attendance/',                                cxapp_attendance_list,           name='cxapp_attendance_list'),
    path('attendance/new/',                            cxapp_attendance_create,         name='cxapp_attendance_create'),
    path('attendance/<int:attendance_id>/',            cxapp_attendance_detail,         name='cxapp_attendance_detail'),
    path('attendance/<int:attendance_id>/edit/',       cxapp_attendance_edit,           name='cxapp_attendance_edit'),
    path('attendance/<int:attendance_id>/delete/',     cxapp_attendance_delete,         name='cxapp_attendance_delete'),
    path('attendance/<int:attendance_id>/maternity/',  cxapp_attendance_maternity_edit, name='cxapp_attendance_maternity_edit'),

    # ── Salary Processing — Cxapp/app/process.py ─────────────────────────────
    path('salary/',                        cxapp_salary_list,          name='cxapp_salary_list'),
    path('salary/process/',                cxapp_salary_process,       name='cxapp_salary_process'),
    path('salary/bulk-process/',           cxapp_salary_bulk_process,  name='cxapp_salary_bulk_process'),
    path('salary/<int:salary_id>/',        cxapp_salary_detail,        name='cxapp_salary_detail'),
    path('salary/<int:salary_id>/reprocess/', cxapp_salary_reprocess,  name='cxapp_salary_reprocess'),

    # ── Compliance Exports — Cxapp/app/compliance.py ─────────────────────────
    path('compliance/',              cxapp_compliance_dashboard, name='cxapp_compliance_dashboard'),
    path('compliance/epf/export/',   cxapp_epf_export,           name='cxapp_epf_export'),
    path('compliance/esi/export/',   cxapp_esi_export,           name='cxapp_esi_export'),
    path('compliance/labour/challan/', cxapp_labour_challan,     name='cxapp_labour_challan'),
]
