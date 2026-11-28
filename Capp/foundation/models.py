"""Capp/foundation/models.py — operators and audit trail (track AI-1)."""
from django.contrib.auth.models import User
from django.db import models

from Sapp.app.company import Company


class CompanyOperator(models.Model):
    """A data-entry user created by the company owner.

    Duck-types CompanyOwnerProfile (user, company, is_active, can_access_system,
    get_access_flags, can_view_* flags, can_download_pdf, can_manage_masters) so every
    existing Capp view works for operators with their (smaller) flag set.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='operator_profile')
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='operators',
                                db_column='CompanyID')
    is_active = models.BooleanField(default=True)
    suspended_reason = models.CharField(max_length=200, blank=True)
    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='operators_created')
    created_at = models.DateTimeField(auto_now_add=True)
    last_login_ip = models.GenericIPAddressField(null=True, blank=True)

    # read access (same names as the owner profile)
    can_view_employees = models.BooleanField(default=True)
    can_view_attendance = models.BooleanField(default=True)
    can_view_wages = models.BooleanField(default=False)
    can_view_compliance = models.BooleanField(default=False)
    can_view_reports = models.BooleanField(default=False)
    can_view_statutory = models.BooleanField(default=False)
    can_download_pdf = models.BooleanField(default=False)
    # write / action access
    can_add_employees = models.BooleanField(default=False, help_text='Add and edit employees')
    can_edit_attendance = models.BooleanField(default=False)
    can_edit_loans = models.BooleanField(default=False, help_text='Loans and advances')
    can_download_payroll = models.BooleanField(default=False,
                                               help_text='Salary sheet, slips, abstracts')
    can_download_challans = models.BooleanField(default=False)
    can_manage_masters = models.BooleanField(default=False,
                                             help_text='Direct companies only')
    can_manage_billing = models.BooleanField(default=False,
                                             help_text='Direct companies only')

    class Meta:
        app_label = 'Capp'
        db_table = 'ca_company_operator'

    def __str__(self):
        return f'{self.user.get_full_name() or self.user.username} (operator, {self.company})'

    def can_access_system(self):
        return self.is_active and self.user.is_active

    def get_access_flags(self):
        return {
            'employees': self.can_view_employees, 'attendance': self.can_view_attendance,
            'wages': self.can_view_wages, 'compliance': self.can_view_compliance,
            'reports': self.can_view_reports, 'pdf': self.can_download_pdf,
            'statutory': self.can_view_statutory, 'masters': self.can_manage_masters,
        }


class CappAuditLog(models.Model):
    """Who did what. Written through Capp.audit.log_action; never edited."""
    company = models.ForeignKey(Company, on_delete=models.CASCADE, related_name='capp_audit',
                                db_column='CompanyID')
    user = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    username = models.CharField(max_length=150)            # kept even if the user is deleted
    role = models.CharField(max_length=10)                 # OWNER / OPERATOR
    action = models.CharField(max_length=40)
    model = models.CharField(max_length=60, blank=True)
    object_id = models.CharField(max_length=40, blank=True)
    detail = models.CharField(max_length=300, blank=True)
    ip = models.GenericIPAddressField(null=True, blank=True)
    at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        app_label = 'Capp'
        db_table = 'ca_audit_log'
        ordering = ['-at', '-id']
