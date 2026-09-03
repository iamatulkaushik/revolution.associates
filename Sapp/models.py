from django.db import models
from django.contrib.auth.models import User
from functools import wraps
from django.http import HttpResponseForbidden
from django.shortcuts import redirect
from django.contrib.auth.decorators import login_required

from Sapp.app import bank
from Sapp.app import state_district

# User role choices
USER_ROLES = [
    ('superadmin', 'Super Admin'),
    ('owner', 'Owner'),
    ('associate', 'Associate'),
    ('operator', 'Operator'),
    ('employee', 'Employee'),
]

# Permission definitions for each role
ROLE_PERMISSIONS = {
    'superadmin': {
        'user_management': ['view', 'add', 'change', 'delete'],
        'company': ['view', 'add', 'change', 'delete'],
        'employees': ['view', 'add', 'change', 'delete'],
        'reports': ['view', 'add', 'change', 'delete'],
    },
    'owner': {
        'company': ['view', 'add', 'change'],  # No delete for company details
        'employees': ['view', 'add', 'change', 'delete'],
        'attendance': ['view', 'add', 'change', 'delete'],
        'allowances': ['view', 'add', 'change', 'delete'],
        'deductions': ['view', 'add', 'change', 'delete'],
        'reports': ['view', 'add', 'change', 'delete'],
        'user_management': ['view', 'add', 'change', 'delete'],
    },
    'associate': {
        'company': ['view', 'add', 'change'],
        'employees': ['view', 'add', 'change', 'delete'],
        'attendance': ['view', 'add', 'change', 'delete'],
        'allowances': ['view', 'add', 'change', 'delete'],
        'deductions': ['view', 'add', 'change', 'delete'],
        'user_management': ['view', 'add', 'change', 'delete'],
        'reports': ['view', 'add', 'change', 'delete'],
        # No user_management permissions
    },
    'operator': {
        'employees': ['view', 'add', 'change', 'delete'],
        'attendance': ['view', 'add', 'change', 'delete'],
        'allowances': ['view', 'add', 'change', 'delete'],
        'deductions': ['view', 'add', 'change', 'delete'],
        'reports': ['view'],
        # Only reports permission
    },
    'employee': {
        'reports': ['view'],  # Limited to attendance, salary slip, allowances, deductions
    },
}