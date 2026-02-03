from django.db import models
from django.contrib.auth.models import User
from Sapp.models import ROLE_PERMISSIONS, USER_ROLES
from Sapp.app.company import Company

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

    class Meta:
        db_table = 'user_profiles'

class UserActivityLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='activity_logs')
    action = models.CharField(max_length=255)
    timestamp = models.DateTimeField(auto_now_add=True)
    ip_address = models.GenericIPAddressField(blank=True, null=True)

    def __str__(self):
        return f"{self.user.username} - {self.action} at {self.timestamp}"

    class Meta:
        db_table = 'user_activity_logs'
        ordering = ['-timestamp']

class associateuser(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='associate_profile')
    associate_id = models.CharField(max_length=50, unique=True)
    companyid = models.ManyToManyField(Company, on_delete=models.CASCADE, related_name='associate_company')
    company_added_date = models.DateField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.user.username} - {self.associate_id}"
    class Meta:
        db_table = 'associate_users'
        ordering = ['associate_id']
    
    def get_companies(self):
        return self.companyid.all()
    
    def add_company(self, company):
        self.companyid.add(company)