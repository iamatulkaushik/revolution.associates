from django.contrib import admin
from .models import CompanyOwnerProfile


@admin.register(CompanyOwnerProfile)
class CompanyOwnerProfileAdmin(admin.ModelAdmin):
    list_display = ('owner_id', 'user', 'company', 'is_active', 'is_suspended')
    search_fields = ('owner_id', 'user__username', 'company__company_name')
    list_filter = ('is_active', 'is_suspended')
