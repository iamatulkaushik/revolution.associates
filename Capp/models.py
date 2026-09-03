"""
Capp/models.py
==============
Company Owner portal — model layer.

CompanyOwnerProfile links a Django User to a Company and controls
which Aapp modules the owner can access (read-only by default).
"""

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from Sapp.app.company import Company


class CompanyOwnerProfile(models.Model):
    """
    One profile per company owner.
    An owner is tied to exactly one company.
    Access flags control which sections of the owner portal are visible.
    """
    user            = models.OneToOneField(User, on_delete=models.CASCADE,
                                           related_name='owner_profile')
    # Link to the company this owner belongs to
    company         = models.ForeignKey(
                          Company,
                          on_delete=models.CASCADE,
                          related_name='company_owners',
                          db_column='CompanyID',
                      )

    # Display / contact
    designation     = models.CharField(max_length=100, default='Owner',
                                        help_text='Title shown in portal e.g. Managing Director')
    mobile          = models.CharField(max_length=15, blank=True)

    # Portal access flags — all True by default; associate can restrict
    can_view_employees    = models.BooleanField(default=True)
    can_view_attendance   = models.BooleanField(default=True)
    can_view_wages        = models.BooleanField(default=True)
    can_view_compliance   = models.BooleanField(default=True)
    can_view_reports      = models.BooleanField(default=True)
    can_download_pdf      = models.BooleanField(default=True)
    can_view_statutory    = models.BooleanField(default=True)

    is_active       = models.BooleanField(default=True)
    last_login_ip   = models.GenericIPAddressField(null=True, blank=True)
    created_at      = models.DateTimeField(auto_now_add=True)
    updated_at      = models.DateTimeField(auto_now=True)
    created_by      = models.ForeignKey(User, on_delete=models.SET_NULL, null=True,
                                         related_name='owner_profiles_created')

    class Meta:
        app_label = 'Capp'
        db_table = 'ca_company_owner_profile'
        verbose_name = 'Company Owner'
        verbose_name_plural = 'Company Owners'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} — {self.company.company_name}'

    def can_access_system(self):
        return self.is_active and self.user.is_active

    def get_access_flags(self):
        return {
            'employees':  self.can_view_employees,
            'attendance': self.can_view_attendance,
            'wages':      self.can_view_wages,
            'compliance': self.can_view_compliance,
            'reports':    self.can_view_reports,
            'pdf':        self.can_download_pdf,
            'statutory':  self.can_view_statutory,
        }


# ── Import models from Aapp/Sapp so migrations pick them up ──────────────────
# (Capp reads Aapp data — no new tables needed for those)
# Company imported via ForeignKey string reference above
