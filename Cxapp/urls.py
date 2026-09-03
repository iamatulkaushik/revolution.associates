from django.urls import path

from Cxapp.app.email_verify import cxapp_resend_verification, cxapp_verify_email
from Cxapp.views import (
    cxapp_signup, cxapp_login, cxapp_logout, cxapp_dashboard,
    cxapp_password_reset_request, cxapp_password_reset_confirm,
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
    cxapp_employee_set_password,
)
from Cxapp.app.license import cxapp_plan_purchase
from Cxapp.app.attandance import (
    cxapp_attendance_list, cxapp_attendance_create, cxapp_attendance_edit,
    cxapp_attendance_detail, cxapp_attendance_delete, cxapp_attendance_maternity_edit,
)
from Cxapp.app.process import (
    cxapp_salary_list, cxapp_salary_process, cxapp_salary_bulk_process,
    cxapp_salary_detail, cxapp_salary_reprocess, cxapp_salary_slip_pdf,
    cxapp_email_salary_slip, cxapp_email_all_slips,
)
from Cxapp.app.loans_advances import (
    cxapp_list_loans, cxapp_create_loan, cxapp_view_loan_schedule,
    cxapp_list_advances, cxapp_create_advance, cxapp_view_advance_schedule,
)
from Cxapp.app.fnf_settlement import (
    cxapp_list_fnf, cxapp_create_fnf, cxapp_view_fnf, cxapp_finalize_fnf,
    cxapp_download_fnf, cxapp_download_fnf_certificate,
)
from Cxapp.app.increment import (
    cxapp_list_increments, cxapp_create_increment, cxapp_view_increment,
)
from Cxapp.app.arrear import (
    cxapp_list_arrears, cxapp_create_arrear, cxapp_view_arrear,
)
from Cxapp.app.banking import (
    cxapp_list_bank_batches, cxapp_select_salary_for_bank_file, cxapp_create_bank_batch,
    cxapp_download_bank_csv, cxapp_download_bank_xlsx,
)
from Cxapp.app.biometric import (
    cxapp_list_devices, cxapp_create_device, cxapp_list_device_mappings, cxapp_create_device_mapping,
    cxapp_list_shifts, cxapp_create_shift, cxapp_assign_shift, ingest_punch,
)
from Cxapp.app.asset_management import (
    cxapp_list_assets, cxapp_create_asset, cxapp_assign_asset,
    cxapp_list_asset_recoveries, cxapp_create_asset_recovery,
)
from Cxapp.app.expense_management import (
    cxapp_list_expense_claims, cxapp_create_expense_claim,
    cxapp_approve_expense_claim, cxapp_reject_expense_claim,
)
from Cxapp.app.compliance import (
    cxapp_compliance_dashboard, cxapp_epf_export, cxapp_esi_export, cxapp_labour_challan,
    cxapp_income_tax_report,
)
from Cxapp.app.statutory import cxapp_company_statutory
from Cxapp.app.employee_portal import (
    cxapp_emp_login, cxapp_emp_logout, cxapp_emp_dashboard, cxapp_emp_salary_slip_pdf,
    cxapp_emp_password_reset_request, cxapp_emp_password_reset_confirm,
)

# NOTE: Cxapp/urls.py is the ROOT urlconf for the 'cxapp' host in django-hosts.
# Bare URL names (no namespace prefix) — same pattern as Aapp/Capp.
#
# cxapp_employee_set_password was previously imported/routed here but the
# view was never implemented in Cxapp/app/employee.py — removed until it
# exists (it was breaking every route in this urlconf). See memory note:
# "Interface for Owner/HR to set employee portal passwords" — still on
# the roadmap, not yet built.

urlpatterns = [

    # ── Auth ──────────────────────────────────────────────────────────────────
    path('',           cxapp_login,   name='cxapp_login'),
    path('signup/',    cxapp_signup,  name='cxapp_signup'),
    path('login/',     cxapp_login,   name='cxapp_login'),
    path('logout/',    cxapp_logout,  name='cxapp_logout'),
    path('verify-email/<str:token>/', cxapp_verify_email, name='cxapp_verify_email'),
    path('resend-verification/', cxapp_resend_verification, name='cxapp_resend_verification'),
    path('reset-password/', cxapp_password_reset_request, name='cxapp_password_reset_request'),
    path('reset/<str:uidb64>/<str:token>/', cxapp_password_reset_confirm, name='cxapp_password_reset_confirm'),

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
    path('employees/<int:employee_id>/set-password/',     cxapp_employee_set_password,      name='cxapp_employee_set_password'),

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
    path('salary/<int:salary_id>/pdf/',       cxapp_salary_slip_pdf,   name='cxapp_salary_slip_pdf'),
    path('salary/<int:salary_id>/email/',     cxapp_email_salary_slip, name='cxapp_email_salary_slip'),
    path('salary/email-all/<int:month>/<int:year>/', cxapp_email_all_slips, name='cxapp_email_all_slips'),

    # ── Loans & Advances — Cxapp/app/loans_advances.py ───────────────────────
    path('loans/',                          cxapp_list_loans,           name='cxapp_list_loans'),
    path('loans/add/',                      cxapp_create_loan,          name='cxapp_create_loan'),
    path('loans/<int:loan_id>/schedule/',   cxapp_view_loan_schedule,   name='cxapp_view_loan_schedule'),
    path('advances/',                       cxapp_list_advances,        name='cxapp_list_advances'),
    path('advances/add/',                   cxapp_create_advance,       name='cxapp_create_advance'),
    path('advances/<int:advance_id>/schedule/', cxapp_view_advance_schedule, name='cxapp_view_advance_schedule'),

    # ── Full & Final Settlement — Cxapp/app/fnf_settlement.py ────────────────
    path('fnf/',                            cxapp_list_fnf,             name='cxapp_list_fnf'),
    path('fnf/add/',                        cxapp_create_fnf,           name='cxapp_create_fnf'),
    path('fnf/<int:settlement_id>/',        cxapp_view_fnf,             name='cxapp_view_fnf'),
    path('fnf/<int:settlement_id>/finalize/', cxapp_finalize_fnf,       name='cxapp_finalize_fnf'),
    path('fnf/<int:settlement_id>/download/', cxapp_download_fnf,       name='cxapp_download_fnf'),
    path('fnf/<int:settlement_id>/certificate/<str:cert_type>/', cxapp_download_fnf_certificate, name='cxapp_download_fnf_certificate'),

    # ── Increment & Arrear — Cxapp/app/increment.py, Cxapp/app/arrear.py ─────
    path('increments/',                     cxapp_list_increments,      name='cxapp_list_increments'),
    path('increments/add/',                 cxapp_create_increment,     name='cxapp_create_increment'),
    path('increments/<int:increment_id>/',  cxapp_view_increment,       name='cxapp_view_increment'),
    path('arrears/',                        cxapp_list_arrears,         name='cxapp_list_arrears'),
    path('arrears/add/',                    cxapp_create_arrear,        name='cxapp_create_arrear'),
    path('arrears/<int:arrear_id>/',        cxapp_view_arrear,          name='cxapp_view_arrear'),

    # ── Banking (NEFT/RTGS/IMPS) — Cxapp/app/banking.py ──────────────────────
    path('banking/batches/',                cxapp_list_bank_batches,           name='cxapp_list_bank_batches'),
    path('banking/select-batch/',           cxapp_select_salary_for_bank_file, name='cxapp_select_salary_for_bank_file'),
    path('banking/generate/<int:month>/<int:year>/', cxapp_create_bank_batch, name='cxapp_create_bank_batch'),
    path('banking/download/<int:batch_id>/csv/',  cxapp_download_bank_csv,  name='cxapp_download_bank_csv'),
    path('banking/download/<int:batch_id>/xlsx/', cxapp_download_bank_xlsx, name='cxapp_download_bank_xlsx'),

    # ── Biometric/RFID Attendance — Cxapp/app/biometric.py ───────────────────
    path('biometric/devices/',                    cxapp_list_devices,          name='cxapp_list_devices'),
    path('biometric/devices/add/',                cxapp_create_device,         name='cxapp_create_device'),
    path('biometric/devices/<int:device_id>/mappings/',     cxapp_list_device_mappings,   name='cxapp_list_device_mappings'),
    path('biometric/devices/<int:device_id>/mappings/add/', cxapp_create_device_mapping,  name='cxapp_create_device_mapping'),
    path('biometric/ingest/',                     ingest_punch,                name='cxapp_ingest_punch'),
    path('shifts/',                               cxapp_list_shifts,           name='cxapp_list_shifts'),
    path('shifts/add/',                           cxapp_create_shift,          name='cxapp_create_shift'),
    path('shifts/assign/',                        cxapp_assign_shift,          name='cxapp_assign_shift'),

    # ── Assets & Expenses — Cxapp/app/asset_management.py, Cxapp/app/expense_management.py ──
    path('assets/',                         cxapp_list_assets,             name='cxapp_list_assets'),
    path('assets/add/',                     cxapp_create_asset,            name='cxapp_create_asset'),
    path('assets/assign/<int:asset_id>/',   cxapp_assign_asset,            name='cxapp_assign_asset'),
    path('assets/recoveries/',              cxapp_list_asset_recoveries,   name='cxapp_list_asset_recoveries'),
    path('assets/recoveries/add/',          cxapp_create_asset_recovery,   name='cxapp_create_asset_recovery'),

    path('expenses/',                       cxapp_list_expense_claims,     name='cxapp_list_expense_claims'),
    path('expenses/add/',                   cxapp_create_expense_claim,    name='cxapp_create_expense_claim'),
    path('expenses/approve/<int:expense_id>/', cxapp_approve_expense_claim, name='cxapp_approve_expense_claim'),
    path('expenses/reject/<int:expense_id>/',  cxapp_reject_expense_claim,  name='cxapp_reject_expense_claim'),

    # ── Compliance Exports — Cxapp/app/compliance.py ─────────────────────────
    path('compliance/',              cxapp_compliance_dashboard, name='cxapp_compliance_dashboard'),
    path('compliance/epf/export/',   cxapp_epf_export,           name='cxapp_epf_export'),
    path('compliance/esi/export/',   cxapp_esi_export,           name='cxapp_esi_export'),
    path('compliance/labour/challan/', cxapp_labour_challan,     name='cxapp_labour_challan'),
    path('compliance/income-tax/',     cxapp_income_tax_report,  name='cxapp_income_tax_report'),

    # ── Employee self-service portal — PAN + password login ──────────────────
    # Cxapp/app/employee_portal.py — separate session track, own salary
    # slips only. Not part of the Owner/Sub-user auth/middleware chain.
    path('employee/login/',    cxapp_emp_login,          name='cxapp_emp_login'),
    path('employee/logout/',   cxapp_emp_logout,         name='cxapp_emp_logout'),
    path('employee/',          cxapp_emp_dashboard,      name='cxapp_emp_dashboard'),
    path('employee/salary/<int:salary_id>/pdf/', cxapp_emp_salary_slip_pdf, name='cxapp_emp_salary_slip_pdf'),
    path('employee/reset-password/', cxapp_emp_password_reset_request, name='cxapp_emp_password_reset_request'),
    path('employee/reset/<str:token>/', cxapp_emp_password_reset_confirm, name='cxapp_emp_password_reset_confirm'),
]