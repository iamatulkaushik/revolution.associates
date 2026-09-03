"""
Cxapp/app/sub_user.py
======================
Sub-user regime for the Cxapp (self-signup Company Owner) portal.
Owner may create up to MAX_SUB_USERS sub-users, each with one of
5 roles: HR, Front Desk, Operator, Employee, Recruitment.

Contains model, form, and views — mirrors the Cxapp/app/designation.py
module layout.
"""

from functools import wraps

from django.db import models, transaction
from django.contrib.auth.models import User
from django import forms
from django.contrib import messages
from django.shortcuts import render, redirect, get_object_or_404


SUB_USER_ROLES = [
    ('hr',          'HR'),
    ('front_desk',  'Front Desk'),
    ('operator',    'Operator'),
    ('employee',    'Employee'),
    ('recruitment', 'Recruitment'),
]

# Role → default access flags. Kept simple/coarse; refine per spec later.
ROLE_PERMISSIONS = {
    'hr':          {'employees': True,  'attendance': True,  'wages': True,  'recruitment': False, 'front_desk': False},
    'front_desk':  {'employees': False, 'attendance': True,  'wages': False, 'recruitment': False, 'front_desk': True},
    'operator':    {'employees': False, 'attendance': True,  'wages': False, 'recruitment': False, 'front_desk': False},
    'employee':    {'employees': False, 'attendance': False, 'wages': False, 'recruitment': False, 'front_desk': False},
    'recruitment': {'employees': False, 'attendance': False, 'wages': False, 'recruitment': True,  'front_desk': False},
}


# ── Model ────────────────────────────────────────────────────────────────────

class CxSubUser(models.Model):
    """
    A sub-user created by the owner. Max 5 per owner, one role each
    (role is not unique — owner can have multiple of the same role,
    the cap is on total count, not per-role).
    """
    owner           = models.ForeignKey('Cxapp.CxOwnerProfile', on_delete=models.CASCADE,
                                         related_name='sub_users')
    user            = models.OneToOneField(User, on_delete=models.CASCADE,
                                            related_name='cx_sub_user')
    role            = models.CharField(max_length=20, choices=SUB_USER_ROLES)
    mobile          = models.CharField(max_length=15, blank=True)
    is_active       = models.BooleanField(default=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_sub_user'
        verbose_name = 'Sub User'
        verbose_name_plural = 'Sub Users'

    def __str__(self):
        return f'{self.user.username} ({self.get_role_display()}) — {self.owner.company.company_name}'

    def get_role_permissions(self):
        return ROLE_PERMISSIONS.get(self.role, {})


# ── Form ─────────────────────────────────────────────────────────────────────

class CxSubUserForm(forms.Form):
    """Owner creates a sub-user. Capped at 5 per owner (enforced in view)."""
    username = forms.CharField(max_length=150)
    password = forms.CharField(widget=forms.PasswordInput, min_length=8)
    role     = forms.ChoiceField(choices=SUB_USER_ROLES)
    mobile   = forms.CharField(max_length=15, required=False)

    def clean_username(self):
        username = self.cleaned_data['username']
        if User.objects.filter(username=username).exists():
            raise forms.ValidationError('Username already taken.')
        return username


# ── Views ────────────────────────────────────────────────────────────────────
# Auth decorators re-imported from Cxapp.views to avoid duplicating
# session/company-resolution logic.

def _get_decorators():
    from Cxapp.views import cx_login_required, owner_only
    return cx_login_required, owner_only


def cxapp_sub_user_list(request):
    cx_login_required, owner_only = _get_decorators()
    return owner_only(_sub_user_list)(request)


def _sub_user_list(request):
    from Cxapp.models import MAX_SUB_USERS
    sub_users = request.cx_owner_profile.sub_users.all().order_by('-created_at')
    slots_remaining = request.cx_owner_profile.sub_user_slots_remaining()
    return render(request, 'Cxapp/users/sub_user_list.html', {
        'sub_users': sub_users,
        'slots_remaining': slots_remaining,
        'max_sub_users': MAX_SUB_USERS,
    })


def cxapp_sub_user_create(request):
    _, owner_only = _get_decorators()
    return owner_only(_sub_user_create)(request)


def _sub_user_create(request):
    from Cxapp.models import MAX_SUB_USERS
    owner_profile = request.cx_owner_profile

    if owner_profile.sub_user_slots_remaining() <= 0:
        messages.error(request, f'Sub-user limit reached ({MAX_SUB_USERS} max).')
        return redirect('cxapp_sub_user_list')

    if request.method == 'POST':
        form = CxSubUserForm(request.POST)
        if form.is_valid():
            data = form.cleaned_data
            with transaction.atomic():
                user = User.objects.create_user(
                    username=data['username'],
                    password=data['password'],
                )
                CxSubUser.objects.create(
                    owner=owner_profile,
                    user=user,
                    role=data['role'],
                    mobile=data.get('mobile', ''),
                )
            messages.success(request, f"Sub-user '{data['username']}' created.")
            return redirect('cxapp_sub_user_list')
    else:
        form = CxSubUserForm()

    return render(request, 'Cxapp/users/sub_user_form.html', {
        'form': form,
        'slots_remaining': owner_profile.sub_user_slots_remaining(),
    })


def cxapp_sub_user_deactivate(request, sub_user_id):
    _, owner_only = _get_decorators()
    return owner_only(_sub_user_deactivate)(request, sub_user_id)


def _sub_user_deactivate(request, sub_user_id):
    sub_user = get_object_or_404(CxSubUser, id=sub_user_id, owner=request.cx_owner_profile)
    if request.method == 'POST':
        sub_user.is_active = False
        sub_user.user.is_active = False
        sub_user.user.save(update_fields=['is_active'])
        sub_user.save(update_fields=['is_active'])
        messages.success(request, f"Sub-user '{sub_user.user.username}' deactivated.")
        return redirect('cxapp_sub_user_list')
    return render(request, 'Cxapp/users/sub_user_deactivate.html', {'sub_user': sub_user})
