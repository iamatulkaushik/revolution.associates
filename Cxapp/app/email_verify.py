"""
Cxapp/app/email_verify.py
==========================
Email verification for self-signup company owners.

Flow:
1. cxapp_signup() creates the user + CxOwnerProfile as before, but the
   profile starts with email_verified=False. A signed, time-limited
   token is emailed to the owner immediately after signup.
2. Owner clicks the link -> cxapp_verify_email() marks email_verified=True.
3. Unverified owners can still log in (avoids locking anyone out if
   email delivery fails), but Cxapp/middleware.py flashes a persistent
   reminder banner and cxapp_resend_verification() lets them ask again.

Uses Django's TimestampSigner (not a DB token table) — matches this
codebase's preference for standards-based, low-maintenance primitives
(same reasoning as the django-cryptography field encryption approach).
"""

import logging

from django.conf import settings
from django.contrib import messages
from django.core.signing import TimestampSigner, BadSignature, SignatureExpired
from django.core.mail import send_mail
from django.shortcuts import redirect, render
from django.template.loader import render_to_string

from Cxapp.models import CxOwnerProfile

logger = logging.getLogger('Cxapp')

VERIFY_SALT = 'cxapp.email_verify'
VERIFY_MAX_AGE = 60 * 60 * 48  # 48 hours

signer = TimestampSigner(salt=VERIFY_SALT)


def _verify_link(request, owner_profile):
    token = signer.sign(str(owner_profile.user_id))
    parent_host = getattr(settings, 'PARENT_HOST', 'localhost:8000')
    scheme = 'https' if request.is_secure() else 'http'
    return f'{scheme}://cxapp.{parent_host}/verify-email/{token}/'


def send_verification_email(request, owner_profile):
    """Send (or resend) the verification link. Never raises — logs on failure
    so signup/login flows never break because of an SMTP hiccup."""
    try:
        link = _verify_link(request, owner_profile)
        company_name = owner_profile.company.company_name
        subject = 'Verify your email — Revolution Associates'
        body = render_to_string('Cxapp/email/verify_email.txt', {
            'company_name': company_name,
            'link': link,
            'hours': VERIFY_MAX_AGE // 3600,
        })
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[owner_profile.user.email],
            fail_silently=False,
        )
        logger.info("Verification email sent: user='%s'", owner_profile.user.username)
        return True
    except Exception:
        logger.exception("Failed to send verification email: user='%s'", owner_profile.user.username)
        return False


def cxapp_verify_email(request, token):
    try:
        user_id = signer.unsign(token, max_age=VERIFY_MAX_AGE)
    except SignatureExpired:
        messages.error(request, 'This verification link has expired. Please request a new one.')
        return redirect('cxapp_resend_verification')
    except BadSignature:
        messages.error(request, 'Invalid verification link.')
        return redirect('cxapp_login')

    try:
        owner_profile = CxOwnerProfile.objects.get(user_id=user_id)
    except CxOwnerProfile.DoesNotExist:
        messages.error(request, 'Invalid verification link.')
        return redirect('cxapp_login')

    if not owner_profile.email_verified:
        owner_profile.email_verified = True
        owner_profile.save(update_fields=['email_verified'])
        logger.info("Email verified: user='%s'", owner_profile.user.username)

    messages.success(request, 'Email verified successfully.')
    return redirect('cxapp_dashboard' if request.user.is_authenticated else 'cxapp_login')


def cxapp_resend_verification(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').strip()
        try:
            owner_profile = CxOwnerProfile.objects.get(user__email__iexact=email)
            if owner_profile.email_verified:
                messages.info(request, 'This email is already verified. Please log in.')
            else:
                send_verification_email(request, owner_profile)
                messages.success(request, 'Verification email sent. Please check your inbox.')
        except CxOwnerProfile.DoesNotExist:
            # Same message either way — don't reveal whether an email is registered.
            messages.success(request, 'If that email is registered, a verification link has been sent.')
        return redirect('cxapp_login')

    return render(request, 'Cxapp/resend_verification.html')
