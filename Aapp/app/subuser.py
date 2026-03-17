from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.contrib import messages
from datetime import date
from Sapp.app.user import SubUser, associateuser, create_sub_user, change_subuser_password
from Sapp.app.license import License


def get_subuser_limit(associate):
    """Return allowed subuser count from active licenses, clamped 1–10."""
    total = License.objects.filter(
        associate=associate,
        is_active=True,
        status='active',
        expiry_date__gte=date.today()
    ).values_list('max_users', flat=True)
    limit = sum(total) if total else 1
    return max(1, min(limit, 10))


def get_associate(request):
    try:
        return associateuser.objects.get(user=request.user)
    except associateuser.DoesNotExist:
        return None


@login_required
def list_subusers(request):
    associate = get_associate(request)
    if not associate:
        messages.error(request, 'Associate profile not found.')
        return redirect('dashboard')
    subusers = SubUser.objects.filter(associate=associate).select_related('user')
    limit    = get_subuser_limit(associate)
    return render(request, 'Aapp/users/list_subusers.html', {
        'subusers': subusers,
        'limit': limit,
    })


@login_required
def add_subuser(request):
    associate = get_associate(request)
    if not associate:
        messages.error(request, 'Associate profile not found.')
        return redirect('dashboard')

    companies  = associate.get_companies()
    limit      = get_subuser_limit(associate)
    current    = SubUser.objects.filter(associate=associate).count()

    if request.method == 'POST':
        username   = request.POST.get('username', '').strip()
        first_name = request.POST.get('first_name', '').strip()
        last_name  = request.POST.get('last_name', '').strip()
        email      = request.POST.get('email', '').strip()
        mobile     = request.POST.get('mobile', '').strip()
        address    = request.POST.get('address', '').strip()
        role       = request.POST.get('role', 'operator')
        password   = request.POST.get('password', '')
        confirm_pw = request.POST.get('confirm_password', '')

        if current >= limit:
            messages.error(request, f'Sub user limit reached ({limit}). Upgrade your license to add more.')
        elif not all([username, first_name, email, password]):
            messages.error(request, 'Username, first name, email and password are required.')
        elif password != confirm_pw:
            messages.error(request, 'Passwords do not match.')
        elif User.objects.filter(username=username).exists():
            messages.error(request, f"Username '{username}' is already taken.")
        else:
            try:
                create_sub_user(
                    username=username, email=email,
                    first_name=first_name, last_name=last_name,
                    password=password, associate=associate,
                    role=role, mobile=mobile, address=address
                )
                messages.success(request, f"Sub user '{username}' created successfully.")
                return redirect('list_subusers')
            except Exception as e:
                messages.error(request, f'Error creating sub user: {e}')

    return render(request, 'Aapp/users/add_subusers.html', {
        'companies': companies,
        'limit': limit,
        'current': current,
    })


@login_required
def alter_subuser(request, subuser_id):
    associate = get_associate(request)
    if not associate:
        messages.error(request, 'Associate profile not found.')
        return redirect('dashboard')

    subuser = get_object_or_404(SubUser, pk=subuser_id, associate=associate)

    if request.method == 'POST':
        subuser.user.first_name = request.POST.get('first_name', '').strip()
        subuser.user.last_name  = request.POST.get('last_name', '').strip()
        subuser.user.email      = request.POST.get('email', '').strip()
        subuser.mobile          = request.POST.get('mobile', '').strip()
        subuser.address         = request.POST.get('address', '').strip()
        subuser.role            = request.POST.get('role', subuser.role)
        subuser.user.save()
        subuser.save()
        messages.success(request, 'Sub user updated successfully.')
        return redirect('list_subusers')

    return render(request, 'Aapp/users/alter_subusers.html', {'subuser': subuser})


@login_required
def reset_subuser_password(request, subuser_id):
    associate = get_associate(request)
    if not associate:
        messages.error(request, 'Associate profile not found.')
        return redirect('dashboard')

    subuser = get_object_or_404(SubUser, pk=subuser_id, associate=associate)

    if request.method == 'POST':
        new_password = request.POST.get('new_password', '')
        confirm_pw   = request.POST.get('confirm_password', '')
        if not new_password:
            messages.error(request, 'Password cannot be empty.')
        elif new_password != confirm_pw:
            messages.error(request, 'Passwords do not match.')
        else:
            change_subuser_password(subuser, new_password)
            messages.success(request, f"Password reset for '{subuser.user.username}' successfully.")
            return redirect('list_subusers')

    return render(request, 'Aapp/users/reset_subuser_password.html', {'subuser': subuser})


@login_required
def disable_subuser(request, subuser_id):
    associate = get_associate(request)
    if not associate:
        messages.error(request, 'Associate profile not found.')
        return redirect('dashboard')

    subuser = get_object_or_404(SubUser, pk=subuser_id, associate=associate)

    if request.method == 'POST':
        action = request.POST.get('action')
        reason = request.POST.get('reason', '')
        if action == 'disable':
            subuser.disable_permanently(reason)
            messages.success(request, f"Sub user '{subuser.user.username}' disabled.")
        elif action == 'suspend':
            subuser.suspend_for_24h(reason)
            messages.success(request, f"Sub user '{subuser.user.username}' suspended for 24 hours.")
        elif action == 'enable':
            subuser.enable_user(reason)
            messages.success(request, f"Sub user '{subuser.user.username}' enabled.")
        return redirect('list_subusers')

    return render(request, 'Aapp/users/disable_subusers.html', {'subuser': subuser})


@login_required
def subuser_companies(request, subuser_id):
    associate = get_associate(request)
    if not associate:
        messages.error(request, 'Associate profile not found.')
        return redirect('dashboard')

    subuser = get_object_or_404(SubUser, pk=subuser_id, associate=associate)
    available = associate.get_companies()
    assigned  = subuser.get_companies()

    if request.method == 'POST':
        action     = request.POST.get('action')
        company_id = request.POST.get('company_id')
        from Sapp.app.company import Company
        company = get_object_or_404(Company, pk=company_id)
        if action == 'allocate':
            if subuser.add_company(company):
                messages.success(request, f"'{company.company_name}' allocated to {subuser.user.username}.")
            else:
                messages.error(request, 'Company not available under your associate account.')
        elif action == 'deallocate':
            subuser.remove_company(company)
            messages.success(request, f"'{company.company_name}' removed from {subuser.user.username}.")
        return redirect('subuser_companies', subuser_id=subuser_id)

    return render(request, 'Aapp/users/subuser_companies.html', {
        'subuser': subuser,
        'available': available,
        'assigned': assigned,
    })
