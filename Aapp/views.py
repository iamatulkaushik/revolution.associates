from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from Sapp.app.company import Company
from Sapp.app.user import UserProfile, associateuser, SubUser
from Sapp.app.license import License

# Create your views here.

def associate_login(request):
    return render(request, 'associate_login.html')

class loginForm(AuthenticationForm):
    username = forms.CharField(label="username", max_length=255)
    password = forms.CharField(label="password", widget = forms.PasswordInput)

def login(request):
    if request.method == 'POST':
        form = loginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            auth_login(request,user)
            messages.success(request, "Logged In Success")
            return redirect('dashboard')
    else:
        form = loginForm()
    return render(request, 'associate_login.html', {'form': form})

def logout(request):
    auth_logout(request)
    messages.success(request, "Logged Out Success")
    return redirect('home')

@login_required
def dashboard(request):
    user = request.user
    #company_all = Company.objects.filter(Company_id = request.selected_company_id)
    users_all = UserProfile.objects.all()
    license_all = License.objects.all()
    # associates_all = associateuser.objects.all().select_related('user')[:5]  # Limit to 5 for dashboard
    # subusers_all = SubUser.objects.all().select_related('user', 'associate')[:5]  # Limit to 5 for dashboard
    
    return render(request, "Aapp/dashboard.html", {
        #'CompanyDetails': company_all,
        'UsersDetail': users_all,
        'LicenseDetails': license_all,
        #'associates_list': associates_all,
        #'subusers_list': subusers_all,
        #'associates_count': associateuser.objects.count(),
        #'subusers_count': SubUser.objects.count(),
    })

#branch creation with already existing branch name check and unique branch code generation within selected company
@login_required
def create_branch(request):
    from Aapp.app.branch_department import branch
    companies = Company.objects.all()
    selected_company = None
    branches = []
    
    if request.method == 'POST':
        company_id = request.POST.get('company')
        branch_name = request.POST.get('branch_name')
        branch_address = request.POST.get('branch_address', '')
        branch_email = request.POST.get('branch_email', '')
        contact_person = request.POST.get('contact_person', '')
        contact_mobile = request.POST.get('contact_mobile', '')
        
        if not company_id:
            messages.error(request, "Please select a company.")
        elif not branch_name:
            messages.error(request, "Please enter a branch name.")
        elif Company.objects.filter(company_id=company_id).exists():
            company = Company.objects.get(company_id=company_id)
            if branch.objects.filter(companyid=company, branch_name=branch_name).exists():
                messages.error(request, f"A branch with the name '{branch_name}' already exists in this company.")
            else:
                try:
                    # Generate a unique branch code
                    branch_count = branch.objects.filter(companyid=company).count()
                    branch_code = f"{company.pan[:4]}{branch_count + 1:03d}"
                    # Create the new branch
                    new_branch = branch.objects.create(
                        branch_name=branch_name,
                        branch_code=branch_code,
                        companyid=company,
                        branch_address=branch_address,
                        branch_email=branch_email,
                        contact_person=contact_person,
                        Cotact_mobile=contact_mobile,
                        created_by=request.user
                    )
                    messages.success(request, f"Branch '{branch_name}' created successfully with code '{branch_code}'.")
                except Exception as e:
                    messages.error(request, f"Error creating branch: {str(e)}")
            selected_company = company
            branches = branch.objects.filter(companyid=company)
        else:
            messages.error(request, "Invalid company selection.")
    
    return render(request, 'Aapp/works/create_branch.html', {
        'companies': companies,
        'selected_company': selected_company,
        'branches': branches,
        'companies_count': companies.count()
    })

@login_required
def branch_list(request):
    from Aapp.app.branch_department import branch
    branches = branch.objects.all()
    return render(request, 'Aapp/works/list_branch.html', {'branches': branches})

@login_required
def branch_details(request):
    return render(request, 'Aapp/works/branch_details.html')