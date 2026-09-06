from django.urls import path
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
]
