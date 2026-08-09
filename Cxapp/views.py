"""
Cxapp/views.py
==============
Main views: signup, login, logout, dashboard, company profile.
Sub-user views live in Cxapp/app/sub_user.py.
Designation views live in Cxapp/app/designation.py.

Auth decorators (cx_login_required, owner_only) are defined here and
imported by the app/ submodules to keep session/company-resolution
logic in one place.
"""

import logging
from functools import wraps

from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.models import User
from django.contrib import messages
from django.db import transaction
from django.shortcuts import render, redirect
from django.views.decorators.debug import sensitive_post_parameters

from Sapp.app.company import Company
from Sapp.app.state_district import District
from Cxapp.models import CxOwnerProfile, LOCKED_COMPANY_FIELDS, MAX_SUB_USERS
from Cxapp.forms import CxSignupForm
from Cxapp.app.license import CxPlan

logger = logging.getLogger(__name__)


# ── Auth decorators (shared with Cxapp/app/*.py) ──────────────────────────────

def cx_login_required(view_func):
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect('cxapp_login')
        if not getattr(request, 'cx_company', None):
            messages.error(request, 'No company account found for this login.')
            return redirect('cxapp_login')
        return view_func(request, *args, **kwargs)
    return _wrapped


def owner_only(view_func):
    """Sub-users cannot access owner-only actions (e.g. managing sub-users)."""
    @wraps(view_func)
    @cx_login_required
    def _wrapped(request, *args, **kwargs):
        if getattr(request, 'cx_sub_user', None) is not None:
            messages.error(request, 'Only the company owner can perform this action.')
            return redirect('cxapp_dashboard')
        return view_func(request, *args, **kwargs)
    return _wrapped


# ── Signup ─────────────────────────────────────────────────────────────────────

@sensitive_post_parameters('password', 'password_confirm')
def cxapp_signup(request):
    if request.method == 'POST':
        form = CxSignupForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data['username'],
                    password=data['password'],
                    email=data['email1'],
                )
                company = Company.objects.create(
                    company_name=data['company_name'],
                    start_date=data['start_date'],
                    pan=data['pan'],
                    email1=data['email1'],
                    mobile=data['mobile'],
                    state_id=data['state_id'],
                    district_id=data['district_id'],
                    address1=data.get('address1', ''),
                    pin=data.get('pin', ''),
                    created_by=data['username'],
                    updated_by=data['username'],
                )
                owner_profile = CxOwnerProfile.objects.create(
                    user=user,
                    company=company,
                    mobile=data['mobile'],
                )
                CxPlan.start_trial(owner_profile)
            auth_login(request, user)
            messages.success(request, f"Welcome, {company.company_name}! Your company account is ready.")
            return redirect('cxapp_dashboard')
    else:
        form = CxSignupForm()

    return render(request, 'Cxapp/signup.html', {'form': form})


# ── Login / Logout ────────────────────────────────────────────────────────────

@sensitive_post_parameters('password')
def cxapp_login(request):
    if request.user.is_authenticated and getattr(request, 'cx_company', None):
        return redirect('cxapp_dashboard')

    if request.method == 'POST':
        username = request.POST.get('username', '')
        password = request.POST.get('password', '')
        user = authenticate(request, username=username, password=password)
        if user is None:
            messages.error(request, 'Invalid username or password.')
            return render(request, 'Cxapp/login.html', {})

        from Cxapp.app.sub_user import CxSubUser
        is_owner = CxOwnerProfile.objects.filter(user=user, is_active=True).exists()
        is_sub = CxSubUser.objects.filter(user=user, is_active=True).exists()
        if not (is_owner or is_sub):
            messages.error(request, 'No company account found for these credentials.')
            return render(request, 'Cxapp/login.html', {})

        auth_login(request, user)
        ip = request.META.get('HTTP_X_FORWARDED_FOR', request.META.get('REMOTE_ADDR', ''))
        if is_owner:
            profile = CxOwnerProfile.objects.get(user=user)
            profile.last_login_ip = ip.split(',')[0].strip() if ip else None
            profile.save(update_fields=['last_login_ip'])
        logger.info("Cxapp login: user='%s'", user.username)
        return redirect('cxapp_dashboard')

    return render(request, 'Cxapp/login.html', {})


def cxapp_logout(request):
    auth_logout(request)
    return redirect('cxapp_login')


# ── Dashboard ─────────────────────────────────────────────────────────────────

@cx_login_required
def cxapp_dashboard(request):
    return render(request, 'Cxapp/dashboard.html', {
        'sub_user_count': request.cx_owner_profile.sub_users.filter(is_active=True).count(),
        'sub_user_max': MAX_SUB_USERS,
    })


# ── Company profile (locked fields excluded) ──────────────────────────────────

@cx_login_required
def cxapp_company_profile(request):
    company = request.cx_company

    if request.method == 'POST' and getattr(request, 'cx_sub_user', None) is None:
        for field in ('tagline1', 'address1', 'address2', 'address3', 'pin',
                      'phone', 'phone2', 'mobile2', 'email2', 'website'):
            if field in LOCKED_COMPANY_FIELDS:
                continue  # never touch locked fields
            setattr(company, field, request.POST.get(field, getattr(company, field, '')))
        company.updated_by = request.user.username
        company.save()
        messages.success(request, 'Company profile updated.')
        return redirect('cxapp_company_profile')

    return render(request, 'Cxapp/company_profile.html', {
        'company': company,
        'locked_fields': LOCKED_COMPANY_FIELDS,
    })


# ── State/District cascading filter ───────────────────────────────────────────
# Shared JSON endpoint used by every form with a state+district pair
# (signup, company profile, employee address). No @cx_login_required —
# this only returns public reference data (district names), and the
# signup form needs it before an owner profile/session exists.

def cxapp_districts_for_state(request):
    from django.http import JsonResponse

    state_id = request.GET.get('state_id')
    if not state_id:
        return JsonResponse({'districts': []})

    districts = District.objects.filter(state_id=state_id).order_by('name').values('Districtid', 'name')
    return JsonResponse({'districts': list(districts)})
