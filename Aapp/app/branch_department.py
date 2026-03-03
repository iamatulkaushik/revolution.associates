from django.forms import forms
from django.db import models
from django.shortcuts import render, redirect
from django.contrib.auth.models import User
from django.contrib.auth import authenticate
from django.db import migrations
from Sapp.app.company import Company
from django.shortcuts import get_object_or_404
from django.contrib import messages

# Classes for Branch and Department models in the application. These models represent the structure of the database tables for branches and departments, including fields for branch and department details, as well as metadata for tracking creation and updates.

class branch(models.Model):
    branchid = models.AutoField(primary_key=True)
    branch_name = models.CharField(max_length=255, db_column='Branch_Name', blank=False, null=False)
    branch_code = models.CharField(max_length=50, blank=True, null=True)
    branch_address = models.TextField(blank=True, default='')
    branch_email = models.EmailField(blank=True, default='')
    contact_person = models.CharField(max_length=200, blank=True, null=True)
    Cotact_mobile = models.CharField(max_length=10, blank=True, null=True)
    companyid = models.ForeignKey(Company, on_delete=models.CASCADE)

    created_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.CASCADE, related_name='branches_created')
    updated_by = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE, related_name='branches_updated')
    created_at = models.DateField(auto_now_add=True)
    updated_at = models.DateField(auto_now=True)

    def __str__(self):
        return f'{self.branch_name}'
    
    class Meta:
        db_table = 'branch_table'


class department(models.Model):
    departmentid = models.AutoField(primary_key=True)
    department_name = models.CharField(max_length=255, db_column='Department_Name', blank=False, null=False)
    branch = models.ForeignKey(branch, on_delete=models.CASCADE)
    companyid = models.ForeignKey(Company, on_delete=models.CASCADE) 
    created_by = models.ForeignKey(User, null=False, blank=False, on_delete=models.CASCADE, related_name='departments_created')
    updated_by = models.ForeignKey(User, blank=True, null=True, on_delete=models.CASCADE, related_name='departments_updated')
    created_at = models.DateField(auto_now=True)
    updated_at = models.DateField(auto_now_add=True)

    def __str__(self):
        return f'{self.department_name}'
    
    class Meta:
        db_table = 'department_table'
        unique_together = ('department_name','branch')

# forms for Branch and Department models to handle user input and validation when creating or updating branch and department records in the application.

class branch_form(forms.Form):
    class Meta:
        model = branch
        fields = ['branch_name', 'branch_address', 'branch_email', 'contact_person', 'Cotact_mobile']

class department_form(forms.Form):
    class Meta:
        model = department
        fields = ['department_name', 'branch']


# Views for handling the creation and updating of branch and department records, including form validation and saving the data to the database.

def list_branch(request):
    if not request.selected_company:
        messages.warning(request, 'Please select a company first.')
        return redirect('Aapp:dashboard')
   
    branches = branch.objects.filter(companyid = request.selected_company)
    return render(request, 'Aapp/works/list_branch.html', {'branches': branches})

def create_branch(request):
    if not request.selected_company:
        messages.warning(request, 'Please select a company first.')
        return redirect('Aapp:dashboard')
    form = branch_form()
    if request.method == 'POST':
        form = branch_form(request.POST)
        if form.is_valid():
            branch_instance = form.save(commit=False)
            branch_instance.created_by = request.user
            branch_instance.companyid = request.selected_company  # Set the company
            branch_instance.save()
            messages.success(request, f"Branch '{branch_instance.branch_name}' created successfully.")
            return redirect('branch_list')
    return render(request, 'Aapp/works/create_branch.html', {'form': form})

def alter_branch(request, branch_id):
    branch_instance = get_object_or_404(branch, branchid=branch_id)
    
    if request.method == 'POST':
        branch_instance.branch_name = request.POST.get('branch_name')
        branch_instance.branch_address = request.POST.get('branch_address', '')
        branch_instance.branch_email = request.POST.get('branch_email', '')
        branch_instance.contact_person = request.POST.get('contact_person', '')
        branch_instance.Cotact_mobile = request.POST.get('contact_mobile', '')
        branch_instance.updated_by = request.user
        branch_instance.save()
        messages.success(request, f"Branch '{branch_instance.branch_name}' updated successfully.")
        return redirect('branch_list')
    
    return render(request, 'Aapp/works/alter_branch.html', {'branch': branch_instance})

def delete_branch(request, branch_id):    
    branch_instance = get_object_or_404(branch, branchid=branch_id)
    
    if request.method == 'POST':
        branch_name = branch_instance.branch_name
        branch_instance.delete()
        messages.success(request, f"Branch '{branch_name}' deleted successfully.")
        return redirect('branch_list')
    
    return render(request, 'Aapp/works/delete_branch.html', {'branch': branch_instance})

# Department Views
def create_department(request):
    branches = branch.objects.all()
    companies = Company.objects.all()
    
    if request.method == 'POST':
        department_name = request.POST.get('department_name')
        branch_id = request.POST.get('branch')
        company_id = request.POST.get('company')
        
        if not all([department_name, branch_id, company_id]):
            messages.error(request, "All fields are required.")
        else:
            branch_instance = branch.objects.get(branchid=branch_id)
            company_instance = Company.objects.get(company_id=company_id)
            
            if department.objects.filter(department_name=department_name, branch=branch_instance).exists():
                messages.error(request, f"Department '{department_name}' already exists in this branch.")
            else:
                department.objects.create(
                    department_name=department_name,
                    branch=branch_instance,
                    companyid=company_instance,
                    created_by=request.user
                )
                messages.success(request, f"Department '{department_name}' created successfully.")
                return redirect('department_list')
    
    return render(request, 'Aapp/works/create_department.html', {'branches': branches, 'companies': companies})

def list_department(request):
    if not request.selected_company:
        messages.warning(request, 'Please select a company first.')
        return redirect('Aapp:dashboard')
    
    dprtfilter = department.objects.filter(companyid = request.selected_company)
    #departments = department.objects.filter(Comapny_id = request.selected_company_id)
    return render(request, 'Aapp/works/list_department.html', {'departments': dprtfilter})

def alter_department(request, department_id):

    
    dept_instance = get_object_or_404(department, departmentid=department_id)
    branches = branch.objects.all()
    
    if request.method == 'POST':
        dept_instance.department_name = request.POST.get('department_name')
        branch_id = request.POST.get('branch')
        dept_instance.branch = branch.objects.get(branchid=branch_id)
        dept_instance.updated_by = request.user
        dept_instance.save()
        messages.success(request, f"Department '{dept_instance.department_name}' updated successfully.")
        return redirect('department_list')
    
    return render(request, 'Aapp/works/alter_department.html', {'department': dept_instance, 'branches': branches})

def delete_department(request, department_id):
    from django.shortcuts import get_object_or_404
    from django.contrib import messages
    
    dept_instance = get_object_or_404(department, departmentid=department_id)
    
    if request.method == 'POST':
        dept_name = dept_instance.department_name
        dept_instance.delete()
        messages.success(request, f"Department '{dept_name}' deleted successfully.")
        return redirect('department_list')
    
    return render(request, 'Aapp/works/delete_department.html', {'department': dept_instance})
    
# post migration code to create initial branches and departments for testing purposes. This code defines a function that creates an initial branch and an associated department, and a migration class that runs this function after the initial migration is applied to set up the database with some default data.

def create_initial_branches_and_departments(apps, schema_editor):
    Branch = apps.get_model('Aapp', 'branch')
    Department = apps.get_model('Aapp', 'department')
    # Create initial branches
    branch1 = Branch.objects.create(branch_name='Head Office', branch_code='B001', branch_address='Update_as_company_address', contact_person='Insert owner Name', contact_mobile='9876543210')
    # Create initial departments for Branch 1
    Department.objects.create(department_name='All-in-One', branch=branch1)
    #Department.objects.create(department_name='Finance', branch=branch1)
    #Department.objects.create(department_name='IT', branch=branch1)
    #Department.objects.create(department_name='Marketing', branch=branch1)

class CreateInitialBranchesAndDepartments(migrations.Migration):

    dependencies = [
        ('Aapp', '0001_initial'),
    ]

    operations = [
        migrations.RunPython(create_initial_branches_and_departments),
    ]