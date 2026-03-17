from django.urls import path
from . import views
from Aapp.app.branch_department import create_branch, list_branch, alter_branch, delete_branch, create_department, list_department, alter_department, delete_department
from Aapp.app.designation import create_designation, list_designation, alter_designation, disable_designation
from Sapp.app.company import create_company_associate, list_company_associate, alter_company_associate, mark_inactive_company, create_company_statutory, alter_company_statutory
from Aapp.app.subuser import list_subusers, add_subuser, alter_subuser, reset_subuser_password, disable_subuser, subuser_companies

app_name = 'Aapp'

urlpatterns = [
    path('', views.login, name='home'),
    path('login/', views.associate_login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('profile/', views.associate_profile, name='associate_profile'),
    path('branch/create/', create_branch, name='create_branch'),
    path('branch/list/', list_branch, name='branch_list'),
    path('branch/alter/<int:branch_id>/', alter_branch, name='alter_branch'),
    path('branch/delete/<int:branch_id>/', delete_branch, name='delete_branch'),
    path('department/create/', create_department, name='create_department'),
    path('department/list/', list_department, name='department_list'),
    path('department/alter/<int:department_id>/', alter_department, name='alter_department'),
    path('department/delete/<int:department_id>/', delete_department, name='delete_department'),
    path('designation/create/', create_designation, name='create_designation'),
    path('designation/list/', list_designation, name='list_designation'),
    path('designation/alter/<int:designation_id>/', alter_designation, name='alter_designation'),
    path('designation/disable/<int:designation_id>/', disable_designation, name='disable_designation'),
    path('company/create/', create_company_associate, name='create_company_associate'),
    path('company/list/', list_company_associate, name='list_company_associate'),
    path('company/alter/<int:company_id>/', alter_company_associate, name='alter_company_associate'),
    path('company/mark-inactive/<int:company_id>/', mark_inactive_company, name='mark_inactive_company'),
    path('company/statutory/create/', create_company_statutory, name='create_company_statutory'),
    path('company/statutory/alter/<int:company_id>/', alter_company_statutory, name='alter_company_statutory'),
    path('api/companies/', views.get_user_companies, name='get_user_companies'),
    path('api/select-company/', views.select_company, name='select_company'),
    path('api/selected-company/', views.get_selected_company, name='get_selected_company'),
    path('subusers/', list_subusers, name='list_subusers'),
    path('subusers/add/', add_subuser, name='add_subuser'),
    path('subusers/alter/<int:subuser_id>/', alter_subuser, name='alter_subuser'),
    path('subusers/reset-password/<int:subuser_id>/', reset_subuser_password, name='reset_subuser_password'),
    path('subusers/disable/<int:subuser_id>/', disable_subuser, name='disable_subuser'),
    path('subusers/companies/<int:subuser_id>/', subuser_companies, name='subuser_companies'),
]