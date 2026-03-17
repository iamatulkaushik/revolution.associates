from django.db import models
from django.contrib.auth.models import User
from Sapp.models import ROLE_PERMISSIONS, USER_ROLES
from Sapp.app.company import Company
from django.utils import timezone
from datetime import timedelta
from django.core.exceptions import ValidationError


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
    
    # Suspension fields
    is_suspended = models.BooleanField(default=False)
    suspension_end_time = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.get_role_display()}"

    def has_permission(self, module, action):
        """Check if user has permission for a specific module and action"""
        if self.role in ROLE_PERMISSIONS:
            permissions = ROLE_PERMISSIONS[self.role]
            if module in permissions:
                return action in permissions[module]
        return False

    def get_permissions(self):
        """Get all permissions for the user's role"""
        if self.role in ROLE_PERMISSIONS:
            return ROLE_PERMISSIONS[self.role]
        return {}
    
    def suspend_for_24h(self, reason=""):
        """Suspend user for 24 hours"""
        self.is_suspended = True
        self.suspension_end_time = timezone.now() + timedelta(hours=24)
        self.suspension_reason = reason
        self.save()
    
    def is_currently_suspended(self):
        """Check if user is currently suspended"""
        if self.is_suspended and self.suspension_end_time:
            if timezone.now() < self.suspension_end_time:
                return True
            else:
                # Auto-unsuspend if time has passed
                self.is_suspended = False
                self.suspension_end_time = None
                self.save()
        return False
    
    def can_login(self):
        """Check if user can login (not suspended and active)"""
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
        return f"{self.user.username} - {self.action} at {self.timestamp}"

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
    
    # Suspension fields
    is_suspended = models.BooleanField(default=False)
    suspension_end_time = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.associate_id}"
    
    class Meta:
        db_table = 'associate_users'
        ordering = ['associate_id']
    
    def get_companies(self):
        return self.companyid.all()
    
    def add_company(self, company):
        self.companyid.add(company)
    
    def remove_company(self, company):
        self.companyid.remove(company)
    
    def suspend_for_24h(self, reason=""):
        """Suspend associate for 24 hours"""
        self.is_suspended = True
        self.suspension_end_time = timezone.now() + timedelta(hours=24)
        self.suspension_reason = reason
        self.save()
        
        # Log the action
        UserActivityLog.objects.create(
            user=self.user,
            action=f"Associate suspended for 24 hours",
            reason=reason
        )
    
    def disable_permanently(self, reason=""):
        """Disable associate permanently"""
        self.is_active = False
        self.user.is_active = False
        self.user.save()
        self.save()
        
        # Log the action
        UserActivityLog.objects.create(
            user=self.user,
            action=f"Associate disabled permanently",
            reason=reason
        )
    
    def enable_user(self, reason=""):
        """Enable associate and restore access"""
        self.is_active = True
        self.is_suspended = False
        self.suspension_end_time = None
        self.suspension_reason = None
        self.user.is_active = True
        self.user.save()
        self.save()
        
        # Log the action
        UserActivityLog.objects.create(
            user=self.user,
            action=f"Associate enabled and access restored",
            reason=reason
        )
    
    def is_currently_suspended(self):
        """Check if associate is currently suspended"""
        if self.is_suspended and self.suspension_end_time:
            if timezone.now() < self.suspension_end_time:
                return True
            else:
                # Auto-unsuspend if time has passed
                self.is_suspended = False
                self.suspension_end_time = None
                self.save()
        return False
    
    def can_access_system(self):
        """Check if associate can access system"""
        return self.is_active and not self.is_currently_suspended()
    
    def get_status_display(self):
        """Get human readable status"""
        if not self.is_active:
            return "Disabled"
        elif self.is_currently_suspended():
            return "Suspended"
        else:
            return "Active"
    
    def get_active_licenses(self):
        """Get all active licenses for this associate"""
        from Sapp.app.license import License
        return License.objects.filter(associate=self, is_active=True, status='active')
    
    def get_subusers_count(self):
        """Get total subusers count"""
        return self.sub_users.count()
    
    def get_active_subusers_count(self):
        """Get active subusers count"""
        return self.sub_users.filter(is_active=True).count()

class SubUser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='subuser_profile')
    associate = models.ForeignKey(associateuser, on_delete=models.CASCADE, related_name='sub_users')
    role = models.CharField(max_length=20, choices=[('operator', 'Operator'), ('employee', 'Employee')], default='employee')
    mobile = models.CharField(max_length=15, blank=True, null=True)
    address = models.TextField(blank=True, null=True)
    companyid = models.ManyToManyField(Company, related_name='subuser_company', blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Suspension fields
    is_suspended = models.BooleanField(default=False)
    suspension_end_time = models.DateTimeField(null=True, blank=True)
    suspension_reason = models.TextField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.associate.associate_id} ({self.role})"
    
    class Meta:
        db_table = 'sub_users'
        ordering = ['associate__associate_id', 'user__username']
    
    def clean(self):
        """Validate that sub user companies are subset of associate companies"""
        super().clean()
        if self.pk:  # Only validate if object exists (for updates)
            associate_companies = set(self.associate.get_companies())
            subuser_companies = set(self.get_companies())
            if not subuser_companies.issubset(associate_companies):
                raise ValidationError("Sub user can only access companies assigned to their associate.")
    
    def get_companies(self):
        """Get companies assigned to this sub user"""
        return self.companyid.all()
    
    def add_company(self, company):
        """Add company access to sub user (only if associate has access)"""
        if company in self.associate.get_companies():
            self.companyid.add(company)
            return True
        return False
    
    def remove_company(self, company):
        """Remove company access from sub user"""
        self.companyid.remove(company)
    
    def suspend_for_24h(self, reason=""):
        """Suspend sub user for 24 hours"""
        self.is_suspended = True
        self.suspension_end_time = timezone.now() + timedelta(hours=24)
        self.suspension_reason = reason
        self.save()
        
        # Log the action
        UserActivityLog.objects.create(
            user=self.user,
            action=f"Sub user suspended for 24 hours",
            reason=reason
        )
    
    def disable_permanently(self, reason=""):
        """Disable sub user permanently"""
        self.is_active = False
        self.user.is_active = False
        self.user.save()
        self.save()
        
        # Log the action
        UserActivityLog.objects.create(
            user=self.user,
            action=f"Sub user disabled permanently",
            reason=reason
        )
    
    def enable_user(self, reason=""):
        """Enable sub user and restore access"""
        self.is_active = True
        self.is_suspended = False
        self.suspension_end_time = None
        self.suspension_reason = None
        self.user.is_active = True
        self.user.save()
        self.save()
        
        # Log the action
        UserActivityLog.objects.create(
            user=self.user,
            action=f"Sub user enabled and access restored",
            reason=reason
        )
    
    def is_currently_suspended(self):
        """Check if sub user is currently suspended"""
        if self.is_suspended and self.suspension_end_time:
            if timezone.now() < self.suspension_end_time:
                return True
            else:
                # Auto-unsuspend if time has passed
                self.is_suspended = False
                self.suspension_end_time = None
                self.save()
        return False
    
    def can_access_system(self):
        """Check if sub user can access system (depends on both sub user and associate status)"""
        return (self.is_active and 
                not self.is_currently_suspended() and 
                self.associate.can_access_system())
    
    def get_status_display(self):
        """Get human readable status"""
        if not self.is_active:
            return "Disabled"
        elif self.is_currently_suspended():
            return "Suspended"
        elif not self.associate.can_access_system():
            return "Associate Restricted"
        else:
            return "Active"
    
    def get_available_companies(self):
        """Get companies available for assignment (from associate)"""
        return self.associate.get_companies()
    
    def sync_companies_with_associate(self):
        """Remove companies that are no longer available through associate"""
        associate_companies = set(self.associate.get_companies())
        current_companies = set(self.get_companies())
        
        # Remove companies that associate no longer has access to
        companies_to_remove = current_companies - associate_companies
        for company in companies_to_remove:
            self.remove_company(company)


# Utility functions for user management
def create_associate_user(username, email, first_name, last_name, password, associate_id, mobile=None, address=None, companies=None):
    """Create a new associate user with all required fields"""
    try:
        # Create Django User
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password
        )
        
        # Create Associate profile
        associate = associateuser.objects.create(
            user=user,
            associate_id=associate_id,
            mobile=mobile,
            address=address
        )
        
        # Add companies if provided
        if companies:
            for company in companies:
                associate.add_company(company)
        
        # Log the creation
        UserActivityLog.objects.create(
            user=user,
            action=f"Associate user created with ID: {associate_id}"
        )
        
        return associate
    except Exception as e:
        # Clean up if user was created but associate creation failed
        if 'user' in locals():
            user.delete()
        raise e


def create_sub_user(username, email, first_name, last_name, password, associate, role='employee', mobile=None, address=None, companies=None):
    """Create a new sub user attached to an associate"""
    try:
        # Create Django User
        user = User.objects.create_user(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            password=password
        )
        
        # Create SubUser profile
        subuser = SubUser.objects.create(
            user=user,
            associate=associate,
            role=role,
            mobile=mobile,
            address=address
        )
        
        # Add companies if provided (only those available through associate)
        if companies:
            associate_companies = set(associate.get_companies())
            for company in companies:
                if company in associate_companies:
                    subuser.add_company(company)
        
        # Log the creation
        UserActivityLog.objects.create(
            user=user,
            action=f"Sub user created under associate: {associate.associate_id} with role: {role}"
        )
        
        return subuser
    except Exception as e:
        # Clean up if user was created but subuser creation failed
        if 'user' in locals():
            user.delete()
        raise e


def get_user_type(user):
    """Determine user type (associate, subuser, or regular)"""
    if hasattr(user, 'associate_profile'):
        return 'associate', user.associate_profile
    elif hasattr(user, 'subuser_profile'):
        return 'subuser', user.subuser_profile
    elif hasattr(user, 'profile'):
        return 'regular', user.profile
    else:
        return 'unknown', None


def can_user_access_system(user):
    """Check if any type of user can access the system"""
    user_type, profile = get_user_type(user)
    
    if user_type == 'associate':
        return profile.can_access_system()
    elif user_type == 'subuser':
        return profile.can_access_system()
    elif user_type == 'regular':
        return profile.can_login() if profile else user.is_active
    else:
        return user.is_active
            
    def get_status_display(self):
        """Get human readable status"""
        if not self.is_active:
            return "Disabled"
        elif self.is_currently_suspended():
            return "Suspended"
        elif not self.associate.can_access_system():
            return "Associate Restricted"
        else:
            return "Active"
    
    def get_available_companies(self):
        """Get companies available for assignment (from associate)"""
        return self.associate.get_companies()
    
    def sync_companies_with_associate(self):
        """Remove companies that are no longer available through associate"""
        associate_companies = set(self.associate.get_companies())
        current_companies = set(self.get_companies())
        
        # Remove companies that associate no longer has access to
        companies_to_remove = current_companies - associate_companies
        for company in companies_to_remove:
            self.remove_company(company)

# utility function to change associate user password
def change_associate_password(associate, new_password):
    """Change password for associate user"""
    user = associate.user
    user.set_password(new_password)
    user.save()
    
    # Log the action
    UserActivityLog.objects.create(
        user=user,
        action=f"Associate password changed"
    )
    
    return True

#utility function to change sub user password
def change_subuser_password(subuser, new_password):
    """Change password for sub user"""
    user = subuser.user
    user.set_password(new_password)
    user.save()
    
    # Log the action
    UserActivityLog.objects.create(
        user=user,
        action=f"Sub user password changed"
    )
    
    return True

#utilty function to delete sub user account completly
def delete_subuser_account(subuser):
    """Delete sub user account completely"""
    user = subuser.user
    username = user.username

    # Log the deletion
    UserActivityLog.objects.create(
        user=user,
        action=f"Sub user account deleted"
    )

    # Delete the subuser profile
    subuser.delete()

    # Delete the Django user
    user.delete()

    return True
