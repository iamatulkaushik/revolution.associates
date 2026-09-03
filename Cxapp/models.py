"""
Cxapp/models.py
================
Main model file for the Cxapp (self-signup Company Owner) portal.
Holds only CxOwnerProfile — the root identity for the app.

Sub-users:    Cxapp/app/sub_user.py   (CxSubUser, roles, permissions)
Designations: Cxapp/app/designation.py (CxDesignation, CxDesignationComponent)

Different from Capp:
- Capp: owner profile is created BY an Associate (Aapp), access is
  read-only and flag-gated by the associate.
- Cxapp: owner signs up directly, owns their Company record outright,
  no Associate involvement. Owner gets full read/write and can create
  up to 5 sub-users with role-scoped access.

Locked fields on Company once created via signup: company_name,
start_date, pan, email1, mobile. Enforced in forms/views, not at the
DB layer, since Sapp/Aapp still need normal field access to the same
Company model.
"""

from django.db import models
from django.contrib.auth.models import User
from Sapp.app.company import Company

LOCKED_COMPANY_FIELDS = ('company_name', 'start_date', 'pan', 'email1', 'mobile')
MAX_SUB_USERS = 5


class CxOwnerProfile(models.Model):
    """
    One profile per self-signup company owner.
    Owner has full, unmediated ownership of exactly one company.
    """
    user            = models.OneToOneField(User, on_delete=models.CASCADE,
                                            related_name='cx_owner_profile')
    company         = models.OneToOneField(
                          Company,
                          on_delete=models.CASCADE,
                          related_name='cx_owner',
                          db_column='CompanyID',
                      )
    mobile          = models.CharField(max_length=15)
    is_active       = models.BooleanField(default=True)
    email_verified  = models.BooleanField(default=False)
    last_login_ip   = models.GenericIPAddressField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'cx_owner_profile'
        verbose_name = 'Company Owner (Self-Signup)'
        verbose_name_plural = 'Company Owners (Self-Signup)'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} — {self.company.company_name}'

    def can_access_system(self):
        return self.is_active and self.user.is_active

    def sub_user_slots_remaining(self):
        return MAX_SUB_USERS - self.sub_users.filter(is_active=True).count()


# Imported here (not used directly) so Django's migration autodetector
# discovers every model under the Cxapp app label from this entry point.
from Cxapp.app.sub_user import CxSubUser, SUB_USER_ROLES, ROLE_PERMISSIONS  # noqa: E402,F401
from Cxapp.app.designation import CxDesignation, CxDesignationComponent  # noqa: E402,F401
from Cxapp.app.employee import (  # noqa: E402,F401
    CxEmployee, CxEmployeeAddress, CxEmployeeContact, CxEmployeeStatutory,
    CxEmployeeKYC, CxEmployeeBanking, CxEmployeeEmployment, CxEmployeeNominee,
)
from Cxapp.app.license import CxPlan  # noqa: E402,F401
from Cxapp.app.attandance import CxAttendance, CxAttendanceMaternity  # noqa: E402,F401
from Cxapp.app.process import CxSalary, CxSalaryLine  # noqa: E402,F401
from Cxapp.app.employee_portal import CxEmployeeAuth  # noqa: E402,F401
