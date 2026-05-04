import logging
from django.db import models
from django.contrib.auth.models import User
from Sapp.models import ROLE_PERMISSIONS, USER_ROLES
from Sapp.app.company import Company
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError

logger = logging.getLogger(__name__)


class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    role = models.CharField(max_length=20, choices=USER_ROLES, default='associate')
    mobile = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    email = models.EmailField(blank=True, null=True)
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='created_users')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='updated_users')
    updated_at = models.DateTimeField(auto_now=True)

    is_suspended = models.BooleanField(default=False)
    suspension_end_time = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.user.username} - {self.get_role_display()}'

    def has_permission(self, module, action):
        if self.role in ROLE_PERMISSIONS:
            permissions = ROLE_PERMISSIONS[self.role]
            if module in permissions:
                return action in permissions[module]
        return False

    def get_permissions(self):
        if self.role in ROLE_PERMISSIONS:
            return ROLE_PERMISSIONS[self.role]
        return {}

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

    def can_login(self):
        return self.user.is_active and not self.is_currently_suspended()

    class Meta:
        db_table = 'user_profiles'


class UserActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)
    reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.user.username} - {self.action} at {self.timestamp}'

    class Meta:
        db_table = 'user_activity_logs'
        ordering = ['-timestamp']


class associateuser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='associate_profile')
    associate_id = models.CharField(max_length=50, unique=True)
    companyid = models.ManyToManyField(Company, related_name='associate_company', blank=True)
    company_added_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    mobile = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_suspended = models.BooleanField(default=False)
    suspension_end_time = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.user.username} - {self.associate_id}'

    class Meta:
        db_table = 'associate_users'
        ordering = ['associate_id']

    def get_companies(self):
        return self.companyid.all()

    def add_company(self, company):
        self.companyid.add(company)

    def remove_company(self, company):
        self.companyid.remove(company)

    def suspend_for_24h(self, reason=''):
        self.is_suspended = True
        self.suspension_end_time = timezone.now() + timedelta(hours=24)
        self.suspension_reason = reason
        self.save()
        UserActivityLog.objects.create(
            user=self.user,
            action='Associate suspended for 24 hours',
            reason=reason,
        )

    def disable_permanently(self, reason=''):
        self.is_active = False
        self.user.is_active = False
        self.user.save()
        self.save()
        UserActivityLog.objects.create(
            user=self.user,
            action='Associate disabled permanently',
            reason=reason,
        )

    def enable_user(self, reason=''):
        self.is_active = True
        self.is_suspended = False
        self.suspension_end_time = None
        self.suspension_reason = None
        self.user.is_active = True
        self.user.save()
        self.save()
        UserActivityLog.objects.create(
            user=self.user,
            action='Associate enabled and access restored',
            reason=reason,
        )

    def is_currently_suspended(self):
        if self.is_suspended and self.suspension_end_time:
            if timezone.now() < self.suspension_end_time:
                return True
            self.is_suspended = False
            self.suspension_end_time = None
            self.save()
        return False

    def can_access_system(self):
        return self.is_active and not self.is_currently_suspended()

    def get_status_display(self):
        if not self.is_active:
            return 'Disabled'
        elif self.is_currently_suspended():
            return 'Suspended'
        return 'Active'

    def get_active_licenses(self):
        from Sapp.app.license import License
        return License.objects.filter(associate=self, is_active=True, status='active')

    def get_subusers_count(self):
        return self.sub_users.count()

    def get_active_subusers_count(self):
        return self.sub_users.filter(is_active=True).count()


class SubUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subuser_profile')
    associate = models.ForeignKey(associateuser, on_delete=models.CASCADE, related_name='sub_users')
    role = models.CharField(
        max_length=20,
        choices=[('operator', 'Operator'), ('employee', 'Employee')],
        default='employee',
    )
    mobile = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    companyid = models.ManyToManyField(Company, related_name='subuser_company', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_suspended = models.BooleanField(default=False)
    suspension_end_time = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f'{self.user.username} - {self.associate.associate_id} ({self.role})'

    class Meta:
        db_table = 'sub_users'
        ordering = ['associate__associate_id', 'user__username']

    def clean(self):
        super().clean()
        if self.pk:
            associate_companies = set(self.associate.get_companies())
            subuser_companies = set(self.get_companies())
            if not subuser_companies.issubset(associate_companies):
                raise ValidationError('Sub user can only access companies assigned to their associate.')

    def get_companies(self):
        return self.companyid.all()

    def add_company(self, company):
        if company in self.associate.get_companies():
            self.companyid.add(company)
            return True
        return False

    def remove_company(self, company):
        self.companyid.remove(company)

    def suspend_for_24h(self, reason=''):
        self.is_suspended = True
        self.suspension_end_time = timezone.now() + timedelta(hours=24)
        self.suspension_reason = reason
        self.save()
        UserActivityLog.objects.create(
            user=self.user,
            action='Sub user suspended for 24 hours',
            reason=reason,
        )

    def disable_permanently(self, reason=''):
        self.is_active = False
        self.user.is_active = False
        self.user.save()
        self.save()
        UserActivityLog.objects.create(
            user=self.user,
            action='Sub user disabled permanently',
            reason=reason,
        )

    def enable_user(self, reason=''):
        self.is_active = True
        self.is_suspended = False
        self.suspension_end_time = None
        self.suspension_reason = None
        self.user.is_active = True
        self.user.save()
        self.save()
        UserActivityLog.objects.create(
            user=self.user,
            action='Sub user enabled and access restored',
            reason=reason,
        )

    def is_currently_suspended(self):
        if self.is_suspended and self.suspension_end_time:
            if timezone.now() < self.suspension_end_time:
                return True
            self.is_suspended = False
            self.suspension_end_time = None
            self.save()
        return False

    def can_access_system(self):
        return (
            self.is_active
            and not self.is_currently_suspended()
            and self.associate.can_access_system()
        )

    def get_status_display(self):
        if not self.is_active:
            return 'Disabled'
        elif self.is_currently_suspended():
            return 'Suspended'
        elif not self.associate.can_access_system():
            return 'Associate Restricted'
        return 'Active'

    def get_available_companies(self):
        return self.associate.get_companies()

    def sync_companies_with_associate(self):
        associate_companies = set(self.associate.get_companies())
        current_companies = set(self.get_companies())
        for company in current_companies - associate_companies:
            self.remove_company(company)

    # Fixed: removed duplicate orphaned method block that appeared at module level
    # after can_user_access_system() — those were unreachable dead code.


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def create_associate_user(username, email, first_name, last_name, password,
                          associate_id, mobile=None, address=None, companies=None):
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
        )
        associate = associateuser.objects.create(
            user=user,
            associate_id=associate_id,
            mobile=mobile,
            address=address,
        )
        if companies:
            for company in companies:
                associate.add_company(company)
        UserActivityLog.objects.create(
            user=user,
            action=f'Associate user created with ID: {associate_id}',
        )
        return associate
    except Exception as e:
        if 'user' in locals():
            user.delete()
        raise e


def create_sub_user(username, email, first_name, last_name, password,
                    associate, role='employee', mobile=None, address=None, companies=None):
    try:
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password,
        )
        subuser = SubUser.objects.create(
            user=user,
            associate=associate,
            role=role,
            mobile=mobile,
            address=address,
        )
        if companies:
            associate_companies = set(associate.get_companies())
            for company in companies:
                if company in associate_companies:
                    subuser.add_company(company)
        UserActivityLog.objects.create(
            user=user,
            action=f'Sub user created under associate: {associate.associate_id} with role: {role}',
        )
        return subuser
    except Exception as e:
        if 'user' in locals():
            user.delete()
        raise e


def get_user_type(user):
    if hasattr(user, 'associate_profile'):
        return 'associate', user.associate_profile
    elif hasattr(user, 'subuser_profile'):
        return 'subuser', user.subuser_profile
    elif hasattr(user, 'profile'):
        return 'regular', user.profile
    return 'unknown', None


def can_user_access_system(user):
    """Check whether any type of user is allowed to access the system."""
    user_type, profile = get_user_type(user)
    if user_type == 'associate':
        return profile.can_access_system()
    elif user_type == 'subuser':
        return profile.can_access_system()
    elif user_type == 'regular':
        return profile.can_login() if profile else user.is_active
    # Superusers / staff with no profile fall back to Django's is_active
    return user.is_active


def change_associate_password(associate, new_password):
    user = associate.user
    user.set_password(new_password)
    user.save()
    UserActivityLog.objects.create(user=user, action='Associate password changed')
    return True


def change_subuser_password(subuser, new_password):
    user = subuser.user
    user.set_password(new_password)
    user.save()
    UserActivityLog.objects.create(user=user, action='Sub user password changed')
    return True


def delete_subuser_account(subuser):
    user = subuser.user
    UserActivityLog.objects.create(user=user, action='Sub user account deleted')
    subuser.delete()
    user.delete()
    return True
