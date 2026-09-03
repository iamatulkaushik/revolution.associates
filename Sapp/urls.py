from django.urls import path
from . import views
from Sapp.app.audit_trail import audit_log_list, audit_log_detail
urlpatterns = [
    # Renamed to sapp_* — 'login'/'logout'/'dashboard' collided with the
    # same names in Aapp.urls. Since both apps are include()'d without a
    # namespace in revolution/urls.py, redirect('dashboard') was resolving
    # to whichever app's URL was registered last, sending Associates into
    # this superadmin-only dashboard and triggering a 403 on every login.
    path('', views.base_home, name="base_home"),
    path('signin/', views.login, name="sapp_login"),
    path('login/', views.login, name="sapp_login"),
    path('logout/', views.logout, name="sapp_logout"),
    path('dashboard/', views.dashboard, name="sapp_dashboard"),
    path('company/list/', views.list_company, name="list_company"),
    path('company/create/', views.create_company, name="create_company"),
    path('company/quick/', views.quick_company, name="quick_company"),
    path('company/alter/<int:company_id>/', views.alter_company, name="alter_company"),
    path('company/<int:company_id>/assign-owner/', views.assign_company_owner, name="assign_company_owner"),
    path('company/shut/<int:company_id>/', views.shut_company, name="shut_company"),
    path('get_districts/<int:state_id>/', views.get_districts, name="get_districts"),
    
    # Associate URLs
    path('users/associate/create/', views.create_associate, name="create_associate"),
    path('users/associate/alter/<int:associate_id>/', views.alter_associate, name="alter_associate"),
    path('users/associate/disable/<int:associate_id>/', views.disable_suspend_associate, name="disable_suspend_associate"),
    path('users/associate/list/', views.list_associates, name="list_associates"),
    path('users/associate/reset-password/<int:associate_id>/', views.reset_associate_password, name="reset_associate_password"),
    
    # Sub User URLs
    # alter_subuser / list_subusers / reset_subuser_password renamed to
    # sapp_* — same cross-app collision issue as login/dashboard/logout
    # above: Aapp.urls registers its own associate-scoped versions of
    # these names, and without a namespace the two were shadowing each
    # other depending on include() order.
    path('users/subuser/create/', views.create_subuser, name="create_subuser"),
    path('users/subuser/create/<int:associate_id>/', views.create_subuser, name="create_subuser_for_associate"),
    path('users/subuser/alter/<int:subuser_id>/', views.alter_subuser, name="sapp_alter_subuser"),
    path('users/subuser/disable/<int:subuser_id>/', views.disable_suspend_subuser, name="disable_suspend_subuser"),
    path('users/subuser/list/', views.list_subusers, name="sapp_list_subusers"),
    path('users/subuser/reset-password/<int:subuser_id>/', views.reset_subuser_password, name="sapp_reset_subuser_password"),
    path('users/subuser/delete/<int:subuser_id>/', views.delete_subuser_account, name="delete_subuser"),
    
    # AJAX URLs
    path('get-associate-companies/<int:associate_id>/', views.get_associate_companies, name="get_associate_companies"),
    path('remove-company-access/<int:company_id>/', views.remove_company_access, name="remove_company_access"),
    path('remove-subuser-company-access/<int:company_id>/', views.remove_subuser_company_access, name="remove_subuser_company_access"),
    
    # License URLs
    path('license/issue/', views.issue_license, name="issue_license"),
    path('license/list/', views.list_licenses, name="list_licenses"),
    path('license/alter/<int:license_id>/', views.alter_license, name="alter_license"),
    path('license/revoke-suspend/<int:license_id>/', views.revoke_suspend_license, name="revoke_suspend_license"),

    # Audit Trail (Sapp-only)
    path('audit/', audit_log_list, name="audit_log_list"),
    path('audit/<int:log_id>/', audit_log_detail, name="audit_log_detail"),
]