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
from Sapp.app.associate_public import associate_public_profile
from django.contrib.staticfiles.urls import staticfiles_urlpatterns
<<<<<<< HEAD
from Sapp.app.marketing import (
    features, pricing, compliance, about, contact, contact_submit,
    robots_txt, sitemap_xml,
)
=======

>>>>>>> 64b858f0873133802dd58c98471a21d54a13f576
urlpatterns = [
    path('',base_home, name="base"),
    path('baseurls/', admin.site.urls),
    path('admin/', include('Sapp.urls')),
    path('associate/',include('Aapp.urls')),
    path('capp/',include('Capp.urls')),
    path('associates/<slug:slug>/', associate_public_profile, name='associate_public_profile'),
<<<<<<< HEAD
    path('features/', features, name='features'),
    path('pricing/', pricing, name='pricing'),
    path('compliance/', compliance, name='compliance'),
    path('about/', about, name='about'),
    path('contact/', contact, name='contact'),
    path('contact/submit/', contact_submit, name='contact_submit'),
    path('robots.txt', robots_txt, name='robots_txt'),
    path('sitemap.xml', sitemap_xml, name='sitemap_xml'),
=======
>>>>>>> 64b858f0873133802dd58c98471a21d54a13f576
]
urlpatterns += staticfiles_urlpatterns()

host_patterns = patterns('',
    host(r'www', 'revolution.urls', name='www'),
    host(r'associate', 'Aapp.urls', name='associate'),
    host(r'admin', 'Sapp.urls', name='admin'),
    host(r'company', 'Capp.urls', name='company'),
)
