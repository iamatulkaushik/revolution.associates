from django.contrib import admin
from .models import CompanyOwnerProfile


@admin.register(CompanyOwnerProfile)
class CompanyOwnerProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'company', 'is_active')
    search_fields = ('owner_id', 'user__username', 'company__company_name')
