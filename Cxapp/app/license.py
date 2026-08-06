"""
Cxapp/app/license.py
======================
Cxapp-only license/trial tracker — NOT the Sapp.License model. Sapp's
License is associate-issued and platform-wide; Cxapp owners self-signup
with no associate involvement, so they get their own lightweight trial
clock tied 1:1 to CxOwnerProfile.

Rule: 7-day trial from signup. After expiry, every Cxapp view except
company profile and the plan-purchase page redirects to plan purchase.
Enforced in Cxapp/middleware.py — this module only holds the model,
the plan choices, and the purchase views.
"""

from datetime import timedelta

from django.db import models
from django.utils import timezone
from django import forms
from django.contrib import messages
from django.shortcuts import render, redirect

TRIAL_DAYS = 7

PLAN_CHOICES = [
    ('trial',      'Trial'),
    ('basic',      'Basic'),
    ('premium',    'Premium'),
    ('enterprise', 'Enterprise'),
]

PLAN_DURATIONS_DAYS = {
    'basic': 365,
    'premium': 365 * 3,
    'enterprise': 365 * 10,
}


class CxPlan(models.Model):
    """
    One row per CxOwnerProfile. Created automatically at signup with
    plan='trial' and a 7-day expiry. Purchasing a plan updates this
    same row rather than creating a new one — one active plan per owner.
    """
    owner        = models.OneToOneField('Cxapp.CxOwnerProfile', on_delete=models.CASCADE,
                                        related_name='plan')
    plan         = models.CharField(max_length=20, choices=PLAN_CHOICES, default='trial')
    started_at   = models.DateTimeField(auto_now_add=True)
    expires_at   = models.DateTimeField()
    is_active    = models.BooleanField(default=True)
    updated_at   = models.DateTimeField(auto_now=True)

    class Meta:
        app_label = 'Cxapp'
        db_table = 'cx_plan'
        verbose_name = 'Owner Plan'
        verbose_name_plural = 'Owner Plans'

    def __str__(self):
        return f'{self.owner.company.company_name} — {self.get_plan_display()} (expires {self.expires_at:%Y-%m-%d})'

    @classmethod
    def start_trial(cls, owner_profile):
        """Called once at Cxapp signup."""
        return cls.objects.create(
            owner=owner_profile,
            plan='trial',
            expires_at=timezone.now() + timedelta(days=TRIAL_DAYS),
        )

    def is_valid(self):
        return self.is_active and self.expires_at >= timezone.now()

    def days_remaining(self):
        delta = self.expires_at - timezone.now()
        return max(0, delta.days)

    def upgrade(self, plan_code):
        """Owner purchases a plan. Extends from now, not from old expiry."""
        if plan_code not in PLAN_DURATIONS_DAYS:
            raise ValueError(f'Unknown plan: {plan_code}')
        self.plan = plan_code
        self.expires_at = timezone.now() + timedelta(days=PLAN_DURATIONS_DAYS[plan_code])
        self.is_active = True
        self.save(update_fields=['plan', 'expires_at', 'is_active', 'updated_at'])


# ── Views ────────────────────────────────────────────────────────────────────
# These two views are the ALWAYS-ALLOWED destinations — must never be
# blocked by the license middleware, or an expired owner could never
# reach the purchase page. See Cxapp/middleware.py ALWAYS_ALLOWED_NAMES.

def cxapp_plan_purchase(request):
    from Cxapp.views import cx_login_required

    @cx_login_required
    def _view(request):
        plan = getattr(request.cx_owner_profile, 'plan', None)

        if request.method == 'POST':
            chosen = request.POST.get('plan')
            if chosen not in PLAN_DURATIONS_DAYS:
                messages.error(request, 'Please select a valid plan.')
            else:
                if plan is None:
                    plan = CxPlan.objects.create(
                        owner=request.cx_owner_profile, plan=chosen,
                        expires_at=timezone.now(),
                    )
                plan.upgrade(chosen)
                messages.success(request, f"Plan upgraded to {plan.get_plan_display()}. "
                                           f"Valid until {plan.expires_at:%d %b %Y}.")
                return redirect('cxapp_dashboard')

        return render(request, 'Cxapp/plan_purchase.html', {
            'plan': plan,
            'plans': [(code, label, PLAN_DURATIONS_DAYS.get(code)) for code, label in PLAN_CHOICES if code != 'trial'],
        })

    return _view(request)
