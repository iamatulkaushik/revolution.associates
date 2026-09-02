"""
Sapp/app/password_reset.py
============================
Shared password-reset core for every portal whose users are plain
django.contrib.auth.User: Aapp (Associate), Capp (Company Owner —
associate-mediated), Cxapp (Company Owner — self-signup).

Sapp is the platform/superadmin layer that all portals already import
from (Company, District, etc.), so this is the natural shared home —
avoids duplicating token logic three times across apps.

Uses Django's own PasswordResetTokenGenerator (same primitive Django's
admin site password reset uses) — no custom crypto, no DB token table.

Each portal supplies:
  - its own templates (branding differs per portal)
  - its own URL names for the request/confirm views
  - the login route name to redirect to when done

Employee self-service (Cxapp/app/employee_portal.py) is NOT covered
here — employees aren't django.contrib.auth.User, they use a separate
CxEmployeeAuth + PAN-based identity. See Cxapp/app/employee_portal.py
for that flow.
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.models import User
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.mail import send_mail
from django.shortcuts import render, redirect
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode

logger = logging.getLogger('Sapp')

token_generator = PasswordResetTokenGenerator()


def send_reset_email(request, user, *, subdomain, confirm_url_name, subject_line, text_template):
    """Builds a uidb64/token reset link for `user` and emails it.
    Never raises — logs and returns False on failure so a reset
    request never 500s the requesting view."""
    try:
        uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
        token = token_generator.make_token(user)
        parent_host = getattr(settings, 'PARENT_HOST', 'localhost:8000')
        scheme = 'https' if request.is_secure() else 'http'
        link = f'{scheme}://{subdomain}.{parent_host}/reset/{uidb64}/{token}/'

        body = render_to_string(text_template, {'user': user, 'link': link})
        send_mail(
            subject=subject_line,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
            fail_silently=False,
        )
        logger.info("Password reset email sent: user='%s'", user.username)
        return True
    except Exception:
        logger.exception("Failed to send password reset email: user='%s'", user.username)
        return False


def handle_reset_request(request, *, template, subdomain, confirm_url_name,
                          subject_line, text_template, login_url_name):
    """Generic 'forgot password' view body — call from each portal's
    thin wrapper view. Renders `template` on GET, processes on POST."""
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        user = User.objects.filter(email__iexact=email, is_active=True).first()
        if user:
            send_reset_email(
                request, user,
                subdomain=subdomain,
                confirm_url_name=confirm_url_name,
                subject_line=subject_line,
                text_template=text_template,
            )
        # Same message regardless — don't reveal whether the email is registered.
        messages.success(request, 'If that email is registered, a reset link has been sent.')
        return redirect(login_url_name)

    return render(request, template)


def handle_reset_confirm(request, uidb64, token, *, template, login_url_name):
    """Generic 'set new password' view body — call from each portal's
    thin wrapper view."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    valid_link = user is not None and token_generator.check_token(user, token)

    if not valid_link:
        messages.error(request, 'This password reset link is invalid or has expired.')
        return redirect(login_url_name)

    if request.method == 'POST':
        password1 = request.POST.get('password1', '')
        password2 = request.POST.get('password2', '')
        if password1 != password2:
            messages.error(request, 'Passwords do not match.')
            return render(request, template, {'validlink': True})
        try:
            validate_password(password1, user=user)
        except ValidationError as e:
            for err in e.messages:
                messages.error(request, err)
            return render(request, template, {'validlink': True})

        user.set_password(password1)
        user.save(update_fields=['password'])
        logger.info("Password reset completed: user='%s'", user.username)
        messages.success(request, 'Password updated. Please log in.')
        return redirect(login_url_name)

    return render(request, template, {'validlink': True})
