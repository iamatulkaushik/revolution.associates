from django.urls import path
from . import views

app_name = 'Aapp'

urlpatterns = [
    path('', views.login, name='home'),
    path('login/', views.associate_login, name='login'),
    path('logout/', views.logout, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('create_branch/', views.create_branch, name='create_branch'),
    path('branch_list/', views.branch_list, name='branch_list'),
    path('branch_details/', views.branch_details, name='branch_details'),
]