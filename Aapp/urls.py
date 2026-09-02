from django.urls import path
from django.http import JsonResponse
from . import views

from Aapp.app.branch_department import (
    create_branch, list_branch, alter_branch, delete_branch,
    create_department, list_department, alter_department, delete_department,
)
from Aapp.app.designation import create_designation, list_designation, alter_designation, disable_designation
from Sapp.app.company import (
    create_company_associate, list_company_associate, alter_company_associate,
    mark_inactive_company, create_company_statutory, alter_company_statutory,
)
from Aapp.app.subuser import (
    list_subusers, add_subuser, alter_subuser, reset_subuser_password,
    disable_subuser, subuser_companies,
)
from Aapp.app.employee import (
    list_employee, create_employee, alter_employee, disable_employee, retire_employee,
    delete_employee, bulk_excel_upload_Employees as employee_bulk_excel_upload,
    download_employee_template, bulk_update_statutory_fields,
)
from Aapp.app.attandance import (
    list_attendance, add_attendance, update_attendance, bulk_attendance, delete_attendance,
    bulk_excel_upload_Attandance as attendance_bulk_excel_upload, download_attendance_template,
    list_overtime_register, create_overtime_register, alter_overtime_register, delete_overtime_register,
)
from Aapp.app.leave_management import list_leave, add_leave, update_leave, delete_leave
from Sapp.app.state_district import District

# Factories Act 1948
from Aapp.app.factory_act import (
    list_factory_registration, create_factory_registration, alter_factory_registration,
    list_whitewash_register, create_whitewash_register,
    list_vessel_examination, create_vessel_examination,
    list_leave_wages_register, create_leave_wages_register,
    list_annual_return, create_annual_return, alter_annual_return,
    list_accident_register, create_accident_register,
)

# Contractors (Form IV / XII)
from Aapp.app.contractor import (
    list_contractors, add_contractor, update_contractor, delete_contractor,
    list_contractor_workers, add_contractor_worker, add_contractor_payment,
)

# Contract Labour Act — Forms I/II, XIII, XIV, 20(CL)
from Aapp.app.contract_labour import (
    list_cl_registration, create_cl_registration, alter_cl_registration,
    list_employment_cards, create_employment_card,
    list_service_certificates, create_service_certificate,
    list_cl_returns, create_cl_return, alter_cl_return,
)

# Minimum Wages Act / Payment of Wages Act — wage registers
# NOTE: Wages Register is now read-only, sourced from salary_slip;
# generate_wages/update_wages/finalize_wages/delete_wages removed —
# process a salary batch instead (see salary_processing urls below).
from Aapp.app.wages import (
    list_wages,
    list_fines, add_fine, delete_fine,
    list_deductions, add_deduction, delete_deduction,
)

# Salary Processing — PF/ESI/PT engine, batch payroll workflow
from Aapp.app.salary_processing import (
    salary_dashboard, create_salary_batch, process_salary_batch,
    view_salary_batch, view_salary_slip, edit_salary_slip,
    approve_salary_batch, delete_salary_batch,
    list_salary_structures, create_salary_structure, view_salary_structure,
    export_salary_register, export_bank_advice,
    download_salary_template, import_salary_structures,
    pf_report, esi_report,
)

# Minimum Wages Form V / Payment of Wages Form IV — annual returns
from Aapp.app.wage_compliance import (
    list_minwages_returns, add_minwages_return, alter_minwages_return,
    list_pow_returns, add_pow_return, alter_pow_return,
)

# EPF & ESI — nomination, family declaration, ECR, contribution return
from Aapp.app.epf_esi import (
    list_epf_nominations, add_epf_nomination, delete_epf_nomination,
    list_epf_ecr, add_epf_ecr, alter_epf_ecr,
    list_esi_family, add_esi_family, remove_esi_family,
    list_esi_returns, add_esi_return, alter_esi_return,
)

# Maternity Benefit Act
from Aapp.app.maternity import (
    list_maternity, add_maternity, update_maternity, mark_maternity_paid, delete_maternity,
    list_maternity_nominations, add_maternity_nomination, delete_maternity_nomination,
)

# Payment of Gratuity Act
from Aapp.app.gratuity import (
    list_nominees, add_nominee, update_nominee, delete_nominee,
    list_gratuity, add_gratuity, mark_gratuity_paid, delete_gratuity,
    list_employer_notices, add_employer_notice,
    list_payment_notices, add_payment_notice,
)

# Payment of Bonus Act
from Aapp.app.bonus import (
    list_bonus, add_bonus, update_bonus, mark_bonus_paid, delete_bonus,
    list_set_on_set_off, add_set_on_set_off, alter_set_on_set_off,
    list_bonus_returns, add_bonus_return, alter_bonus_return,
)

# Punjab Shops & Commercial Establishments Act (Haryana)
# NOTE: overtime views removed here — use list_overtime_register /
# create_overtime_register from Aapp.app.attandance instead (Form IV
# overtime register now lives on MinimumWagesOvertimeRegister).
from Aapp.app.shops_act import (
    list_establishments, add_establishment, update_establishment, delete_establishment,
)

# Punjab Labour Welfare Fund Act (Haryana)
from Aapp.app.labour_welfare import list_lwf, add_lwf, alter_lwf, mark_lwf_paid

# Centralised statutory compliance calendar
from Aapp.app.pdf_views import (
    download_salary_slip, download_salary_sheet,
    download_salary_abstract, download_company_profile,
    download_letterhead_doc, download_all_slips,
    email_salary_slip, email_all_slips,
)

from Aapp.app.compliance_tracker import (
    compliance_dashboard, list_compliance_items, add_compliance_item,
    alter_compliance_item, mark_compliance_filed, seed_compliance_calendar,
)

from Aapp.app.loans_advances import (
    list_loans, create_loan, alter_loan, view_loan_schedule, download_loan_schedule,
    list_advances, create_advance, alter_advance, view_advance_schedule, download_advance_schedule,
)

from Aapp.app.increment import (
    list_increments, create_increment, view_increment_schedule, download_increment_schedule,
)

from Aapp.app.arrear import (
    list_arrears, create_arrear, view_arrear_schedule, download_arrear_schedule,
)

from Aapp.app.fnf_settlement import (
    list_fnf_settlements, create_fnf_settlement, view_fnf_settlement,
    finalize_fnf_settlement, download_fnf_settlement, download_fnf_certificate,
)

from Aapp.app.biometric_device import (
    list_biometric_devices, create_biometric_device,
    list_device_mappings, create_device_mapping,
)

from Aapp.app.shift import (
    list_shifts, create_shift, alter_shift, assign_shift,
)

from Aapp.app.punch_log import (
    ingest_punch, download_punch_sheet, view_daily_attendance,
)

from Aapp.app.banking import (
    list_bank_batches, select_processing_for_bank_file, create_bank_batch,
    download_bank_csv, download_bank_xlsx,
)

from Aapp.app.asset_management import (
    list_assets, create_asset, alter_asset, assign_asset,
    list_asset_recoveries, create_asset_recovery,
)

from Aapp.app.expense_management import (
    list_expense_claims, create_expense_claim, approve_expense_claim, reject_expense_claim,
)
from Aapp.app.form16 import (
    select_employee_for_form16, download_form16, download_deductions_report,
)


def get_districts(request, state_id):
    districts = District.objects.filter(state_id=state_id).order_by('name').values('Districtid', 'name')
    return JsonResponse([{'id': d['Districtid'], 'name': d['name']} for d in districts], safe=False)


app_name = 'Aapp'
# NOTE: this urls.py is loaded directly as the ROOT urlconf for the
# 'aapp' host by django-hosts (see revolution/hosts.py: host 'aapp' ->
# 'Aapp.urls'), not via include(). Django only applies app_name
# namespacing through include(), so 'Aapp:' is NEVER a valid prefix
# here — use 'aapp_dashboard' (not bare 'dashboard'), e.g. redirect('aapp_dashboard'),
# {% url 'list_employee' %}. (revolution/urls.py deliberately does NOT
# also include() this module under a path prefix — see the note there.)

urlpatterns = [
    # ── Auth & Dashboard ─────────────────────────────────────────────────────
    path('', views.associate_base_home, name='home'),
    path('login/', views.associate_login, name='associate_login'),
    path('logout/', views.logout, name='logout'),
    path('reset-password/', views.associate_password_reset_request, name='associate_password_reset_request'),
    path('reset/<str:uidb64>/<str:token>/', views.associate_password_reset_confirm, name='associate_password_reset_confirm'),
    path('dashboard/', views.associate_dashboard, name='aapp_dashboard'),
    path('profile/', views.associate_profile, name='associate_profile'),
    path('profile/public/', views.associate_public_profile_update, name='associate_public_profile_update'),


    # ── Branch & Department ──────────────────────────────────────────────────
    path('branch/create/', create_branch, name='create_branch'),
    path('branch/list/', list_branch, name='branch_list'),
    path('branch/alter/<int:branch_id>/', alter_branch, name='alter_branch'),
    path('branch/delete/<int:branch_id>/', delete_branch, name='delete_branch'),
    path('department/create/', create_department, name='create_department'),
    path('department/list/', list_department, name='department_list'),
    path('department/alter/<int:department_id>/', alter_department, name='alter_department'),
    path('department/delete/<int:department_id>/', delete_department, name='delete_department'),

    # ── Designation ───────────────────────────────────────────────────────────
    path('designation/create/', create_designation, name='create_designation'),
    path('designation/list/', list_designation, name='list_designation'),
    path('designation/alter/<int:designation_id>/', alter_designation, name='alter_designation'),
    path('designation/disable/<int:designation_id>/', disable_designation, name='disable_designation'),

    # ── Company ───────────────────────────────────────────────────────────────
    path('company/create/', create_company_associate, name='create_company_associate'),
    path('company/list/', list_company_associate, name='list_company_associate'),
    path('company/alter/<int:company_id>/', alter_company_associate, name='alter_company_associate'),
    path('company/mark-inactive/<int:company_id>/', mark_inactive_company, name='mark_inactive_company'),
    path('company/statutory/create/', create_company_statutory, name='create_company_statutory'),
    path('company/statutory/alter/<int:company_id>/', alter_company_statutory, name='alter_company_statutory'),
    path('api/companies/', views.get_user_companies, name='get_user_companies'),
    path('api/select-company/', views.select_company, name='select_company'),
    path('api/selected-company/', views.get_selected_company, name='get_selected_company'),

    # ── Sub Users ─────────────────────────────────────────────────────────────
    path('subusers/', list_subusers, name='list_subusers'),
    path('subusers/add/', add_subuser, name='add_subuser'),
    path('subusers/alter/<int:subuser_id>/', alter_subuser, name='alter_subuser'),
    path('subusers/reset-password/<int:subuser_id>/', reset_subuser_password, name='reset_subuser_password'),
    path('subusers/disable/<int:subuser_id>/', disable_subuser, name='disable_subuser'),
    path('subusers/companies/<int:subuser_id>/', subuser_companies, name='subuser_companies'),

    # ── Employees ─────────────────────────────────────────────────────────────
    path('employees/', list_employee, name='list_employee'),
    path('employees/create/', create_employee, name='create_employee'),
    path('employees/alter/<int:employee_id>/', alter_employee, name='alter_employee'),
    path('employees/disable/<int:employee_id>/', disable_employee, name='disable_employee'),
    path('employees/retire/<int:employee_id>/', retire_employee, name='retire_employee'),
    path('employees/delete/<int:employee_id>/', delete_employee, name='delete_employee'),
    path('employees/excel-upload/', employee_bulk_excel_upload, name='bulk_excel_upload_employees'),
    path('employees/download-template/', download_employee_template, name='download_employee_template'),
    path('employees/statutory-update/', bulk_update_statutory_fields, name='bulk_update_statutory_fields'),

    # ── Attendance ────────────────────────────────────────────────────────────
    path('attendance/', list_attendance, name='list_attendance'),
    path('attendance/add/', add_attendance, name='add_attendance'),
    path('attendance/bulk/', bulk_attendance, name='bulk_attendance'),
    path('attendance/update/<int:attendance_id>/', update_attendance, name='update_attendance'),
    path('attendance/delete/<int:attendance_id>/', delete_attendance, name='delete_attendance'),
    path('attendance/excel-upload/', attendance_bulk_excel_upload, name='bulk_excel_upload_attendance'),
    path('attendance/download-template/', download_attendance_template, name='download_attendance_template'),

    # Minimum Wages Act Form IV — Overtime Register
    path('attendance/overtime-register/', list_overtime_register, name='list_overtime_register'),
    path('attendance/overtime-register/create/', create_overtime_register, name='create_overtime_register'),
    path('attendance/overtime-register/alter/<int:ot_register_id>/', alter_overtime_register, name='alter_overtime_register'),
    path('attendance/overtime-register/delete/<int:ot_register_id>/', delete_overtime_register, name='delete_overtime_register'),

    # ── Leave (employee_leave — internal leave tracking) ────────────────────
    path('leave/', list_leave, name='list_leave'),
    path('leave/add/', add_leave, name='add_leave'),
    path('leave/update/<int:leave_id>/', update_leave, name='update_leave'),
    path('leave/delete/<int:leave_id>/', delete_leave, name='delete_leave'),

    path('get_districts/<int:state_id>/', get_districts, name='get_districts'),

    # ════════════════════════════════════════════════════════════════════════
    # FACTORIES ACT 1948
    # ════════════════════════════════════════════════════════════════════════
    path('factory/registration/', list_factory_registration, name='list_factory_registration'),
    path('factory/registration/create/', create_factory_registration, name='create_factory_registration'),
    path('factory/registration/alter/<int:factory_id>/', alter_factory_registration, name='alter_factory_registration'),

    path('factory/<int:factory_id>/whitewash/', list_whitewash_register, name='list_whitewash_register'),
    path('factory/<int:factory_id>/whitewash/create/', create_whitewash_register, name='create_whitewash_register'),

    path('factory/<int:factory_id>/vessel/', list_vessel_examination, name='list_vessel_examination'),
    path('factory/<int:factory_id>/vessel/create/', create_vessel_examination, name='create_vessel_examination'),

    path('factory/leave-wages/', list_leave_wages_register, name='list_leave_with_wages_register'),
    path('factory/leave-wages/create/', create_leave_wages_register, name='create_leave_with_wages_register'),

    path('factory/<int:factory_id>/annual-return/', list_annual_return, name='list_annual_return'),
    path('factory/<int:factory_id>/annual-return/create/', create_annual_return, name='create_annual_return'),
    path('factory/annual-return/alter/<int:return_id>/', alter_annual_return, name='alter_annual_return'),

    path('factory/<int:factory_id>/accident/', list_accident_register, name='list_accident_records'),
    path('factory/<int:factory_id>/accident/create/', create_accident_register, name='create_accident_record'),

    # ════════════════════════════════════════════════════════════════════════
    # CONTRACTORS (Form IV — Register of Contractors / Form XII — Muster Roll)
    # ════════════════════════════════════════════════════════════════════════
    path('contractors/', list_contractors, name='list_contractors'),
    path('contractors/add/', add_contractor, name='add_contractor'),
    path('contractors/update/<int:contractor_id>/', update_contractor, name='update_contractor'),
    path('contractors/delete/<int:contractor_id>/', delete_contractor, name='delete_contractor'),
    path('contractors/<int:contractor_id>/workers/', list_contractor_workers, name='list_contractor_workers'),
    path('contractors/<int:contractor_id>/workers/add/', add_contractor_worker, name='add_contractor_worker'),
    path('contractors/<int:contractor_id>/payment/add/', add_contractor_payment, name='add_contractor_payment'),

    # ════════════════════════════════════════════════════════════════════════
    # CONTRACT LABOUR (R&A) ACT 1970 — Forms I/II, XIII, XIV, 20(CL)
    # ════════════════════════════════════════════════════════════════════════
    path('contract-labour/registration/', list_cl_registration, name='list_cl_registration'),
    path('contract-labour/registration/create/', create_cl_registration, name='create_cl_registration'),
    path('contract-labour/registration/alter/<int:reg_id>/', alter_cl_registration, name='alter_cl_registration'),

    path('contract-labour/<int:contractor_id>/cards/', list_employment_cards, name='list_employment_cards'),
    path('contract-labour/<int:contractor_id>/cards/create/', create_employment_card, name='create_employment_card'),

    path('contract-labour/<int:contractor_id>/certificates/', list_service_certificates, name='list_service_certificates'),
    path('contract-labour/<int:contractor_id>/certificates/create/', create_service_certificate, name='create_service_certificate'),

    path('contract-labour/<int:contractor_id>/returns/', list_cl_returns, name='list_cl_returns'),
    path('contract-labour/<int:contractor_id>/returns/create/', create_cl_return, name='create_cl_return'),
    path('contract-labour/returns/alter/<int:return_id>/', alter_cl_return, name='alter_cl_return'),

    # ════════════════════════════════════════════════════════════════════════
    # WAGES — Form III/17 (Wage Register, read-only from salary_slip),
    # Form I (Fines), Form II (Deductions)
    # ════════════════════════════════════════════════════════════════════════
    path('wages/', list_wages, name='list_wages'),

    # ── Payslip PDF download & email (views existed, were never routed) ─────
    path('wages/<int:wages_id>/slip.pdf/', download_salary_slip, name='download_salary_slip'),
    path('wages/sheet/<int:month>/<int:year>/pdf/', download_salary_sheet, name='download_salary_sheet'),
    path('wages/abstract/<int:month>/<int:year>/pdf/', download_salary_abstract, name='download_salary_abstract'),
    path('wages/all-slips/<int:month>/<int:year>/pdf/', download_all_slips, name='download_all_slips'),
    path('wages/<int:wages_id>/email-slip/', email_salary_slip, name='email_salary_slip'),
    path('wages/email-all-slips/<int:month>/<int:year>/', email_all_slips, name='email_all_slips'),

    # ── Company Profile & Letterhead docs (views existed, never routed) ─────
    path('company/profile.pdf/', download_company_profile, name='download_company_profile'),
    path('letterhead/<str:doc_type>/', download_letterhead_doc, name='download_letterhead_doc'),

    path('wages/fines/', list_fines, name='list_fines'),
    path('wages/fines/add/', add_fine, name='add_fine'),
    path('wages/fines/delete/<int:fine_id>/', delete_fine, name='delete_fine'),

    path('wages/deductions/', list_deductions, name='list_deductions'),
    path('wages/deductions/add/', add_deduction, name='add_deduction'),
    path('wages/deductions/delete/<int:deduction_id>/', delete_deduction, name='delete_deduction'),

    # ── Minimum Wages Act Form V / Payment of Wages Act Form IV ─────────────
    path('wages/minimum-wages-returns/', list_minwages_returns, name='list_minwages_returns'),
    path('wages/minimum-wages-returns/add/', add_minwages_return, name='add_minwages_return'),
    path('wages/minimum-wages-returns/alter/<int:return_id>/', alter_minwages_return, name='alter_minwages_return'),

    path('wages/payment-of-wages-returns/', list_pow_returns, name='list_pow_returns'),
    path('wages/payment-of-wages-returns/add/', add_pow_return, name='add_pow_return'),
    path('wages/payment-of-wages-returns/alter/<int:return_id>/', alter_pow_return, name='alter_pow_return'),

    # ════════════════════════════════════════════════════════════════════════
    # SALARY PROCESSING — PF/ESI/PT engine, monthly batch payroll workflow
    # ════════════════════════════════════════════════════════════════════════
    path('salary/', salary_dashboard, name='salary_dashboard'),

    path('salary/batch/create/', create_salary_batch, name='create_salary_batch'),
    path('salary/batch/<int:batch_id>/process/', process_salary_batch, name='process_salary_batch'),
    path('salary/batch/<int:batch_id>/', view_salary_batch, name='view_salary_batch'),
    path('salary/batch/<int:batch_id>/approve/', approve_salary_batch, name='approve_salary_batch'),
    path('salary/batch/<int:batch_id>/delete/', delete_salary_batch, name='delete_salary_batch'),
    path('salary/batch/<int:batch_id>/export/', export_salary_register, name='export_salary_register'),
    path('salary/batch/<int:batch_id>/bank-advice/', export_bank_advice, name='export_bank_advice'),

    path('salary/slip/<int:slip_id>/', view_salary_slip, name='view_salary_slip'),
    path('salary/slip/<int:slip_id>/edit/', edit_salary_slip, name='edit_salary_slip'),

    path('salary/structures/', list_salary_structures, name='list_salary_structures'),
    path('salary/structures/create/', create_salary_structure, name='create_salary_structure'),
    path('salary/structures/<int:structure_id>/', view_salary_structure, name='view_salary_structure'),
    path('salary/structures/template/', download_salary_template, name='download_salary_template'),
    path('salary/structures/import/', import_salary_structures, name='import_salary_structures'),

    path('salary/reports/pf/', pf_report, name='pf_report'),
    path('salary/reports/esi/', esi_report, name='esi_report'),

    # ════════════════════════════════════════════════════════════════════════
    # EPF & MP ACT 1952 — Form 2 (Nomination), Monthly ECR
    # ════════════════════════════════════════════════════════════════════════
    path('epf/nominations/', list_epf_nominations, name='list_epf_nominations'),
    path('epf/nominations/add/', add_epf_nomination, name='add_epf_nomination'),
    path('epf/nominations/delete/<int:nomination_id>/', delete_epf_nomination, name='delete_epf_nomination'),

    path('epf/ecr/', list_epf_ecr, name='list_epf_ecr'),
    path('epf/ecr/add/', add_epf_ecr, name='add_epf_ecr'),
    path('epf/ecr/alter/<int:ecr_id>/', alter_epf_ecr, name='alter_epf_ecr'),

    # ════════════════════════════════════════════════════════════════════════
    # ESI ACT 1948 — Form 1A (Family), Form 7 (Half-Yearly Contribution Return)
    # ════════════════════════════════════════════════════════════════════════
    path('esi/family/', list_esi_family, name='list_esi_family'),
    path('esi/family/add/', add_esi_family, name='add_esi_family'),
    path('esi/family/remove/<int:member_id>/', remove_esi_family, name='remove_esi_family'),

    path('esi/returns/', list_esi_returns, name='list_esi_returns'),
    path('esi/returns/add/', add_esi_return, name='add_esi_return'),
    path('esi/returns/alter/<int:return_id>/', alter_esi_return, name='alter_esi_return'),

    # ════════════════════════════════════════════════════════════════════════
    # MATERNITY BENEFIT ACT 1961 — Form B (Register), Form F (Nomination)
    # ════════════════════════════════════════════════════════════════════════
    path('maternity/', list_maternity, name='list_maternity'),
    path('maternity/add/', add_maternity, name='add_maternity'),
    path('maternity/update/<int:maternity_id>/', update_maternity, name='update_maternity'),
    path('maternity/mark-paid/<int:maternity_id>/', mark_maternity_paid, name='mark_maternity_paid'),
    path('maternity/delete/<int:maternity_id>/', delete_maternity, name='delete_maternity'),

    path('maternity/nominations/', list_maternity_nominations, name='list_maternity_nominations'),
    path('maternity/nominations/add/', add_maternity_nomination, name='add_maternity_nomination'),
    path('maternity/nominations/delete/<int:nomination_id>/', delete_maternity_nomination, name='delete_maternity_nomination'),

    # ════════════════════════════════════════════════════════════════════════
    # PAYMENT OF GRATUITY ACT 1972 — Form E (Nominee), F-H (Records),
    #   A-D (Employer Notices), I/J (Payment / Rejection Notices)
    # ════════════════════════════════════════════════════════════════════════
    path('gratuity/nominees/', list_nominees, name='list_nominees'),
    path('gratuity/nominees/add/', add_nominee, name='add_nominee'),
    path('gratuity/nominees/update/<int:nominee_id>/', update_nominee, name='update_nominee'),
    path('gratuity/nominees/delete/<int:nominee_id>/', delete_nominee, name='delete_nominee'),

    path('gratuity/', list_gratuity, name='list_gratuity'),
    path('gratuity/add/', add_gratuity, name='add_gratuity'),
    path('gratuity/mark-paid/<int:gratuity_id>/', mark_gratuity_paid, name='mark_gratuity_paid'),
    path('gratuity/delete/<int:gratuity_id>/', delete_gratuity, name='delete_gratuity'),

    path('gratuity/employer-notices/', list_employer_notices, name='list_employer_notices'),
    path('gratuity/employer-notices/add/', add_employer_notice, name='add_employer_notice'),

    path('gratuity/payment-notices/', list_payment_notices, name='list_payment_notices'),
    path('gratuity/payment-notices/add/<int:gratuity_id>/', add_payment_notice, name='add_payment_notice'),

    # ════════════════════════════════════════════════════════════════════════
    # PAYMENT OF BONUS ACT 1965 — Form A/C (Bonus), Form B (Set-On/Off), Form D (Annual)
    # ════════════════════════════════════════════════════════════════════════
    path('bonus/', list_bonus, name='list_bonus'),
    path('bonus/add/', add_bonus, name='add_bonus'),
    path('bonus/update/<int:bonus_id>/', update_bonus, name='update_bonus'),
    path('bonus/mark-paid/<int:bonus_id>/', mark_bonus_paid, name='mark_bonus_paid'),
    path('bonus/delete/<int:bonus_id>/', delete_bonus, name='delete_bonus'),

    path('bonus/set-on-set-off/', list_set_on_set_off, name='list_set_on_set_off'),
    path('bonus/set-on-set-off/add/', add_set_on_set_off, name='add_set_on_set_off'),
    path('bonus/set-on-set-off/alter/<int:record_id>/', alter_set_on_set_off, name='alter_set_on_set_off'),

    path('bonus/annual-returns/', list_bonus_returns, name='list_bonus_returns'),
    path('bonus/annual-returns/add/', add_bonus_return, name='add_bonus_return'),
    path('bonus/annual-returns/alter/<int:return_id>/', alter_bonus_return, name='alter_bonus_return'),

    # ════════════════════════════════════════════════════════════════════════
    # PUNJAB SHOPS & COMMERCIAL ESTABLISHMENTS ACT 1958 (HARYANA)
    # ════════════════════════════════════════════════════════════════════════
    path('shops-act/establishments/', list_establishments, name='list_establishments'),
    path('shops-act/establishments/add/', add_establishment, name='add_establishment'),
    path('shops-act/establishments/update/<int:estab_id>/', update_establishment, name='update_establishment'),
    path('shops-act/establishments/delete/<int:estab_id>/', delete_establishment, name='delete_establishment'),
    # Overtime register — see 'attendance/overtime-register/' below
    # (Aapp.app.attandance.MinimumWagesOvertimeRegister)

    # ════════════════════════════════════════════════════════════════════════
    # PUNJAB LABOUR WELFARE FUND ACT 1965 (HARYANA)
    # ════════════════════════════════════════════════════════════════════════
    path('labour-welfare-fund/', list_lwf, name='list_lwf'),
    path('labour-welfare-fund/add/', add_lwf, name='add_lwf'),
    path('labour-welfare-fund/alter/<int:lwf_id>/', alter_lwf, name='alter_lwf'),
    path('labour-welfare-fund/mark-paid/<int:lwf_id>/', mark_lwf_paid, name='mark_lwf_paid'),

    # ════════════════════════════════════════════════════════════════════════
    # CENTRALISED COMPLIANCE CALENDAR — all acts, all due dates, one dashboard
    # ════════════════════════════════════════════════════════════════════════
    path('compliance/', compliance_dashboard, name='compliance_dashboard'),
    path('compliance/items/', list_compliance_items, name='list_compliance_items'),
    path('compliance/items/add/', add_compliance_item, name='add_compliance_item'),
    path('compliance/items/alter/<int:tracker_id>/', alter_compliance_item, name='alter_compliance_item'),
    path('compliance/items/mark-filed/<int:tracker_id>/', mark_compliance_filed, name='mark_compliance_filed'),
    path('compliance/seed/', seed_compliance_calendar, name='seed_compliance_calendar'),

    path('loans/', list_loans, name='list_loans'),
    path('loans/add/', create_loan, name='create_loan'),
    path('loans/alter/<int:loan_id>/', alter_loan, name='alter_loan'),
    path('loans/schedule/<int:loan_id>/', view_loan_schedule, name='view_loan_schedule'),
    path('loans/schedule/<int:loan_id>/download/', download_loan_schedule, name='download_loan_schedule'),

    path('advances/', list_advances, name='list_advances'),
    path('advances/add/', create_advance, name='create_advance'),
    path('advances/alter/<int:advance_id>/', alter_advance, name='alter_advance'),
    path('advances/schedule/<int:advance_id>/', view_advance_schedule, name='view_advance_schedule'),
    path('advances/schedule/<int:advance_id>/download/', download_advance_schedule, name='download_advance_schedule'),

    path('increments/', list_increments, name='list_increments'),
    path('increments/add/', create_increment, name='create_increment'),
    path('increments/schedule/<int:increment_id>/', view_increment_schedule, name='view_increment_schedule'),
    path('increments/schedule/<int:increment_id>/download/', download_increment_schedule, name='download_increment_schedule'),

    path('arrears/', list_arrears, name='list_arrears'),
    path('arrears/add/', create_arrear, name='create_arrear'),
    path('arrears/schedule/<int:arrear_id>/', view_arrear_schedule, name='view_arrear_schedule'),
    path('arrears/schedule/<int:arrear_id>/download/', download_arrear_schedule, name='download_arrear_schedule'),

    path('fnf/', list_fnf_settlements, name='list_fnf_settlements'),
    path('fnf/add/', create_fnf_settlement, name='create_fnf_settlement'),
    path('fnf/<int:settlement_id>/', view_fnf_settlement, name='view_fnf_settlement'),
    path('fnf/<int:settlement_id>/finalize/', finalize_fnf_settlement, name='finalize_fnf_settlement'),
    path('fnf/<int:settlement_id>/download/', download_fnf_settlement, name='download_fnf_settlement'),
    path('fnf/<int:settlement_id>/certificate/<str:cert_type>/', download_fnf_certificate, name='download_fnf_certificate'),

    path('biometric/devices/', list_biometric_devices, name='list_biometric_devices'),
    path('biometric/devices/add/', create_biometric_device, name='create_biometric_device'),
    path('biometric/devices/<int:device_id>/mappings/', list_device_mappings, name='list_device_mappings'),
    path('biometric/devices/<int:device_id>/mappings/add/', create_device_mapping, name='create_device_mapping'),
    path('biometric/ingest/', ingest_punch, name='ingest_punch'),  # daemon-facing, API-key auth not session auth

    path('shifts/', list_shifts, name='list_shifts'),
    path('shifts/add/', create_shift, name='create_shift'),
    path('shifts/alter/<int:shift_id>/', alter_shift, name='alter_shift'),
    path('shifts/assign/', assign_shift, name='assign_shift'),

    path('attendance/daily/<int:month>/<int:year>/', view_daily_attendance, name='view_daily_attendance'),
    path('attendance/daily/<int:month>/<int:year>/download/', download_punch_sheet, name='download_punch_sheet'),

    path('banking/batches/', list_bank_batches, name='list_bank_batches'),
    path('banking/select-batch/', select_processing_for_bank_file, name='select_processing_for_bank_file'),
    path('banking/generate/<int:processing_id>/', create_bank_batch, name='create_bank_batch'),
    path('banking/download/<int:batch_id>/csv/', download_bank_csv, name='download_bank_csv'),
    path('banking/download/<int:batch_id>/xlsx/', download_bank_xlsx, name='download_bank_xlsx'),

    path('assets/', list_assets, name='list_assets'),
    path('assets/add/', create_asset, name='create_asset'),
    path('assets/alter/<int:asset_id>/', alter_asset, name='alter_asset'),
    path('assets/assign/<int:asset_id>/', assign_asset, name='assign_asset'),
    path('assets/recoveries/', list_asset_recoveries, name='list_asset_recoveries'),
    path('assets/recoveries/add/', create_asset_recovery, name='create_asset_recovery'),

    path('expenses/', list_expense_claims, name='list_expense_claims'),
    path('expenses/add/', create_expense_claim, name='create_expense_claim'),
    path('expenses/approve/<int:expense_id>/', approve_expense_claim, name='approve_expense_claim'),
    path('expenses/reject/<int:expense_id>/', reject_expense_claim, name='reject_expense_claim'),

    # ── Income Tax / Form 16 — Aapp/app/form16.py (views existed, never routed) ──
    path('form16/', select_employee_for_form16, name='select_employee_for_form16'),
    path('form16/<int:employee_id>/<str:financial_year>/', download_form16, name='download_form16'),
    path('form16/deductions-report/<int:month>/<int:year>/', download_deductions_report, name='download_deductions_report'),
]
