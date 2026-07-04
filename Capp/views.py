import logging

from django import forms as dj_forms
from django.contrib import messages
from django.contrib.auth import authenticate, login as auth_login, logout as auth_logout
from django.contrib.auth.forms import AuthenticationForm
from django.http import Http404
from django.shortcuts import render, redirect, get_object_or_404

from .decorators import owner_required
from .forms import build_form_class
from .registry import REGISTRY, REGISTRY_BY_SLUG, CATEGORIES
from Sapp.app.company import Company, company_statury

logger = logging.getLogger(__name__)


class OwnerLoginForm(AuthenticationForm):
    username = dj_forms.CharField(label='Owner ID / Username', max_length=255)
    password = dj_forms.CharField(label='Password', widget=dj_forms.PasswordInput)


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

def login_company(request):
    if request.method == 'POST':
        form = OwnerLoginForm(data=request.POST)
        if form.is_valid():
            user = form.get_user()
            profile = getattr(user, 'company_owner_profile', None)
            if profile is None:
                messages.error(request, 'This account is not registered as a Company Owner.')
                return render(request, 'Capp/login.html', {'form': form})
            if not profile.can_access_system():
                messages.error(request, 'Your account is suspended or disabled.')
                return render(request, 'Capp/login.html', {'form': form})
            auth_login(request, user)
            return redirect('company_dashboard')
        messages.error(request, 'Invalid username or password.')
    else:
        form = OwnerLoginForm()
    return render(request, 'Capp/login.html', {'form': form})


def logout_company(request):
    auth_logout(request)
    return redirect('login_owner')


# ---------------------------------------------------------------------------
# Dashboard & company profile
# ---------------------------------------------------------------------------

@owner_required
def dashboard(request):
    company = request.owned_company
    counts = []
    for cat in CATEGORIES:
        entries = [e for e in REGISTRY if e.category == cat]
        cat_count = 0
        for e in entries:
            cat_count += e.model.objects.filter(**{e.company_lookup: company}).count()
        counts.append({'category': cat, 'count': cat_count, 'modules': len(entries)})
    return render(request, 'Capp/dashboard.html', {
        'company': company,
        'owner_profile': request.owner_profile,
        'counts': counts,
        'categories': CATEGORIES,
        'registry': REGISTRY,
    })


@owner_required
def company_detail(request):
    company = request.owned_company
    statutory = company_statury.objects.filter(company=company).first()
    return render(request, 'Capp/company/detail.html', {'company': company, 'statutory': statutory})


@owner_required
def company_edit(request):
    from django.forms import modelform_factory

    company = request.owned_company
    exclude = ['company_id', 'company_name', 'pan', 'start_date', 'shut_date', 'created_at', 'created_by', 'updated_at', 'updated_by']
    FormClass = modelform_factory(Company, exclude=exclude)

    if request.method == 'POST':
        form = FormClass(request.POST, instance=company)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.updated_by = request.user.username
            obj.save()
            messages.success(request, 'Company details updated.')
            return redirect('company_detail')
    else:
        form = FormClass(instance=company)
    return render(request, 'Capp/company/edit.html', {'form': form, 'company': company})


@owner_required
def profile(request):
    return render(request, 'Capp/profile.html', {'owner_profile': request.owner_profile})


# ---------------------------------------------------------------------------
# Generic CRUD engine — every registry entry gets list/add/edit/delete
# ---------------------------------------------------------------------------

def _get_entry(slug):
    entry = REGISTRY_BY_SLUG.get(slug)
    if entry is None:
        raise Http404('Unknown module')
    return entry


def _stamp_audit(obj, user, stamp_created=False):
    """Set created_by/updated_by whether the field is a User FK or a CharField."""
    fields = (['created_by'] if stamp_created else []) + ['updated_by']
    for name in fields:
        try:
            field = obj._meta.get_field(name)
        except Exception:
            continue
        setattr(obj, name, user if field.is_relation else user.username)


def _company_kwargs(entry, company):
    """Build the create-time kwargs that stamp the record to the owner's company."""
    root_field = entry.company_lookup.split('__')[0]
    if '__' in entry.company_lookup:
        # Indirectly-scoped model (e.g. via attendance/factory/employee FK) —
        # the parent FK itself is already filtered to the company in the
        # form's queryset, so nothing extra needs stamping here.
        return {}
    return {root_field: company}


@owner_required
def generic_list(request, slug):
    entry = _get_entry(slug)
    company = request.owned_company
    qs = entry.model.objects.filter(**{entry.company_lookup: company})
    columns = [entry.model._meta.get_field(f).verbose_name.title() for f in entry.list_fields]
    rows = []
    for obj in qs:
        cells = [getattr(obj, f) for f in entry.list_fields]
        rows.append({
            'cells': cells,
            'actions': [
                {'label': 'Edit', 'url': f'/{entry.slug}/{obj.pk}/edit/', 'css': 'edit'},
                {'label': 'Delete', 'url': f'/{entry.slug}/{obj.pk}/delete/', 'css': 'delete'},
            ],
        })
    return render(request, 'Capp/generic/list.html', {
        'page_title': entry.label,
        'columns': columns,
        'rows': rows,
        'add_url': f'/{entry.slug}/add/',
        'company': company,
    })


@owner_required
def generic_create(request, slug):
    entry = _get_entry(slug)
    company = request.owned_company
    FormClass = build_form_class(entry)
    if request.method == 'POST':
        form = FormClass(request.POST, company=company)
        if form.is_valid():
            obj = form.save(commit=False)
            for field, value in _company_kwargs(entry, company).items():
                setattr(obj, field, value)
            _stamp_audit(obj, request.user, stamp_created=True)
            obj.save()
            if hasattr(form, 'save_m2m'):
                form.save_m2m()
            messages.success(request, f'{entry.label} added successfully.')
            return redirect(f'/{entry.slug}/')
    else:
        form = FormClass(company=company)
    return render(request, 'Capp/generic/form.html', {
        'page_title': f'Add {entry.label}',
        'form': form,
        'cancel_url': f'/{entry.slug}/',
        'company': company,
    })


@owner_required
def generic_update(request, slug, pk):
    entry = _get_entry(slug)
    company = request.owned_company
    obj = get_object_or_404(entry.model.objects.filter(**{entry.company_lookup: company}), pk=pk)
    FormClass = build_form_class(entry)
    if request.method == 'POST':
        form = FormClass(request.POST, instance=obj, company=company)
        if form.is_valid():
            updated = form.save(commit=False)
            _stamp_audit(updated, request.user, stamp_created=False)
            updated.save()
            messages.success(request, f'{entry.label} updated successfully.')
            return redirect(f'/{entry.slug}/')
    else:
        form = FormClass(instance=obj, company=company)
    return render(request, 'Capp/generic/form.html', {
        'page_title': f'Edit {entry.label}',
        'form': form,
        'cancel_url': f'/{entry.slug}/',
        'company': company,
    })


@owner_required
def generic_delete(request, slug, pk):
    entry = _get_entry(slug)
    company = request.owned_company
    obj = get_object_or_404(entry.model.objects.filter(**{entry.company_lookup: company}), pk=pk)
    if request.method == 'POST':
        obj.delete()
        messages.success(request, f'{entry.label} deleted.')
        return redirect(f'/{entry.slug}/')
    return render(request, 'Capp/generic/confirm.html', {
        'page_title': f'Delete {entry.label}',
        'confirm_message': f'Are you sure you want to delete this {entry.label} record? This cannot be undone.',
        'cancel_url': f'/{entry.slug}/',
        'submit_label': 'Delete',
        'button_css': 'danger',
    })
