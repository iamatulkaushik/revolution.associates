from django.urls import path

from . import views

# NOTE: like Aapp.urls, this module is loaded directly as the ROOT urlconf
# for the 'capp' host by django-hosts, not via include(). No app_name
# namespacing — use bare names, e.g. redirect('dashboard').

urlpatterns = [
    path('', views.login_company, name='home'),
    path('login/', views.login_company, name='login_owner'),
    path('logout/', views.logout_company, name='logout_owner'),
    path('dashboard/', views.dashboard, name='company_dashboard'),

    path('company/', views.company_detail, name='company_detail'),
    path('company/edit/', views.company_edit, name='company_edit'),
    path('profile/', views.profile, name='owner_profile'),

    # Generic CRUD — one set of routes serves every registry module.
    path('<slug:slug>/', views.generic_list, name='generic_list'),
    path('<slug:slug>/add/', views.generic_create, name='generic_create'),
    path('<slug:slug>/<int:pk>/edit/', views.generic_update, name='generic_update'),
    path('<slug:slug>/<int:pk>/delete/', views.generic_delete, name='generic_delete'),
]
