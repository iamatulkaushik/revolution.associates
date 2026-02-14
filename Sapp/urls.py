from django.urls import path
from . import views

urlpatterns = [
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('license_invalid/', views.license_invalid, name='license_invalid_page'),
    path('no_company/', views.no_company, name='no_company_page'),
    path('not_an_associate/', views.not_an_associate, name='not_an_associate_page'),
]
