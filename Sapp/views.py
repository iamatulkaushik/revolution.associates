from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django import forms
from django.contrib.auth.models import User
from django.db import transaction

from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth import authenticate, login as auth_login
from Sapp.app.company import Company, create_company_form_superadmin
from Sapp.app.user import UserProfile, associateuser, SubUser, create_associate_user, create_sub_user
from Sapp.app.license import License
from Sapp.app.state_district import District

# Create your views here.
def base_home(request):
    return render(request, 'home.html')

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
    return render(request, 'login.html', {'form': form})

def signup(request):
    return render(request, 'signup.html')

@login_required
def dashboard(request):
    user = request.user
    company_all = Company.objects.all()
    users_all = UserProfile.objects.all()
    license_all = License.objects.all()
    associates_all = associateuser.objects.all().select_related('user')[:5]  # Limit to 5 for dashboard
    subusers_all = SubUser.objects.all().select_related('user', 'associate')[:5]  # Limit to 5 for dashboard
    
    return render(request, "Sapp/dashboard.html", {
        'CompanyDetails': company_all,
        'UsersDetail': users_all,
        'LicenseDetails': license_all,
        'associates_list': associates_all,
        'subusers_list': subusers_all,
        'associates_count': associateuser.objects.count(),
        'subusers_count': SubUser.objects.count(),
    })

@login_required
def create_company(request):
    if request.method == 'POST':
        form = create_company_form_superadmin(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company registered successfully!')
            return redirect('list_company')
    else:
        form = create_company_form_superadmin()
    return render(request, 'Sapp/company/create_company.html', {'form': form})

@login_required
def list_company(request):
    companies = Company.objects.all()
    return render(request, 'Sapp/company/list_company.html', {'companies': companies})

@login_required
def alter_company(request, company_id):
    company = get_object_or_404(Company, company_id=company_id)
    if request.method == 'POST':
        form = create_company_form_superadmin(request.POST, instance=company)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company updated successfully!')
            return redirect('list_company')
    else:
        form = create_company_form_superadmin(instance=company)
    return render(request, 'Sapp/company/alter_company.html', {'form': form, 'company': company})

@login_required
def shut_company(request, company_id):
    company = get_object_or_404(Company, company_id=company_id)
    if request.method == 'POST':
        shut_date = request.POST.get('shut_date')
        company.shut_date = shut_date
        company.save()
        messages.success(request, 'Company shut date updated!')
        return redirect('list_company')
    return render(request, 'Sapp/company/shut_company.html', {'company': company})

@login_required
def quick_company(request):
    if request.method == 'POST':
        form = create_company_form_superadmin.quick_company_form(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company created quickly!')
            return redirect('list_company')
    else:
        form = create_company_form_superadmin.quick_company_form()
    
    # Get recent companies for display
    recent_companies = Company.objects.all().order_by('-company_id')[:10]
    
    return render(request, 'Sapp/company/quick_company.html', {
        'form': form,
        'recent_companies': recent_companies
    })

def get_districts(request, state_id):
    try:
        districts = District.objects.filter(state__Stateid=state_id).values('Districtid', 'name')
        return JsonResponse([{'id': d['Districtid'], 'name': d['name']} for d in districts], safe=False)
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

# Associate Management Views
@login_required
def create_associate(request):
    if request.method == 'POST':
        print(f"POST data: {request.POST}")
        try:
            # Validate passwords match
            password1 = request.POST.get('password1')
            password2 = request.POST.get('password2')
            print(f"Password1: {password1}, Password2: {password2}")
            
            if password1 != password2:
                messages.error(request, 'Passwords do not match!')
                companies = Company.objects.all()
                return render(request, 'Sapp/users/create_associate.html', {'companies': companies})
            
            # Check if username already exists
            username = request.POST.get('username')
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists!')
                companies = Company.objects.all()
                return render(request, 'Sapp/users/create_associate.html', {'companies': companies})
            
            # Check if associate_id already exists
            associate_id = request.POST.get('associate_id')
            if associateuser.objects.filter(associate_id=associate_id).exists():
                messages.error(request, 'Associate ID already exists!')
                companies = Company.objects.all()
                return render(request, 'Sapp/users/create_associate.html', {'companies': companies})
            
            print("Starting transaction...")
            with transaction.atomic():
                companies = request.POST.getlist('companies')
                company_objects = Company.objects.filter(id__in=companies) if companies else []
                print(f"Selected companies: {companies}")
                
                associate = create_associate_user(
                    username=username,
                    email=request.POST.get('email'),
                    first_name=request.POST.get('first_name'),
                    last_name=request.POST.get('last_name'),
                    password=password1,
                    associate_id=associate_id,
                    mobile=request.POST.get('mobile'),
                    address=request.POST.get('address'),
                    companies=company_objects
                )
                print(f"Associate created: {associate}")
                messages.success(request, f'Associate {associate.associate_id} created successfully!')
                return redirect('list_associates')
        except Exception as e:
            print(f"Exception occurred: {str(e)}")
            import traceback
            traceback.print_exc()
            messages.error(request, f'Error creating associate: {str(e)}')
    
    companies = Company.objects.all()
    return render(request, 'Sapp/users/create_associate.html', {'companies': companies})

@login_required
def alter_associate(request, associate_id):
    associate = get_object_or_404(associateuser, id=associate_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Update user fields
                associate.user.username = request.POST['username']
                associate.user.email = request.POST['email']
                associate.user.first_name = request.POST['first_name']
                associate.user.last_name = request.POST['last_name']
                associate.user.save()
                
                # Update associate fields
                associate.mobile = request.POST.get('mobile')
                associate.address = request.POST.get('address')
                associate.is_active = request.POST.get('is_active') == 'True'
                associate.save()
                
                # Update companies
                companies = request.POST.getlist('companies')
                if companies:
                    company_objects = Company.objects.filter(id__in=companies)
                    associate.companyid.set(company_objects)
                
                messages.success(request, 'Associate updated successfully!')
                return redirect('list_associates')
        except Exception as e:
            messages.error(request, f'Error updating associate: {str(e)}')
    
    all_companies = Company.objects.all()
    return render(request, 'Sapp/users/alter_associate.html', {
        'associate': associate,
        'all_companies': all_companies
    })

@login_required
def disable_suspend_associate(request, associate_id):
    associate = get_object_or_404(associateuser, id=associate_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('reason', '')
        
        try:
            if action == 'suspend_24h':
                associate.suspend_for_24h(reason)
                messages.success(request, f'Associate suspended for 24 hours.')
            elif action == 'disable':
                associate.disable_permanently(reason)
                messages.success(request, f'Associate disabled permanently.')
            elif action == 'enable':
                associate.enable_user(reason)
                messages.success(request, f'Associate enabled successfully.')
            
            return redirect('list_associates')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return render(request, 'Sapp/users/disable_suspend_associate.html', {'associate': associate})

@login_required
def list_associates(request):
    associates = associateuser.objects.all().select_related('user')
    return render(request, 'Sapp/users/list_associates.html', {'associates': associates})

# Sub User Management Views
@login_required
def create_subuser(request, associate_id=None):
    associate = None
    if associate_id:
        associate = get_object_or_404(associateuser, id=associate_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                associate_obj = get_object_or_404(associateuser, id=request.POST['associate'])
                companies = request.POST.getlist('companies')
                company_objects = Company.objects.filter(id__in=companies) if companies else []
                
                subuser = create_sub_user(
                    username=request.POST['username'],
                    email=request.POST['email'],
                    first_name=request.POST['first_name'],
                    last_name=request.POST['last_name'],
                    password=request.POST['password1'],
                    associate=associate_obj,
                    role=request.POST['role'],
                    mobile=request.POST.get('mobile'),
                    address=request.POST.get('address'),
                    companies=company_objects
                )
                messages.success(request, f'Sub user created successfully under {associate_obj.associate_id}!')
                return redirect('list_subusers')
        except Exception as e:
            messages.error(request, f'Error creating sub user: {str(e)}')
    
    associates = associateuser.objects.filter(is_active=True)
    return render(request, 'Sapp/users/create_subuser.html', {
        'associates': associates,
        'associate': associate
    })

@login_required
def alter_subuser(request, subuser_id):
    subuser = get_object_or_404(SubUser, id=subuser_id)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                # Update user fields
                subuser.user.username = request.POST['username']
                subuser.user.email = request.POST['email']
                subuser.user.first_name = request.POST['first_name']
                subuser.user.last_name = request.POST['last_name']
                subuser.user.save()
                
                # Update subuser fields
                subuser.mobile = request.POST.get('mobile')
                subuser.address = request.POST.get('address')
                subuser.role = request.POST['role']
                subuser.is_active = request.POST.get('is_active') == 'True'
                
                # Update associate if changed
                new_associate = get_object_or_404(associateuser, id=request.POST['associate'])
                subuser.associate = new_associate
                subuser.save()
                
                # Update companies (only those available through associate)
                companies = request.POST.getlist('companies')
                if companies:
                    company_objects = Company.objects.filter(
                        id__in=companies
                    ).filter(
                        id__in=new_associate.companyid.values_list('id', flat=True)
                    )
                    subuser.companyid.set(company_objects)
                
                messages.success(request, 'Sub user updated successfully!')
                return redirect('list_subusers')
        except Exception as e:
            messages.error(request, f'Error updating sub user: {str(e)}')
    
    associates = associateuser.objects.filter(is_active=True)
    return render(request, 'Sapp/users/alter_subuser.html', {
        'subuser': subuser,
        'associates': associates
    })

@login_required
def disable_suspend_subuser(request, subuser_id):
    subuser = get_object_or_404(SubUser, id=subuser_id)
    
    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('reason', '')
        
        try:
            if action == 'suspend_24h':
                subuser.suspend_for_24h(reason)
                messages.success(request, f'Sub user suspended for 24 hours.')
            elif action == 'disable':
                subuser.disable_permanently(reason)
                messages.success(request, f'Sub user disabled permanently.')
            elif action == 'enable':
                subuser.enable_user(reason)
                messages.success(request, f'Sub user enabled successfully.')
            
            return redirect('list_subusers')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    
    return render(request, 'Sapp/users/disable_suspend_subuser.html', {'subuser': subuser})

@login_required
def list_subusers(request):
    subusers = SubUser.objects.all().select_related('user', 'associate__user')
    return render(request, 'Sapp/users/list_subusers.html', {'subusers': subusers})

# AJAX Views
@login_required
def get_associate_companies(request, associate_id):
    try:
        associate = get_object_or_404(associateuser, id=associate_id)
        companies = associate.get_companies().values('id', 'company_name', 'pan')
        return JsonResponse({'companies': list(companies)})
    except Exception as e:
        return JsonResponse({'error': str(e)}, status=500)

@login_required
def remove_company_access(request, company_id):
    if request.method == 'POST':
        try:
            # This would be called from alter_associate.html
            # You'd need to pass associate_id in the request or session
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)

@login_required
def remove_subuser_company_access(request, company_id):
    if request.method == 'POST':
        try:
            # This would be called from alter_subuser.html
            # You'd need to pass subuser_id in the request or session
            return JsonResponse({'success': True})
        except Exception as e:
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request'}, status=400)