import logging
import uuid
from datetime import datetime

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django import forms
from django.contrib.auth.models import User
from django.db import transaction
from django.contrib.auth.forms import AuthenticationForm
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.views.decorators.debug import sensitive_post_parameters

from Sapp.app.company import Company, create_company_form_superadmin
from Sapp.app.user import (
    UserProfile, associateuser, SubUser,
    create_associate_user, create_sub_user,
    delete_subuser_account as _delete_subuser_account,
    can_user_access_system,
)
from Sapp.app.license import License
from Sapp.app.state_district import District
from Sapp.decorators import superadmin_required
from Capp.models import CompanyOwnerProfile

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Public views (no auth required)
# ---------------------------------------------------------------------------

def base_home(request):
    from django.conf import settings
    parent_host = getattr(settings, 'PARENT_HOST', 'localhost:8000')
    associate_login_url = f'http://aapp.{parent_host}/login/'
    return render(request, 'home.html', {'associate_login_url': associate_login_url})


class loginForm(AuthenticationForm):
    username = forms.CharField(label='Username', max_length=255)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)


@sensitive_post_parameters('password')
def login(request):
    if request.method == 'POST':
        form = loginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # Fixed: enforce suspension / disabled check at login time
            if not can_user_access_system(user):
                messages.error(request, 'Your account is suspended or disabled. Please contact support.')
                return render(request, 'login.html', {'form': form})

            # Only superusers may access the Sapp panel
            if not user.is_superuser:
                messages.error(request, 'You do not have permission to access this panel.')
                return render(request, 'login.html', {'form': form})

            auth_login(request, user)
            logger.info("Superadmin login: user='%s'", user.username)
            messages.success(request, 'Logged in successfully.')
            return redirect('sapp_dashboard')
    else:
        form = loginForm()
    return render(request, 'login.html', {'form': form})


def signup(request):
    return render(request, 'signup.html')


def logout(request):
    username = request.user.username if request.user.is_authenticated else 'unknown'
    auth_logout(request)
    logger.info("Superadmin logout: user='%s'", username)
    messages.success(request, 'Logged out successfully.')
    return redirect('../signin')


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@superadmin_required
def dashboard(request):
    company_all = Company.objects.all()
    users_all = UserProfile.objects.all()
    license_all = License.objects.all()
    associates_all = associateuser.objects.all().select_related('user')[:5]
    subusers_all = SubUser.objects.all().select_related('user', 'associate')[:5]

    return render(request, 'Sapp/dashboard.html', {
        'CompanyDetails': company_all,
        'UsersDetail': users_all,
        'LicenseDetails': license_all,
        'associates_list': associates_all,
        'subusers_list': subusers_all,
        'associates_count': associateuser.objects.count(),
        'subusers_count': SubUser.objects.count(),
    })


# ---------------------------------------------------------------------------
# Company management
# ---------------------------------------------------------------------------

@superadmin_required
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


@superadmin_required
def list_company(request):
    companies = Company.objects.all()
    return render(request, 'Sapp/company/list_company.html', {'companies': companies})


@superadmin_required
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
        current_owner = CompanyOwnerProfile.objects.filter(company=company).select_related('user').first()
        eligible_users = User.objects.filter(
            company_owner_profile__isnull=True,
            is_superuser=False,
            profile__isnull=False,
            profile__role__in=['owner']
        ).order_by('username')
    if current_owner:
        eligible_users = (eligible_users | User.objects.filter(pk=current_owner.user_id)).order_by('username')
    return render(request, 'Sapp/company/alter_company.html', {
        'form': form,
        'company': company,
        'current_owner': current_owner,
        'eligible_users': eligible_users,
    })


@superadmin_required
def assign_company_owner(request, company_id):
    company = get_object_or_404(Company, company_id=company_id)
    profile = CompanyOwnerProfile.objects.filter(company=company).select_related('user').first()

    if request.method != 'POST':
        return redirect('alter_company', company_id=company_id)

    mode = request.POST.get('mode', 'existing')
    owner_id = request.POST.get('owner_id', '').strip()
    mobile = request.POST.get('mobile', '').strip()

    try:
        with transaction.atomic():
            if mode == 'new':
                username = request.POST.get('username', '').strip()
                password1 = request.POST.get('password1', '')
                password2 = request.POST.get('password2', '')

                if not username or not password1:
                    messages.error(request, 'Username and password are required.')
                    return redirect('alter_company', company_id=company_id)
                if password1 != password2:
                    messages.error(request, 'Passwords do not match!')
                    return redirect('alter_company', company_id=company_id)
                if User.objects.filter(username=username).exists():
                    messages.error(request, 'Username already exists!')
                    return redirect('alter_company', company_id=company_id)
                try:
                    validate_password(password1)
                except ValidationError as ve:
                    for error in ve.messages:
                        messages.error(request, error)
                    return redirect('alter_company', company_id=company_id)

                user = User.objects.create_user(
                    username=username,
                    password=password1,
                    email=request.POST.get('email', ''),
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                )
            else:
                user_id = request.POST.get('user_id')
                if not user_id:
                    messages.error(request, 'Select a user to assign as owner.')
                    return redirect('alter_company', company_id=company_id)
                user = get_object_or_404(User, pk=user_id)
                existing = CompanyOwnerProfile.objects.filter(user=user).exclude(company=company).first()
                if existing:
                    messages.error(request, f'{user.username} already owns {existing.company.company_name}.')
                    return redirect('alter_company', company_id=company_id)

            if not owner_id:
                owner_id = f'OWN-{company.company_id:04d}'
            if CompanyOwnerProfile.objects.filter(owner_id=owner_id).exclude(company=company).exists():
                messages.error(request, f'Owner ID "{owner_id}" is already in use.')
                return redirect('alter_company', company_id=company_id)

            if profile:
                profile.user = user
                profile.owner_id = owner_id
                profile.mobile = mobile or profile.mobile
                profile.is_active = True
                profile.save()
                messages.success(request, f'{user.username} is now the owner of {company.company_name}.')
            else:
                CompanyOwnerProfile.objects.create(
                    user=user, company=company, owner_id=owner_id,
                    mobile=mobile, created_by=request.user,
                )
                messages.success(request, f'{user.username} assigned as owner of {company.company_name}.')
    except Exception:
        logger.exception('Failed to assign company owner for company_id=%s', company_id)
        messages.error(request, 'Could not assign owner. Please check the details and try again.')

    return redirect('alter_company', company_id=company_id)


@superadmin_required
def shut_company(request, company_id):
    company = get_object_or_404(Company, company_id=company_id)
    if request.method == 'POST':
        shut_date = request.POST.get('shut_date')
        company.shut_date = shut_date
        company.save()
        messages.success(request, 'Company shut date updated!')
        return redirect('list_company')
    return render(request, 'Sapp/company/shut_company.html', {'company': company})


@superadmin_required
def quick_company(request):
    if request.method == 'POST':
        form = create_company_form_superadmin.quick_company_form(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Company created quickly!')
            return redirect('list_company')
    else:
        form = create_company_form_superadmin.quick_company_form()

    recent_companies = Company.objects.all().order_by('-company_id')[:10]
    return render(request, 'Sapp/company/quick_company.html', {
        'form': form,
        'recent_companies': recent_companies,
    })


# Fixed: added @superadmin_required
@superadmin_required
def get_districts(request, state_id):
    try:
        districts = District.objects.filter(state__Stateid=state_id).values('Districtid', 'name')
        return JsonResponse([{'id': d['Districtid'], 'name': d['name']} for d in districts], safe=False)
    except Exception as e:
        logger.error("get_districts error for state_id=%s: %s", state_id, e)
        return JsonResponse({'error': 'Unable to fetch districts.'}, status=500)


# ---------------------------------------------------------------------------
# Associate management
# ---------------------------------------------------------------------------

@superadmin_required
def create_associate(request):
    if request.method == 'POST':
        try:
            password1 = request.POST.get('password1', '')
            password2 = request.POST.get('password2', '')

            # Fixed: removed print(password1, password2) — never log passwords
            if password1 != password2:
                messages.error(request, 'Passwords do not match!')
                return render(request, 'Sapp/users/create_associate.html', {'companies': Company.objects.all()})

            username = request.POST.get('username', '').strip()
            if User.objects.filter(username=username).exists():
                messages.error(request, 'Username already exists!')
                return render(request, 'Sapp/users/create_associate.html', {'companies': Company.objects.all()})

            associate_id = request.POST.get('associate_id', '').strip()
            if associateuser.objects.filter(associate_id=associate_id).exists():
                messages.error(request, 'Associate ID already exists!')
                return render(request, 'Sapp/users/create_associate.html', {'companies': Company.objects.all()})

            # Fixed: validate password strength via AUTH_PASSWORD_VALIDATORS
            try:
                validate_password(password1)
            except ValidationError as ve:
                for error in ve.messages:
                    messages.error(request, error)
                return render(request, 'Sapp/users/create_associate.html', {'companies': Company.objects.all()})

            with transaction.atomic():
                company_ids = [c for c in request.POST.getlist('companies') if c]
                associate = create_associate_user(
                    username=username,
                    email=request.POST.get('email', ''),
                    first_name=request.POST.get('first_name', ''),
                    last_name=request.POST.get('last_name', ''),
                    password=password1,
                    associate_id=associate_id,
                    mobile=request.POST.get('mobile'),
                    address=request.POST.get('address'),
                    companies=None,
                )
                if company_ids:
                    company_objects = Company.objects.filter(company_id__in=company_ids)
                    associate.companyid.set(company_objects)

            logger.info("Associate created: id='%s' by superadmin='%s'", associate_id, request.user.username)
            messages.success(request, f'Associate {associate.associate_id} created successfully!')
            return redirect('list_associates')

        except Exception as e:
            logger.exception("Error creating associate: %s", e)
            messages.error(request, f'Error creating associate: {e}')

    companies = Company.objects.all()
    return render(request, 'Sapp/users/create_associate.html', {'companies': companies})


@superadmin_required
def alter_associate(request, associate_id):
    associate = get_object_or_404(associateuser, id=associate_id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                associate.user.username = request.POST['username']
                associate.user.email = request.POST['email']
                associate.user.first_name = request.POST['first_name']
                associate.user.last_name = request.POST['last_name']
                associate.user.save()

                associate.mobile = request.POST.get('mobile')
                associate.address = request.POST.get('address')
                associate.is_active = request.POST.get('is_active') == 'True'
                associate.save()

                company_ids = [c for c in request.POST.getlist('companies') if c]
                if company_ids:
                    company_objects = Company.objects.filter(company_id__in=company_ids)
                    associate.companyid.set(company_objects)

            messages.success(request, 'Associate updated successfully!')
            return redirect('list_associates')
        except Exception as e:
            logger.exception("Error updating associate id=%s: %s", associate_id, e)
            messages.error(request, f'Error updating associate: {e}')

    all_companies = Company.objects.all()
    return render(request, 'Sapp/users/alter_associate.html', {
        'associate': associate,
        'all_companies': all_companies,
    })


@superadmin_required
def disable_suspend_associate(request, associate_id):
    associate = get_object_or_404(associateuser, id=associate_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('reason', '')

        try:
            if action == 'suspend_24h':
                associate.suspend_for_24h(reason)
                messages.success(request, 'Associate suspended for 24 hours.')
            elif action == 'disable':
                associate.disable_permanently(reason)
                messages.success(request, 'Associate disabled permanently.')
            elif action == 'enable':
                associate.enable_user(reason)
                messages.success(request, 'Associate enabled successfully.')
            logger.info(
                "Associate action '%s' on id=%s by superadmin='%s'",
                action, associate_id, request.user.username,
            )
            return redirect('list_associates')
        except Exception as e:
            logger.exception("Associate action error: %s", e)
            messages.error(request, f'Error: {e}')

    return render(request, 'Sapp/users/disable_suspend_associate.html', {'associate': associate})


@superadmin_required
def list_associates(request):
    associates = associateuser.objects.all().select_related('user')
    return render(request, 'Sapp/users/list_associates.html', {'associates': associates})


@superadmin_required
def associate_profile(request, associate_id):
    associate = get_object_or_404(associateuser, id=associate_id)
    licenses = License.objects.filter(associate=associate).select_related('company')
    subusers_count = SubUser.objects.filter(associate=associate).count()
    active_subusers = SubUser.objects.filter(associate=associate, is_active=True).count()
    companies = associate.get_companies()

    if request.method == 'POST':
        try:
            associate.user.first_name = request.POST.get('first_name', '')
            associate.user.last_name = request.POST.get('last_name', '')
            associate.user.email = request.POST.get('email', '')
            associate.mobile = request.POST.get('mobile', '')
            associate.address = request.POST.get('address', '')
            associate.user.save()
            associate.save()
            messages.success(request, 'Profile updated successfully!')
            return redirect('associate_profile', associate_id=associate_id)
        except Exception as e:
            messages.error(request, f'Error updating profile: {e}')

    return render(request, 'Sapp/users/associate_profile.html', {
        'associate': associate,
        'licenses': licenses,
        'subusers_count': subusers_count,
        'active_subusers': active_subusers,
        'companies': companies,
    })


@superadmin_required
def reset_associate_password(request, associate_id):
    associate = get_object_or_404(associateuser, id=associate_id)

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match!')
        else:
            # Fixed: validate strength via AUTH_PASSWORD_VALIDATORS
            try:
                validate_password(new_password, user=associate.user)
                associate.user.set_password(new_password)
                associate.user.save()
                logger.info(
                    "Password reset for associate id=%s by superadmin='%s'",
                    associate_id, request.user.username,
                )
                messages.success(request, f'Password reset successfully for {associate.user.username}!')
                return redirect('alter_associate', associate_id=associate_id)
            except ValidationError as ve:
                for error in ve.messages:
                    messages.error(request, error)

    return render(request, 'Sapp/users/reset_password.html', {
        'user_obj': associate,
        'user_type': 'Associate',
        'redirect_url': 'alter_associate',
    })


# ---------------------------------------------------------------------------
# Sub User management
# ---------------------------------------------------------------------------

@superadmin_required
def create_subuser(request, associate_id=None):
    associate = None
    if associate_id:
        associate = get_object_or_404(associateuser, id=associate_id)

    if request.method == 'POST':
        try:
            password1 = request.POST.get('password1', '')

            # Fixed: validate password strength
            try:
                validate_password(password1)
            except ValidationError as ve:
                for error in ve.messages:
                    messages.error(request, error)
                associates = associateuser.objects.filter(is_active=True)
                return render(request, 'Sapp/users/create_subuser.html', {
                    'associates': associates, 'associate': associate,
                })

            with transaction.atomic():
                associate_obj = get_object_or_404(associateuser, id=request.POST['associate'])
                company_ids = [c for c in request.POST.getlist('companies') if c]
                company_objects = Company.objects.filter(company_id__in=company_ids) if company_ids else []

                subuser = create_sub_user(
                    username=request.POST['username'],
                    email=request.POST['email'],
                    first_name=request.POST['first_name'],
                    last_name=request.POST['last_name'],
                    password=password1,
                    associate=associate_obj,
                    role=request.POST['role'],
                    mobile=request.POST.get('mobile'),
                    address=request.POST.get('address'),
                    companies=company_objects,
                )
            messages.success(request, f'Sub user created successfully under {associate_obj.associate_id}!')
            return redirect('sapp_list_subusers')
        except Exception as e:
            logger.exception("Error creating sub user: %s", e)
            messages.error(request, f'Error creating sub user: {e}')

    associates = associateuser.objects.filter(is_active=True)
    return render(request, 'Sapp/users/create_subuser.html', {
        'associates': associates,
        'associate': associate,
    })


@superadmin_required
def alter_subuser(request, subuser_id):
    subuser = get_object_or_404(SubUser, id=subuser_id)

    if request.method == 'POST':
        try:
            with transaction.atomic():
                subuser.user.username = request.POST['username']
                subuser.user.email = request.POST['email']
                subuser.user.first_name = request.POST['first_name']
                subuser.user.last_name = request.POST['last_name']
                subuser.user.save()

                subuser.mobile = request.POST.get('mobile')
                subuser.address = request.POST.get('address')
                subuser.role = request.POST['role']
                subuser.is_active = request.POST.get('is_active') == 'True'

                new_associate = get_object_or_404(associateuser, id=request.POST['associate'])
                subuser.associate = new_associate
                subuser.save()

                company_ids = [c for c in request.POST.getlist('companies') if c]
                if company_ids:
                    company_objects = Company.objects.filter(
                        company_id__in=company_ids
                    ).filter(
                        company_id__in=new_associate.companyid.values_list('company_id', flat=True)
                    )
                    subuser.companyid.set(company_objects)

            messages.success(request, 'Sub user updated successfully!')
            return redirect('sapp_list_subusers')
        except Exception as e:
            logger.exception("Error updating sub user id=%s: %s", subuser_id, e)
            messages.error(request, f'Error updating sub user: {e}')

    associates = associateuser.objects.filter(is_active=True)
    return render(request, 'Sapp/users/alter_subuser.html', {
        'subuser': subuser,
        'associates': associates,
    })


@superadmin_required
def disable_suspend_subuser(request, subuser_id):
    subuser = get_object_or_404(SubUser, id=subuser_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('reason', '')

        try:
            if action == 'suspend_24h':
                subuser.suspend_for_24h(reason)
                messages.success(request, 'Sub user suspended for 24 hours.')
            elif action == 'disable':
                subuser.disable_permanently(reason)
                messages.success(request, 'Sub user disabled permanently.')
            elif action == 'enable':
                subuser.enable_user(reason)
                messages.success(request, 'Sub user enabled successfully.')
            return redirect('sapp_list_subusers')
        except Exception as e:
            logger.exception("Subuser action error: %s", e)
            messages.error(request, f'Error: {e}')

    return render(request, 'Sapp/users/disable_suspend_subuser.html', {'subuser': subuser})


@superadmin_required
def delete_subuser_account(request, subuser_id):
    subuser = get_object_or_404(SubUser, id=subuser_id)
    if request.method == 'POST':
        username = subuser.user.username
        try:
            _delete_subuser_account(subuser)
            logger.info("Sub user '%s' deleted by superadmin='%s'", username, request.user.username)
            messages.success(request, f"Sub user '{username}' deleted successfully.")
        except Exception as e:
            logger.exception("Error deleting sub user: %s", e)
            messages.error(request, f'Error deleting sub user: {e}')
        return redirect('sapp_list_subusers')
    return render(request, 'Sapp/users/delete_subuser.html', {'subuser': subuser})


@superadmin_required
def list_subusers(request):
    subusers = SubUser.objects.all().select_related('user', 'associate__user')
    return render(request, 'Sapp/users/list_subusers.html', {'subusers': subusers})


@superadmin_required
def reset_subuser_password(request, subuser_id):
    subuser = get_object_or_404(SubUser, id=subuser_id)

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_password = request.POST.get('confirm_password', '')

        if new_password != confirm_password:
            messages.error(request, 'Passwords do not match!')
        else:
            # Fixed: validate strength via AUTH_PASSWORD_VALIDATORS
            try:
                validate_password(new_password, user=subuser.user)
                subuser.user.set_password(new_password)
                subuser.user.save()
                messages.success(request, f'Password reset successfully for {subuser.user.username}!')
                return redirect('sapp_alter_subuser', subuser_id=subuser_id)
            except ValidationError as ve:
                for error in ve.messages:
                    messages.error(request, error)

    return render(request, 'Sapp/users/reset_password.html', {
        'user_obj': subuser,
        'user_type': 'Sub User',
        'redirect_url': 'alter_subuser',
    })


# ---------------------------------------------------------------------------
# AJAX views
# ---------------------------------------------------------------------------

@superadmin_required
def get_associate_companies(request, associate_id):
    try:
        associate = get_object_or_404(associateuser, id=associate_id)
        companies = associate.get_companies().values('company_id', 'company_name', 'pan')
        return JsonResponse({'companies': list(companies)})
    except Exception as e:
        logger.error("get_associate_companies error: %s", e)
        return JsonResponse({'error': str(e)}, status=500)


@superadmin_required
def remove_company_access(request, company_id):
    """Fixed: actually removes company access from the given associate."""
    if request.method == 'POST':
        try:
            associate_id = request.POST.get('associate_id')
            if not associate_id:
                return JsonResponse({'error': 'associate_id is required'}, status=400)
            associate = get_object_or_404(associateuser, id=associate_id)
            company = get_object_or_404(Company, company_id=company_id)
            associate.remove_company(company)
            logger.info(
                "Company id=%s removed from associate id=%s by superadmin='%s'",
                company_id, associate_id, request.user.username,
            )
            return JsonResponse({'success': True})
        except Exception as e:
            logger.exception("remove_company_access error: %s", e)
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)


@superadmin_required
def remove_subuser_company_access(request, company_id):
    """Fixed: actually removes company access from the given sub user."""
    if request.method == 'POST':
        try:
            subuser_id = request.POST.get('subuser_id')
            if not subuser_id:
                return JsonResponse({'error': 'subuser_id is required'}, status=400)
            subuser = get_object_or_404(SubUser, id=subuser_id)
            company = get_object_or_404(Company, company_id=company_id)
            subuser.remove_company(company)
            logger.info(
                "Company id=%s removed from sub user id=%s by superadmin='%s'",
                company_id, subuser_id, request.user.username,
            )
            return JsonResponse({'success': True})
        except Exception as e:
            logger.exception("remove_subuser_company_access error: %s", e)
            return JsonResponse({'error': str(e)}, status=500)
    return JsonResponse({'error': 'Invalid request method'}, status=400)


# ---------------------------------------------------------------------------
# License management
# ---------------------------------------------------------------------------

@superadmin_required
def issue_license(request):
    if request.method == 'POST':
        try:
            company = get_object_or_404(Company, company_id=request.POST['company'])
            associate_id = request.POST.get('associate')
            associate = get_object_or_404(associateuser, id=associate_id) if associate_id else None

            license_key = request.POST.get('license_key') or str(uuid.uuid4())[:16].upper()
            issue_date = datetime.strptime(request.POST['issue_date'], '%Y-%m-%d').date()

            license = License.objects.create(
                company=company,
                associate=associate,
                license_key=license_key,
                license_type=request.POST['license_type'],
                issue_date=issue_date,
                max_users=request.POST.get('max_users', 5),
            )
            logger.info("License '%s' issued by superadmin='%s'", license.license_key, request.user.username)
            messages.success(request, f'License {license.license_key} issued successfully!')
            return redirect('list_licenses')
        except Exception as e:
            logger.exception("Error issuing license: %s", e)
            messages.error(request, f'Error issuing license: {e}')

    companies = Company.objects.all()
    associates = associateuser.objects.filter(is_active=True)
    return render(request, 'Sapp/license/issue_license.html', {
        'companies': companies,
        'associates': associates,
    })


@superadmin_required
def list_licenses(request):
    licenses = License.objects.all().select_related('company', 'associate__user')
    return render(request, 'Sapp/license/list_licenses.html', {'licenses': licenses})


@superadmin_required
def alter_license(request, license_id):
    license = get_object_or_404(License, license_id=license_id)

    if request.method == 'POST':
        try:
            associate_id = request.POST.get('associate')
            license.associate = get_object_or_404(associateuser, id=associate_id) if associate_id else None
            license.license_type = request.POST['license_type']
            license.max_users = request.POST['max_users']
            license.issue_date = request.POST['issue_date']
            license.expiry_date = request.POST['expiry_date']
            license.save()
            messages.success(request, 'License updated successfully!')
            return redirect('list_licenses')
        except Exception as e:
            logger.exception("Error updating license id=%s: %s", license_id, e)
            messages.error(request, f'Error updating license: {e}')

    associates = associateuser.objects.filter(is_active=True)
    return render(request, 'Sapp/license/alter_licese.html', {
        'license': license,
        'associates': associates,
    })


@superadmin_required
def revoke_suspend_license(request, license_id):
    license = get_object_or_404(License, license_id=license_id)

    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('reason', '')

        try:
            if action == 'suspend':
                license.suspend(reason)
                messages.success(request, 'License suspended successfully.')
            elif action == 'revoke':
                license.revoke(reason)
                messages.success(request, 'License revoked successfully.')
            elif action == 'activate':
                license.activate()
                messages.success(request, 'License activated successfully.')
            logger.info(
                "License id=%s action='%s' by superadmin='%s'",
                license_id, action, request.user.username,
            )
            return redirect('list_licenses')
        except Exception as e:
            logger.exception("License action error: %s", e)
            messages.error(request, f'Error: {e}')

    return render(request, 'Sapp/license/revoke_suspend_licese.html', {'license': license})
