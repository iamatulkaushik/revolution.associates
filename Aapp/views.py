import logging

from django.shortcuts import render, redirect
from django.contrib.auth.forms import AuthenticationForm
from django import forms
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.views.decorators.debug import sensitive_post_parameters
from django.http import JsonResponse

from Aapp.app.branch_department import branch, department
from Sapp.app.company import Company
from Sapp.app.user import UserProfile, associateuser, SubUser, can_user_access_system, AssociateOfficeImage
from Sapp.app.license import License
from Sapp.app.password_reset import handle_reset_request, handle_reset_confirm

logger = logging.getLogger(__name__)


class loginForm(AuthenticationForm):
    username = forms.CharField(label='Username', max_length=255)
    password = forms.CharField(label='Password', widget=forms.PasswordInput)


# ---------------------------------------------------------------------------
# Auth views
# ---------------------------------------------------------------------------

def associate_base_home(request):
    """Renders the associate login landing page."""
    return render(request, 'associate_base_home.html')


@sensitive_post_parameters('password')
def associate_login(request):
    if request.method == 'POST':
        form = loginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()

            # Fixed: enforce suspension / disabled status at login time.
            # The models have can_access_system() but it was never called here.
            if not can_user_access_system(user):
                messages.error(
                    request,
                    'Your account is currently suspended or disabled. '
                    'Please contact your administrator.',
                )
                return render(request, 'associate_login.html', {'form': form})

            auth_login(request, user)
            logger.info("Associate login: user='%s'", user.username)
            messages.success(request, 'Logged in successfully.')
            return redirect('aapp_dashboard')
    else:
        form = loginForm()
    return render(request, 'associate_login.html', {'form': form})


def logout(request):
    username = request.user.username if request.user.is_authenticated else 'unknown'
    auth_logout(request)
    logger.info("Associate logout: user='%s'", username)
    messages.success(request, 'Logged out successfully.')
    return redirect('home')


def associate_password_reset_request(request):
    return handle_reset_request(
        request,
        template='associate_password_reset_request.html',
        subdomain='aapp',
        confirm_url_name='associate_password_reset_confirm',
        subject_line='Reset your password — Revolution Associates',
        text_template='Aapp/email/password_reset.txt',
        login_url_name='associate_login',
    )


def associate_password_reset_confirm(request, uidb64, token):
    return handle_reset_confirm(
        request, uidb64, token,
        template='associate_password_reset_confirm.html',
        login_url_name='associate_login',
    )


# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------

@login_required
def associate_dashboard(request):
    selected_company_id = request.session.get('selected_company_id')
    branches_count = 0
    departments_count = 0

    if selected_company_id:
        branches_count = branch.objects.filter(companyid=selected_company_id).count()
        departments_count = department.objects.filter(companyid=selected_company_id).count()

    return render(request, 'Aapp/dashboard.html', {
        'branches_count': branches_count,
        'departments_count': departments_count,
    })


# ---------------------------------------------------------------------------
# Profile
# ---------------------------------------------------------------------------

@login_required
def associate_profile(request):
    try:
        associate = associateuser.objects.get(user=request.user)
    except associateuser.DoesNotExist:
        messages.error(request, 'Associate profile not found.')
        return redirect('aapp_dashboard')

    licenses = License.objects.filter(associate=associate).select_related('company')
    subusers = SubUser.objects.filter(associate=associate).select_related('user')
    subusers_count = subusers.count()
    active_subusers = subusers.filter(is_active=True).count()
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
            return redirect('associate_profile')
        except Exception as e:
            logger.exception("Profile update error for user='%s': %s", request.user.username, e)
            messages.error(request, f'Error updating profile: {e}')

    return render(request, 'Aapp/users/associate_profile.html', {
        'associate': associate,
        'licenses': licenses,
        'subusers': subusers,
        'subusers_count': subusers_count,
        'active_subusers': active_subusers,
        'companies': companies,
    })

@login_required
def associate_public_profile_update(request):
    try:
        associate = associateuser.objects.get(user=request.user)
    except associateuser.DoesNotExist:
        messages.error(request, 'Associate profile not found.')
        return redirect('aapp_dashboard')

    if request.method == 'POST':
        try:
            associate.is_public_profile = bool(request.POST.get('is_public_profile'))
            slug = request.POST.get('slug', '').strip()
            if slug:
                associate.slug = slug
            associate.public_display_name = request.POST.get('public_display_name', '').strip()
            associate.contact_email = request.POST.get('contact_email', '').strip()
            associate.contact_phone = request.POST.get('contact_phone', '').strip()
            associate.bio = request.POST.get('bio', '').strip()

            if request.FILES.get('logo'):
                associate.logo = request.FILES['logo']

            associate.save()

            for img in request.FILES.getlist('office_images'):
                AssociateOfficeImage.objects.create(associate=associate, image=img)

            messages.success(request, 'Public profile updated successfully!')
        except Exception as e:
            logger.exception("Public profile update error for user='%s': %s", request.user.username, e)
            messages.error(request, f'Error updating public profile: {e}')

    return redirect('associate_profile')


# ---------------------------------------------------------------------------
# Branch management
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
    selected_company = None
    branches = []

    if request.method == 'POST':
        company_id = request.POST.get('company')
        branch_name = request.POST.get('branch_name', '').strip()
        branch_address = request.POST.get('branch_address', '')
        branch_email = request.POST.get('branch_email', '')
        contact_person = request.POST.get('contact_person', '')
        contact_mobile = request.POST.get('contact_mobile', '')

        if not company_id:
            messages.error(request, 'Please select a company.')
        elif not branch_name:
            messages.error(request, 'Please enter a branch name.')
        else:
            try:
                company = Company.objects.get(company_id=company_id)
            except Company.DoesNotExist:
                messages.error(request, 'Invalid company selection.')
                return render(request, 'Aapp/works/create_branch.html', {
                    'companies': companies,
                    'selected_company': selected_company,
                    'branches': branches,
                    'companies_count': companies.count(),
                })

            if branch.objects.filter(companyid=company, branch_name=branch_name).exists():
                messages.error(request, f"A branch named '{branch_name}' already exists in this company.")
            else:
                try:
                    branch_count = branch.objects.filter(companyid=company).count()
                    branch_code = f'{company.pan[:4]}{branch_count + 1:03d}'
                    branch.objects.create(
                        branch_name=branch_name,
                        branch_code=branch_code,
                        companyid=company,
                        branch_address=branch_address,
                        branch_email=branch_email,
                        contact_person=contact_person,
                        contact_mobile=contact_mobile,   # Fixed field name (was Cotact_mobile)
                        created_by=request.user,
                    )
                    messages.success(request, f"Branch '{branch_name}' created with code '{branch_code}'.")
                except Exception as e:
                    logger.exception("Branch creation error: %s", e)
                    messages.error(request, f'Error creating branch: {e}')

            selected_company = company
            branches = branch.objects.filter(companyid=company)

    return render(request, 'Aapp/works/create_branch.html', {
        'companies': companies,
        'selected_company': selected_company,
        'branches': branches,
        'companies_count': companies.count(),
    })


@login_required
def branch_list(request):
    branches = branch.objects.all()
    return render(request, 'Aapp/works/list_branch.html', {'branches': branches})


@login_required
def branch_details(request):
    return render(request, 'Aapp/works/branch_details.html')


# ---------------------------------------------------------------------------
# Company selection API
# ---------------------------------------------------------------------------

@login_required
def get_user_companies(request):
    user = request.user
    if hasattr(user, 'associate_profile'):
        companies = user.associate_profile.companyid.filter(shut_date__isnull=True)
    elif hasattr(user, 'subuser_profile'):
        companies = user.subuser_profile.companyid.filter(shut_date__isnull=True)
    elif user.is_superuser:
        companies = Company.objects.filter(shut_date__isnull=True)
    else:
        companies = Company.objects.none()

    companies = companies.values('company_id', 'company_name')
    selected_id = request.session.get('selected_company_id')
    return JsonResponse({
        'companies': list(companies),
        'selected_id': selected_id,
    })


@login_required
def select_company(request):
    """
    Fixed: validates that the company being selected actually belongs to
    the logged-in associate. Without this check any authenticated user
    could select any company_id and access another associate's data.
    """
    if request.method == 'POST':
        company_id = request.POST.get('company_id')
        if not company_id:
            return JsonResponse({'status': 'error', 'message': 'No company_id provided.'}, status=400)

        try:
            company_id = int(company_id)
        except (ValueError, TypeError):
            return JsonResponse({'status': 'error', 'message': 'Invalid company_id.'}, status=400)

        # Determine which companies this user is allowed to access
        user = request.user
        allowed_company_ids = None

        if hasattr(user, 'associate_profile'):
            allowed_company_ids = set(
                user.associate_profile.companyid.values_list('company_id', flat=True)
            )
        elif hasattr(user, 'subuser_profile'):
            allowed_company_ids = set(
                user.subuser_profile.companyid.values_list('company_id', flat=True)
            )

        # Superusers may select any company
        if allowed_company_ids is not None and not user.is_superuser:
            if company_id not in allowed_company_ids:
                logger.warning(
                    "Unauthorised company selection: user='%s' attempted company_id=%s",
                    user.username, company_id,
                )
                return JsonResponse(
                    {'status': 'error', 'message': 'You do not have access to this company.'},
                    status=403,
                )

        request.session['selected_company_id'] = company_id
        return JsonResponse({'status': 'success', 'company_id': company_id})

    return JsonResponse({'status': 'error', 'message': 'Invalid request method.'}, status=405)


@login_required
def get_selected_company(request):
    company_id = request.session.get('selected_company_id')
    if company_id:
        try:
            company = Company.objects.get(company_id=company_id)
            return JsonResponse({
                'company_id': company.company_id,
                'company_name': company.company_name,
                'mobile': company.mobile,
                'email': company.email1,
                'pan': company.pan,
            })
        except Company.DoesNotExist:
            pass
    return JsonResponse({'company_id': None})