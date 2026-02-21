"""
URL configuration for revolution project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django_hosts import patterns, host
from django.urls import path, include
from django.views.generic import RedirectView
from Sapp.views import base_home
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

urlpatterns = [
    path('',base_home, name="base"),
    path('baseurls/', admin.site.urls),
    path('admin/', include('Sapp.urls')),
    path('associate/',include('Aapp.urls')),
]
host_patterns = patterns('',
    host(r'www', 'revolution.urls', name='www'),
    host(r'associate', 'Aapp.urls', name='associate'),
    host(r'admin', 'Sapp.urls', name='admin'),
    host(r'api', 'api.urls', name='api'),
)

urlpatterns + staticfiles_urlpatterns()