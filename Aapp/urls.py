from django.urls import path
from . import views
from Aapp.app.branch_department import alter_branch, delete_branch, create_department, list_department, alter_department, delete_department
from Sapp.app.company import select_company, get_user_companies, get_selected_company

app_name = 'Aapp'

urlpatterns = [
    path('', views.login, name='home'),
    path('login/', views.associate_login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('branch/create/', views.create_branch, name='create_branch'),
    path('branch/list/', views.branch_list, name='branch_list'),
    path('branch/alter/<int:branch_id>/', alter_branch, name='alter_branch'),
    path('branch/delete/<int:branch_id>/', delete_branch, name='delete_branch'),
    path('department/create/', create_department, name='create_department'),
    path('department/list/', list_department, name='department_list'),
    path('department/alter/<int:department_id>/', alter_department, name='alter_department'),
    path('department/delete/<int:department_id>/', delete_department, name='delete_department'),
    # Company Selector URLs
    path('company/select/', select_company, name='select_company'),
    path('company/list/', get_user_companies, name='get_user_companies'),
    path('company/selected/', get_selected_company, name='get_selected_company'),
]