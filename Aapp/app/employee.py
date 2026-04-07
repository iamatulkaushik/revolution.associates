from django import forms
from django.db import models
from django.shortcuts import redirect, render, get_object_or_404
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Sapp.app.state_district import State, District
from Sapp.app.bank import bank_name
from Aapp.app.designation import designation
from Aapp.app.branch_department import branch, department

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
    passport_number = models.CharField(max_length=20, db_column="Passport_Number", blank=True)
    passport_expiry = models.DateField(db_column="Passport_Expiry", null=True, blank=True)
    passport_name = models.CharField(max_length=200, db_column="Passport_Name", blank=True)
    driving_license_number = models.CharField(max_length=20, db_column="Driving_License_Number", blank=True)
    driving_license_expiry = models.DateField(db_column="Driving_License_Expiry", null=True, blank=True)
    driving_license_name = models.CharField(max_length=200, db_column="Driving_License_Name", blank=True)
    voterid = models.CharField(max_length=20, db_column="VoterID", blank=True)
    voterid_name = models.CharField(max_length=200, db_column="VoterID_Name", blank=True)
    
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



# ── helpers ──────────────────────────────────────────────────────────────────
def _company_ctx(request):
    """Return selected company or None."""
    cid = request.session.get('selected_company_id')
    if not cid:
        return None
    from Sapp.app.company import Company
    return Company.objects.filter(company_id=cid).first()


def _form_ctx(company):
    """Return dropdowns scoped to selected company."""
    return {
        'designations': designation.objects.filter(company=company, is_active=True, is_deleted=False),
        'branches':     branch.objects.filter(companyid=company),
        'departments':  department.objects.filter(companyid=company),
        'states':       State.objects.all(),
        'banks':        bank_name.objects.all().order_by('name'),
    }


# ── list ─────────────────────────────────────────────────────────────────────
def list_employee(request):
    from django.contrib import messages
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')
    employees = employee.objects.filter(CompanyID=company).select_related(
        'designationID', 'branchID', 'departmentID')
    return render(request, 'Aapp/employees/list_employee.html',
                  {'employees': employees, 'company': company})


# ── create ────────────────────────────────────────────────────────────────────
def create_employee(request):
    from django.contrib import messages
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    ctx = _form_ctx(company)
    ctx['company'] = company

    if request.method == 'POST':
        p = request.POST
        required = ['employeecode', 'name', 'gender', 'dateofbirth', 'mobile',
                    'email', 'aadhar_number', 'aadhar_name', 'bank_name',
                    'bank_account', 'bank_ifsc', 'dateofjoining',
                    'designationID', 'departmentID', 'branchID',
                    'temporaryaddress', 'temp_state', 'temp_district', 'temp_pincode']
        if not all(p.get(f) for f in required):
            messages.error(request, 'All required fields must be filled.')
        elif employee.objects.filter(employeecode=p['employeecode'], CompanyID=company).exists():
            messages.error(request, f"Employee code '{p['employeecode']}' already exists.")
        elif employee.objects.filter(mobile=p['mobile']).exists():
            messages.error(request, 'Mobile number already registered.')
        elif employee.objects.filter(aadhar_number=p['aadhar_number']).exists():
            messages.error(request, 'Aadhaar number already registered.')
        elif p.get('pan_number') and employee.objects.filter(pan_number=p['pan_number']).exists():
            messages.error(request, 'PAN number already registered.')
        elif employee.objects.filter(bank_account=p['bank_account']).exists():
            messages.error(request, 'Bank account already registered.')
        else:
            try:
                same = p.get('same_as_permanent') == 'on'
                employee.objects.create(
                    employeecode   = p['employeecode'],
                    name           = p['name'],
                    fathername     = p.get('fathername', ''),
                    mothername     = p.get('mothername', ''),
                    gender         = p['gender'],
                    dateofbirth    = p['dateofbirth'],
                    bloodgroup     = p.get('bloodgroup', ''),
                    religion       = p.get('religion', ''),
                    maritalstatus  = p.get('maritalstatus', ''),
                    temporaryaddress = p['temporaryaddress'],
                    temp_state_id  = p['temp_state'],
                    temp_district_id = p['temp_district'],
                    temp_pincode   = p['temp_pincode'],
                    same_as_permanent = same,
                    permanentaddress = p['temporaryaddress'] if same else p.get('permanentaddress', ''),
                    perm_state_id  = p['temp_state'] if same else (p.get('perm_state') or None),
                    perm_district_id = p['temp_district'] if same else (p.get('perm_district') or None),
                    perm_pincode   = p['temp_pincode'] if same else p.get('perm_pincode', ''),
                    country        = p.get('country', 'India'),
                    mobile         = p['mobile'],
                    phone          = p.get('phone', ''),
                    email          = p['email'],
                    aadhar_number  = p['aadhar_number'],
                    aadhar_name    = p['aadhar_name'],
                    pan_name       = p.get('pan_name', ''),
                    pan_number     = p.get('pan_number') or None,
                    bank_name      = p['bank_name'],
                    bank_account   = p['bank_account'],
                    bank_ifsc      = p['bank_ifsc'],
                    driving_license_name   = p.get('driving_license_name', ''),
                    driving_license_number = p.get('driving_license_number', ''),
                    driving_license_expiry = p.get('driving_license_expiry') or None,
                    passport_name   = p.get('passport_name', ''),
                    passport_number = p.get('passport_number', ''),
                    passport_expiry = p.get('passport_expiry') or None,
                    dateofjoining  = p['dateofjoining'],
                    uan_number     = p.get('uan_number', ''),
                    uan_doj        = p.get('uan_doj') or None,
                    epf_memberID   = p.get('epf_memberID', ''),
                    epf_higher     = p.get('epf_higher') == 'on',
                    esic_number    = p.get('esic_number', ''),
                    esic_doj       = p.get('esic_doj') or None,
                    labour_id      = p.get('labour_id', ''),
                    designationID_id = p['designationID'],
                    departmentID_id  = p['departmentID'],
                    branchID_id      = p['branchID'],
                    CompanyID        = company,
                )
                messages.success(request, f"Employee '{p['name']}' created successfully.")
                return redirect('Aapp:list_employee')
            except Exception as e:
                messages.error(request, f'Error: {e}')

    return render(request, 'Aapp/employees/create_employee.html', ctx)


# ── alter ─────────────────────────────────────────────────────────────────────
def alter_employee(request, employee_id):
    from django.contrib import messages
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    emp = get_object_or_404(employee, employeeid=employee_id, CompanyID=company)
    ctx = _form_ctx(company)
    ctx.update({'emp': emp, 'company': company})

    if request.method == 'POST':
        p = request.POST
        try:
            same = p.get('same_as_permanent') == 'on'
            emp.name           = p.get('name', emp.name)
            emp.fathername     = p.get('fathername', emp.fathername)
            emp.mothername     = p.get('mothername', emp.mothername)
            emp.gender         = p.get('gender', emp.gender)
            emp.dateofbirth    = p.get('dateofbirth', emp.dateofbirth)
            emp.bloodgroup     = p.get('bloodgroup', emp.bloodgroup)
            emp.religion       = p.get('religion', emp.religion)
            emp.maritalstatus  = p.get('maritalstatus', emp.maritalstatus)
            emp.temporaryaddress = p.get('temporaryaddress', emp.temporaryaddress)
            emp.temp_state_id  = p.get('temp_state', emp.temp_state_id)
            emp.temp_district_id = p.get('temp_district', emp.temp_district_id)
            emp.temp_pincode   = p.get('temp_pincode', emp.temp_pincode)
            emp.same_as_permanent = same
            emp.permanentaddress = p['temporaryaddress'] if same else p.get('permanentaddress', emp.permanentaddress)
            emp.perm_state_id  = p['temp_state'] if same else (p.get('perm_state') or emp.perm_state_id)
            emp.perm_district_id = p['temp_district'] if same else (p.get('perm_district') or emp.perm_district_id)
            emp.perm_pincode   = p['temp_pincode'] if same else p.get('perm_pincode', emp.perm_pincode)
            emp.mobile         = p.get('mobile', emp.mobile)
            emp.phone          = p.get('phone', emp.phone)
            emp.email          = p.get('email', emp.email)
            emp.pan_name       = p.get('pan_name', emp.pan_name)
            emp.pan_number     = p.get('pan_number') or emp.pan_number
            emp.bank_name      = p.get('bank_name', emp.bank_name)
            emp.bank_account   = p.get('bank_account', emp.bank_account)
            emp.bank_ifsc      = p.get('bank_ifsc', emp.bank_ifsc)
            emp.uan_number     = p.get('uan_number', emp.uan_number)
            emp.uan_doj        = p.get('uan_doj') or emp.uan_doj
            emp.epf_memberID   = p.get('epf_memberID', emp.epf_memberID)
            emp.epf_higher     = p.get('epf_higher') == 'on'
            emp.esic_number    = p.get('esic_number', emp.esic_number)
            emp.esic_doj       = p.get('esic_doj') or emp.esic_doj
            emp.labour_id      = p.get('labour_id', emp.labour_id)
            emp.designationID_id = p.get('designationID', emp.designationID_id)
            emp.departmentID_id  = p.get('departmentID', emp.departmentID_id)
            emp.branchID_id      = p.get('branchID', emp.branchID_id)
            emp.save()
            messages.success(request, f"Employee '{emp.name}' updated successfully.")
            return redirect('Aapp:list_employee')
        except Exception as e:
            messages.error(request, f'Error: {e}')

    return render(request, 'Aapp/employees/alter_employee.html', ctx)


# ── disable / enable ──────────────────────────────────────────────────────────
def disable_employee(request, employee_id):
    from django.contrib import messages
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    emp = get_object_or_404(employee, employeeid=employee_id, CompanyID=company)

    if request.method == 'POST':
        action = request.POST.get('action')
        if action == 'disable':
            emp.is_working = False
            emp.save()
            messages.success(request, f"Employee '{emp.name}' disabled.")
        elif action == 'enable':
            emp.is_working = True
            emp.dateofleaving = None
            emp.leaving_reason = ''
            emp.save()
            messages.success(request, f"Employee '{emp.name}' re-enabled.")
        return redirect('Aapp:list_employee')

    return render(request, 'Aapp/employees/disable_employee.html', {'emp': emp})


# ── retire ────────────────────────────────────────────────────────────────────
def retire_employee(request, employee_id):
    from django.contrib import messages
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    emp = get_object_or_404(employee, employeeid=employee_id, CompanyID=company)

    if request.method == 'POST':
        emp.dateofretirement = request.POST.get('dateofretirement') or None
        emp.dateofleaving    = request.POST.get('dateofleaving') or None
        emp.leaving_reason   = request.POST.get('leaving_reason', '')
        emp.is_working       = False
        emp.save()
        messages.success(request, f"Employee '{emp.name}' retired/separated.")
        return redirect('Aapp:list_employee')

    return render(request, 'Aapp/employees/retire_employee.html', {'emp': emp})


# ── delete ────────────────────────────────────────────────────────────────────
def delete_employee(request, employee_id):
    from django.contrib import messages
    company = _company_ctx(request)
    if not company:
        messages.warning(request, 'Please select a company first.')
        return redirect('dashboard')

    emp = get_object_or_404(employee, employeeid=employee_id, CompanyID=company)

    if request.method == 'POST':
        name = emp.name
        emp.delete()
        messages.success(request, f"Employee '{name}' deleted permanently.")
        return redirect('Aapp:list_employee')

    return render(request, 'Aapp/employees/delete_employee.html', {'emp': emp})