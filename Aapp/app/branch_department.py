from django import forms
from django.db import models
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company


class branch(models.Model):
    branchid = models.AutoField(primary_key=True)
    branch_name = models.CharField(max_length=255, db_column='Branch_Name', blank=False, null=False)
    branch_code = models.CharField(max_length=50, blank=True, null=True)
    branch_address = models.TextField(blank=True, default='')
    branch_email = models.EmailField(blank=True, default='')
    contact_person = models.CharField(max_length=200, blank=True, null=True)
    # Fixed: was 'Cotact_mobile' (typo). See migration 0006_rename_cotact_mobile.
    contact_mobile = models.CharField(max_length=10, blank=True, null=True)
    companyid = models.ForeignKey(Company, on_delete=models.CASCADE)

    created_by = models.ForeignKey(
        User, null=True, blank=True, on_delete=models.CASCADE, related_name='branches_created'
    )
    updated_by = models.ForeignKey(
        User, blank=True, null=True, on_delete=models.CASCADE, related_name='branches_updated'
    )
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)

    def __str__(self):
        return self.branch_name

    class Meta:
        db_table = 'branch_table'


class department(models.Model):
    departmentid = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=255, db_column='Department_Name', blank=False, null=False)
    branch = models.ForeignKey(branch, on_delete=models.CASCADE)
    companyid = models.ForeignKey(Company, on_delete=models.CASCADE)
    created_by = models.ForeignKey(
        User, null=False, blank=False, on_delete=models.CASCADE, related_name='departments_created'
    )
    updated_by = models.ForeignKey(
        User, blank=True, null=True, on_delete=models.CASCADE, related_name='departments_updated'
    )
    created_at = models.DateField(auto_now=True)
    updated_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return self.department_name

    class Meta:
        db_table = 'department_table'
        unique_together = ('department_name', 'branch')


class branch_form(forms.ModelForm):
    class Meta:
        model = branch
        fields = ['branch_name', 'branch_address', 'branch_email', 'contact_person', 'contact_mobile']


class department_form(forms.ModelForm):
    class Meta:
        model = department
        fields = ['department_name', 'branch', 'companyid']


# ---------------------------------------------------------------------------
# Branch views
# ---------------------------------------------------------------------------

@login_required
def create_branch(request):
    user = request.user
    if hasattr(user, 'associate_profile'):
        companies = user.associate_profile.companyid.all()
    elif hasattr(user, 'subuser_profile'):
        companies = user.subuser_profile.companyid.all()
    elif user.is_superuser:
        companies = Company.objects.all()
    else:
        companies = Company.objects.none()
    if request.method == 'POST':
        form = branch_form(request.POST)
        company_id = request.POST.get('companyid')
        company = get_object_or_404(Company, company_id=company_id)
        if form.is_valid():
            b = form.save(commit=False)
            b.companyid = company
            b.created_by = request.user
            b.save()
            messages.success(request, f"Branch '{b.branch_name}' created.")
            return redirect('branch_list')
    else:
        form = branch_form()
    return render(request, 'Aapp/works/create_branch.html', {'form': form, 'companies': companies})


@login_required
def list_branch(request):
    branches = branch.objects.select_related('companyid').all()
    return render(request, 'Aapp/works/list_branch.html', {'branches': branches})


@login_required
def alter_branch(request, branch_id):
    b = get_object_or_404(branch, branchid=branch_id)
    if request.method == 'POST':
        form = branch_form(request.POST, instance=b)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.updated_by = request.user
            updated.save()
            messages.success(request, 'Branch updated.')
            return redirect('branch_list')
    else:
        form = branch_form(instance=b)
    return render(request, 'Aapp/works/alter_branch.html', {'form': form, 'branch': b})


@login_required
def delete_branch(request, branch_id):
    b = get_object_or_404(branch, branchid=branch_id)
    if request.method == 'POST':
        b.delete()
        messages.success(request, 'Branch deleted.')
        return redirect('Aapp:branch_list')
    return render(request, 'Aapp/works/delete_branch.html', {'branch': b})


# ---------------------------------------------------------------------------
# Department views
# ---------------------------------------------------------------------------

@login_required
def create_department(request):
    company_id = request.session.get('selected_company_id')
    company = get_object_or_404(Company, company_id=company_id) if company_id else None
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('aapp_dashboard')
    if request.method == 'POST':
        department_name = request.POST.get('department_name')
        branch_id = request.POST.get('branch')
        b = get_object_or_404(branch, branchid=branch_id, companyid=company)
        department.objects.create(
            department_name=department_name,
            branch=b,
            companyid=company,
            created_by=request.user,
        )
        messages.success(request, f"Department '{department_name}' created.")
        return redirect('department_list')
    branches = branch.objects.filter(companyid=company)
    return render(request, 'Aapp/works/create_department.html', {
        'selected_company': company,
        'branches': branches,
    })


@login_required
def list_department(request):
    departments = department.objects.select_related('branch', 'companyid').all()
    return render(request, 'Aapp/works/list_department.html', {'departments': departments})


@login_required
def alter_department(request, department_id):
    d = get_object_or_404(department, departmentid=department_id)
    if request.method == 'POST':
        form = department_form(request.POST, instance=d)
        if form.is_valid():
            updated = form.save(commit=False)
            updated.updated_by = request.user
            updated.save()
            messages.success(request, 'Department updated.')
            return redirect('Aapp:department_list')
    else:
        form = department_form(instance=d)
    return render(request, 'Aapp/works/alter_department.html', {'form': form, 'department': d})


@login_required
def delete_department(request, department_id):
    d = get_object_or_404(department, departmentid=department_id)
    if request.method == 'POST':
        d.delete()
        messages.success(request, 'Department deleted.')
        return redirect('Aapp:department_list')
    return render(request, 'Aapp/works/delete_department.html', {'department': d})