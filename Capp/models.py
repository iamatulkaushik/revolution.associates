from datetime import date

from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from datetime import timedelta

from Sapp.app.company import Company


class CompanyOwnerProfile(models.Model):
    """
    Scopes a single Django User to exactly one Company. This is the
    Capp equivalent of Sapp.app.user.associateuser, except an owner
    is bound to one company only (no company switching).
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='company_owner_profile')
    company = models.OneToOneField(Company, on_delete=models.CASCADE, related_name='owner_profile')
    owner_id = models.CharField(max_length=50, unique=True)
    mobile = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)

    is_suspended = models.BooleanField(default=False)
    suspension_end_time = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True, null=True)

    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='owners_created')
    created_at = models.DateTimeField(default=timezone.now)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'company_owner_profiles'
        ordering = ['owner_id']

    def __str__(self):
        return f'{self.user.username} - {self.company.company_name}'

    def suspend_for_24h(self, reason=''):
        self.is_suspended = True
        self.suspension_end_time = timezone.now() + timedelta(hours=24)
        self.suspension_reason = reason
        self.save()

    def is_currently_suspended(self):
        if self.is_suspended and self.suspension_end_time:
            if timezone.now() < self.suspension_end_time:
                return True
            self.is_suspended = False
            self.suspension_end_time = None
            self.save()
        return False

    def can_access_system(self):
        return self.is_active and self.user.is_active and not self.is_currently_suspended()

    def get_status_display(self):
        if not self.is_active:
            return 'Disabled'
        elif self.is_currently_suspended():
            return 'Suspended'
        return 'Active'
