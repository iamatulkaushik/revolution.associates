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
    download_employee_template,
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
from Aapp.app.wages import (
    list_wages, generate_wages, update_wages, finalize_wages, delete_wages,
    list_fines, add_fine, delete_fine,
    list_deductions, add_deduction, delete_deduction,
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
from Aapp.app.shops_act import (
    list_establishments, add_establishment, update_establishment, delete_establishment,
    list_overtime, add_overtime, delete_overtime,
)

# Punjab Labour Welfare Fund Act (Haryana)
from Aapp.app.labour_welfare import list_lwf, add_lwf, alter_lwf, mark_lwf_paid

# Centralised statutory compliance calendar
from Aapp.app.compliance_tracker import (
    compliance_dashboard, list_compliance_items, add_compliance_item,
    alter_compliance_item, mark_compliance_filed, seed_compliance_calendar,
)


def get_districts(request, state_id):
    districts = District.objects.filter(state__Stateid=state_id).order_by('name').values('Districtid', 'name')
    return JsonResponse([{'id': d['Districtid'], 'name': d['name']} for d in districts], safe=False)


app_name = 'Aapp'
# NOTE: this urls.py is loaded directly as the ROOT urlconf for the
# 'aapp' host by django-hosts (see revolution/hosts.py: host 'aapp' ->
# 'Aapp.urls'), not via include(). Django only applies app_name
# namespacing through include(), so 'Aapp:' is NEVER a valid prefix
# here — always use bare names, e.g. redirect('dashboard'),
# {% url 'list_employee' %}. (revolution/urls.py deliberately does NOT
# also include() this module under a path prefix — see the note there.)

urlpatterns = [
    # ── Auth & Dashboard ─────────────────────────────────────────────────────
    path('', views.associate_base_home, name='home'),
    path('login/', views.login, name='associate_login'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.associate_profile, name='associate_profile'),

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
    # WAGES — Form III/17 (Wage Register), Form I (Fines), Form II (Deductions)
    # ════════════════════════════════════════════════════════════════════════
    path('wages/', list_wages, name='list_wages'),
    path('wages/generate/', generate_wages, name='generate_wages'),
    path('wages/update/<int:wages_id>/', update_wages, name='update_wages'),
    path('wages/finalize/<int:wages_id>/', finalize_wages, name='finalize_wages'),
    path('wages/delete/<int:wages_id>/', delete_wages, name='delete_wages'),

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

    path('shops-act/overtime/', list_overtime, name='list_overtime'),
    path('shops-act/overtime/add/', add_overtime, name='add_overtime'),
    path('shops-act/overtime/delete/<int:ot_id>/', delete_overtime, name='delete_overtime'),

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
]
