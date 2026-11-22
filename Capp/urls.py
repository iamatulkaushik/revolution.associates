from django.urls import include, path
from Capp.views import (
    capp_login, capp_logout, capp_dashboard,
    capp_password_reset_request, capp_password_reset_confirm,
    capp_employee_list, capp_employee_detail,
    capp_attendance_list, capp_overtime_list,
    capp_wages_list, capp_salary_slip_select,
    capp_salary_slip_download, capp_salary_sheet,
    capp_salary_abstract,
    capp_epf_ecr, capp_esi_returns, capp_gratuity,
    capp_bonus, capp_maternity, capp_lwf,
    capp_compliance,
    capp_company_profile_pdf, capp_letterhead,
    capp_grand_total_report, capp_wages_register_report,
    capp_wages_slip_report, capp_wages_slip_bulk_report,
)

# NOTE: Capp/urls.py is the ROOT urlconf for the 'capp' host in django-hosts.
# Use bare URL names (no namespace prefix) — same pattern as Aapp.urls.

from Capp.bank_views import (
    capp_bankformat_list, capp_bankformat_edit, capp_bankformat_delete, capp_bank_file,
)
from Capp.billing_views import (
    capp_deduction_list, capp_deduction_edit, capp_deduction_delete,
    capp_client_list, capp_client_edit, capp_client_delete,
)
from Capp.invoice_views import (
    capp_invoice_list, capp_invoice_generate, capp_invoice_detail,
    capp_invoice_action, capp_invoice_download,
)
from Capp.import_views import capp_import_employees
from Capp.masters import (
    capp_company_details,
    capp_branch_list, capp_branch_edit, capp_branch_delete,
    capp_department_list, capp_department_edit, capp_department_delete,
    capp_designation_list, capp_designation_edit, capp_designation_delete,
)

urlpatterns = [

    # ── Auth ──────────────────────────────────────────────────────────────────
    path('',          capp_login,    name='capp_login'),
    path('login/',    capp_login,    name='capp_login'),
    path('logout/',   capp_logout,   name='capp_logout'),
    path('reset-password/', capp_password_reset_request, name='capp_password_reset_request'),
    path('reset/<str:uidb64>/<str:token>/', capp_password_reset_confirm, name='capp_password_reset_confirm'),

    # ── Dashboard ─────────────────────────────────────────────────────────────
    path('dashboard/', capp_dashboard, name='capp_dashboard'),

    # ── Employees (read-only) ─────────────────────────────────────────────────
    path('employees/',          capp_employee_list,   name='capp_employee_list'),
    path('employees/<int:pk>/', capp_employee_detail, name='capp_employee_detail'),

    # ── Attendance (read-only) ────────────────────────────────────────────────
    path('attendance/',  capp_attendance_list, name='capp_attendance_list'),
    path('overtime/',    capp_overtime_list,   name='capp_overtime_list'),

    # ── Wages & PDF downloads ─────────────────────────────────────────────────
    path('wages/',                               capp_wages_list,           name='capp_wages_list'),
    path('wages/slip/',                          capp_salary_slip_select,   name='capp_salary_slip'),
    path('wages/slip/<int:wages_id>/download/',  capp_salary_slip_download, name='capp_slip_download'),
    path('wages/sheet/',                         capp_salary_sheet,         name='capp_salary_sheet'),
    path('wages/abstract/',                      capp_salary_abstract,      name='capp_salary_abstract'),

    # ── Statutory registers (read-only) ───────────────────────────────────────
    path('statutory/epf/',       capp_epf_ecr,    name='capp_epf_ecr'),
    path('statutory/esi/',       capp_esi_returns, name='capp_esi_returns'),
    path('statutory/gratuity/',  capp_gratuity,   name='capp_gratuity'),
    path('statutory/bonus/',     capp_bonus,       name='capp_bonus'),
    path('statutory/maternity/', capp_maternity,   name='capp_maternity'),
    path('statutory/lwf/',       capp_lwf,         name='capp_lwf'),

    # ── Compliance calendar ───────────────────────────────────────────────────
    path('compliance/', capp_compliance, name='capp_compliance'),

    # ── Reports & Documents ───────────────────────────────────────────────────
    path('reports/company-profile.pdf/',      capp_company_profile_pdf, name='capp_company_profile_pdf'),
    path('reports/letterhead/<str:doc_type>/', capp_letterhead,         name='capp_letterhead'),
    path('reports/grand-total/', capp_grand_total_report, name='capp_grand_total_report'),
    path('reports/wages-register/', capp_wages_register_report, name='capp_wages_register_report'),
    path('reports/wages-slip/<int:slip_id>/', capp_wages_slip_report, name='capp_wages_slip_report'),
    path('reports/wages-slip-bulk/', capp_wages_slip_bulk_report, name='capp_wages_slip_bulk_report'),

    # ── Masters (owner-managed) ──────────────────────────────────────────
    path('masters/company/', capp_company_details, name='capp_company_details'),
    path('masters/branches/', capp_branch_list, name='capp_branch_list'),
    path('masters/branches/add/', capp_branch_edit, name='capp_branch_add'),
    path('masters/branches/<int:pk>/edit/', capp_branch_edit, name='capp_branch_edit'),
    path('masters/branches/<int:pk>/delete/', capp_branch_delete, name='capp_branch_delete'),
    path('masters/departments/', capp_department_list, name='capp_department_list'),
    path('masters/departments/add/', capp_department_edit, name='capp_department_add'),
    path('masters/departments/<int:pk>/edit/', capp_department_edit, name='capp_department_edit'),
    path('masters/departments/<int:pk>/delete/', capp_department_delete, name='capp_department_delete'),
    path('masters/designations/', capp_designation_list, name='capp_designation_list'),
    path('masters/designations/add/', capp_designation_edit, name='capp_designation_add'),
    path('masters/designations/<int:pk>/edit/', capp_designation_edit, name='capp_designation_edit'),
    path('masters/designations/<int:pk>/delete/', capp_designation_delete, name='capp_designation_delete'),
    path('masters/bank-formats/', capp_bankformat_list, name='capp_bankformat_list'),
    path('masters/bank-formats/add/', capp_bankformat_edit, name='capp_bankformat_add'),
    path('masters/bank-formats/<int:pk>/edit/', capp_bankformat_edit, name='capp_bankformat_edit'),
    path('masters/bank-formats/<int:pk>/delete/', capp_bankformat_delete, name='capp_bankformat_delete'),
    path('wages/bank-file/', capp_bank_file, name='capp_bank_file'),
    path('billing/deductions/', capp_deduction_list, name='capp_deduction_list'),
    path('billing/deductions/add/', capp_deduction_edit, name='capp_deduction_add'),
    path('billing/deductions/<int:pk>/edit/', capp_deduction_edit, name='capp_deduction_edit'),
    path('billing/deductions/<int:pk>/delete/', capp_deduction_delete, name='capp_deduction_delete'),
    path('billing/clients/', capp_client_list, name='capp_client_list'),
    path('billing/clients/add/', capp_client_edit, name='capp_client_add'),
    path('billing/clients/<int:pk>/edit/', capp_client_edit, name='capp_client_edit'),
    path('billing/clients/<int:pk>/delete/', capp_client_delete, name='capp_client_delete'),
    path('billing/invoices/', capp_invoice_list, name='capp_invoice_list'),
    path('billing/invoices/generate/', capp_invoice_generate, name='capp_invoice_generate'),
    path('billing/invoices/<int:pk>/', capp_invoice_detail, name='capp_invoice_detail'),
    path('billing/invoices/<int:pk>/do/<str:action>/', capp_invoice_action, name='capp_invoice_action'),
    path('billing/invoices/<int:pk>/download/<str:fmt>/', capp_invoice_download, name='capp_invoice_download'),
    path('masters/import/employees/', capp_import_employees, name='capp_import_employees'),
    path('', include('Capp.entry.urls')),    # ENTRY track
    path('', include('Capp.direct.urls')),   # DIRECT track
]
