from django import forms
from django.db import models
from django.shortcuts import redirect, render, get_object_or_404
from django.views import View
from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import Q
from Sapp.app.company import Company
from Sapp.app.state_district import State, District
from Sapp.app.user import UserProfile
from Sapp.app.bank import Bank
from Aapp.app.designation import designation
from Aapp.app.branch_department import branch, department
import csv

class employee(models.Model):
    # Personal data
    employeeid = models.AutoField(primary_key=True)
    employeecode = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=255)
    fathername = models.CharField(max_length=255, blank=True)
    mothername = models.CharField(max_length=255, blank=True)
    gender = models.CharField(max_length=10, choices=[('Male', 'Male'), ('Female', 'Female'), ('Other', 'Other')])
    dateofbirth = models.DateField()
    bloodgroup = models.CharField(max_length=10, blank=True)
    religion = models.CharField(max_length=255, blank=True)
    maritalstatus = models.CharField(max_length=20, choices=[('Single', 'Single'), ('Married', 'Married'), ('Divorced', 'Divorced'), ('Widowed', 'Widowed')], blank=True)
    
    # Temporary Address
    temporaryaddress = models.TextField()
    temp_state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, related_name='temp_employees')
    temp_district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, related_name='temp_employees')
    temp_pincode = models.CharField(max_length=10)
    
    # Permanent Address
    same_as_permanent = models.BooleanField(default=False)
    permanentaddress = models.TextField(blank=True)
    perm_state = models.ForeignKey(State, on_delete=models.SET_NULL, null=True, blank=True, related_name='perm_employees')
    perm_district = models.ForeignKey(District, on_delete=models.SET_NULL, null=True, blank=True, related_name='perm_employees')
    perm_pincode = models.CharField(max_length=10, blank=True)
    
    country = models.CharField(max_length=255, default='India')
    mobile = models.CharField(max_length=20, unique=True)
    phone = models.CharField(max_length=20, blank=True)
    email = models.EmailField()
    
    # KYC Fields
    aadhar_number = models.CharField(max_length=12, db_column='Aadhar_Number', unique=True)
    aadhar_name = models.CharField(max_length=200, db_column='Aadhar_Name')
    pan_name = models.CharField(max_length=200, db_column='PAN_Name', blank=True)
    pan_number = models.CharField(max_length=10, db_column='PAN_Number', blank=True, unique=True, null=True)
    bank_name = models.CharField(max_length=255, db_column="Account_Name")
    bank_account = models.CharField(max_length=20, db_column="Account_number", unique=True)
    bank_ifsc = models.CharField(max_length=11, db_column="Bank_IFSC")
    
    # Employment data
    dateofjoining = models.DateField()
    uan_number = models.CharField(max_length=50, db_column="UAN", blank=True)
    uan_doj = models.DateField(db_column="EPF_Joining", null=True, blank=True)
    epf_memberID = models.CharField(max_length=100, db_column="EPF_MemberID", blank=True)
    epf_higher = models.BooleanField(default=False)
    esic_number = models.CharField(max_length=10, db_column="ESIC", blank=True)
    esic_doj = models.DateField(db_column="ESI_Joining", null=True, blank=True)
    esic_dol_reason = models.CharField(max_length=255, db_column="ESI_Reason", blank=True)
    labour_id = models.CharField(max_length=50, db_column="LabourID", blank=True)
    dateofretirement = models.DateField(null=True, blank=True)
    dateofleaving = models.DateField(null=True, blank=True)
    leaving_reason = models.CharField(max_length=255, db_column="Leaving_Reason", blank=True)
    is_working = models.BooleanField(default=True)
    
    # Foreign keys
    designationID = models.ForeignKey(designation, on_delete=models.PROTECT, db_column="DesignationID")
    departmentID = models.ForeignKey(department, on_delete=models.PROTECT, db_column="DepartmentID")
    branchID = models.ForeignKey(branch, on_delete=models.PROTECT, db_column="BranchID")
    CompanyID = models.ForeignKey(Company, on_delete=models.PROTECT, db_column='CompanyID')
    
    class Meta:
        db_table = 'employee'
        ordering = ['employeeid']

    def __str__(self):
        return f"{self.employeecode} - {self.name}"

# Forms
class EmployeeCompleteForm(forms.ModelForm):
    class Meta:
        model = employee
        fields = '__all__'
        widgets = {
            'dateofbirth': forms.DateInput(attrs={'type': 'date'}),
            'dateofjoining': forms.DateInput(attrs={'type': 'date'}),
            'uan_doj': forms.DateInput(attrs={'type': 'date'}),
            'esic_doj': forms.DateInput(attrs={'type': 'date'}),
            'dateofretirement': forms.DateInput(attrs={'type': 'date'}),
            'dateofleaving': forms.DateInput(attrs={'type': 'date'}),
        }

class EmployeeQuickForm(forms.ModelForm):
    class Meta:
        model = employee
        fields = ['employeecode', 'name', 'gender', 'dateofbirth', 'mobile', 'email', 
                  'aadhar_number', 'aadhar_name', 'bank_name', 'bank_account', 'bank_ifsc',
                  'dateofjoining', 'designationID', 'departmentID', 'branchID', 'CompanyID']
        widgets = {
            'dateofbirth': forms.DateInput(attrs={'type': 'date'}),
            'dateofjoining': forms.DateInput(attrs={'type': 'date'}),
        }

class EmployeeSelfUpdateForm(forms.ModelForm):
    class Meta:
        model = employee
        fields = ['mobile', 'phone', 'email', 'temporaryaddress', 'temp_state', 'temp_district', 
                  'temp_pincode', 'permanentaddress', 'perm_state', 'perm_district', 'perm_pincode',
                  'bank_name', 'bank_account', 'bank_ifsc']

class BulkEmployeeUploadForm(forms.Form):
    csv_file = forms.FileField(label='Upload CSV File', help_text='Upload employee data in CSV format')



# Views
class EmployeeCompleteView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.user_type not in ['associate', 'subuser']:
            return redirect('employee_dashboard')
        form = EmployeeCompleteForm()
        return render(request, 'employee/employee_complete_form.html', {'form': form})

    def post(self, request):
        if request.user.user_type not in ['associate', 'subuser']:
            return redirect('employee_dashboard')
        form = EmployeeCompleteForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('employee_list')
        return render(request, 'employee/employee_complete_form.html', {'form': form})

class EmployeeQuickView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.user_type not in ['associate', 'subuser']:
            return redirect('employee_dashboard')
        form = EmployeeQuickForm()
        return render(request, 'employee/employee_quick_form.html', {'form': form})

    def post(self, request):
        if request.user.user_type not in ['associate', 'subuser']:
            return redirect('employee_dashboard')
        form = EmployeeQuickForm(request.POST)
        if form.is_valid():
            form.save()
            return redirect('employee_list')
        return render(request, 'employee/employee_quick_form.html', {'form': form})

class BulkEmployeeUploadView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.user_type != 'associate':
            return redirect('employee_dashboard')
        form = BulkEmployeeUploadForm()
        return render(request, 'employee/bulk_upload.html', {'form': form})

    def post(self, request):
        if request.user.user_type != 'associate':
            return redirect('employee_dashboard')
        form = BulkEmployeeUploadForm(request.POST, request.FILES)
        if form.is_valid():
            csv_file = request.FILES['csv_file']
            decoded_file = csv_file.read().decode('utf-8').splitlines()
            reader = csv.DictReader(decoded_file)
            for row in reader:
                employee.objects.create(**row)
            return redirect('employee_list')
        return render(request, 'employee/bulk_upload.html', {'form': form})

class EmployeeSelfUpdateView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.user_type != 'employee':
            return redirect('employee_dashboard')
        emp = get_object_or_404(employee, email=request.user.email)
        form = EmployeeSelfUpdateForm(instance=emp)
        return render(request, 'employee/self_update.html', {'form': form})

    def post(self, request):
        if request.user.user_type != 'employee':
            return redirect('employee_dashboard')
        emp = get_object_or_404(employee, email=request.user.email)
        form = EmployeeSelfUpdateForm(request.POST, instance=emp)
        if form.is_valid():
            form.save()
            return redirect('employee_dashboard')
        return render(request, 'employee/self_update.html', {'form': form})

class EmployeeListView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.user_type == 'associate':
            employees = employee.objects.all()
        elif request.user.user_type == 'subuser':
            employees = employee.objects.filter(branchID=request.user.branch)
        else:
            employees = employee.objects.filter(email=request.user.email)
        return render(request, 'employee/employee_list.html', {'employees': employees})

class EmployeeReportView(LoginRequiredMixin, View):
    def get(self, request):
        if request.user.user_type == 'associate':
            employees = employee.objects.all()
            template = 'employee/report_full.html'
        elif request.user.user_type == 'subuser':
            employees = employee.objects.filter(branchID=request.user.branch)
            template = 'employee/report_limited.html'
        else:
            employees = employee.objects.filter(email=request.user.email)
            template = 'employee/report_self.html'
        return render(request, template, {'employees': employees})