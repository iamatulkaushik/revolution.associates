"""Public marketing + legal views. Single source of truth for plans (PLANS)."""
import logging
from django.conf import settings
from django.core.mail import send_mail
from django.http import HttpResponse
from django.shortcuts import render, redirect
from django.urls import reverse
from django.contrib import messages

log = logging.getLogger(__name__)

# status: ''=live, 'soon'=rolling out, 'plan'=planned
PLANS = [
    dict(slug="copper", name="Copper", price=999, limit="Up to 25 employees", pick=False, features=[
        ("Employee master and onboarding", ""), ("Attendance and leave", ""),
        ("Payroll with EPF and ESI", ""), ("Payslips (PDF)", ""),
        ("Core statutory reports", "")]),
    dict(slug="silver", name="Silver", price=2499, limit="Up to 75 employees", pick=False, features=[
        ("Everything in Copper", ""), ("Professional Tax, 19+ states", ""),
        ("Loans and advances with EMI schedule", ""), ("Bulk payslip email", ""),
        ("Bank payout files", "")]),
    dict(slug="gold", name="Gold", price=4999, limit="Up to 200 employees", pick=True, features=[
        ("Everything in Silver", ""), ("TDS, Form 16 and Form 24Q", ""),
        ("Biometric / RFID attendance sync", ""), ("Overtime and LOP", ""),
        ("Arrears, increments, Full and Final", ""), ("Audit trail", "")]),
    dict(slug="platinum", name="Platinum", price=8999, limit="Unlimited employees", pick=False, features=[
        ("Everything in Gold", ""), ("Asset and expense management", ""),
        ("Maker-checker payroll approval", "soon"),
        ("Direct bank disbursement and API access", "plan"),
        ("Priority support", "")]),
]
for _p in PLANS:
    _p["price_display"] = "₹{:,}".format(_p["price"])

SITE_EMAIL = "support@reas.host"
LEGAL_UPDATED = "28 October 2026"


def _ctx(**kw):
    kw.setdefault("plans", PLANS)
    kw.setdefault("site_email", SITE_EMAIL)
    kw.setdefault("legal_updated", LEGAL_UPDATED)
    return kw


def features(request):   return render(request, "marketing/features.html", _ctx())
def pricing(request):    return render(request, "marketing/pricing.html", _ctx())
def compliance(request): return render(request, "marketing/compliance.html", _ctx())
def about(request):      return render(request, "marketing/about.html", _ctx())
def contact(request):    return render(request, "marketing/contact.html", _ctx())
def privacy(request):    return render(request, "legal/privacy.html", _ctx())
def terms(request):      return render(request, "legal/terms.html", _ctx())
def cookies(request):    return render(request, "legal/cookies.html", _ctx())
def refund(request):     return render(request, "legal/refund.html", _ctx())


def contact_submit(request):
    if request.method != "POST":
        return redirect("contact")
    d = request.POST
    if d.get("website"):                       # honeypot: bots fill this
        messages.success(request, "Thanks. We will reply within one business day.")
        return redirect("contact")
    if not d.get("consent"):
        messages.error(request, "Please tick the consent box so we can contact you.")
        return redirect("contact")
    body = "\n".join(f"{k}: {d.get(k, '').strip()}" for k in ("name", "company", "email", "phone", "topic", "message"))
    try:
        send_mail("New enquiry: reas.host", body, settings.DEFAULT_FROM_EMAIL, [SITE_EMAIL], fail_silently=False)
        messages.success(request, "Thanks. We will reply within one business day.")
    except Exception:
        log.exception("Contact form email failed")
        messages.error(request, f"We could not send that. Please email {SITE_EMAIL}.")
    return redirect("contact")


def robots_txt(request):
    lines = ["User-agent: *", "Allow: /", "Disallow: /admin/", "Disallow: /associate/", "Disallow: /capp/",
             "Disallow: /baseurls/", "Sitemap: https://reas.host/sitemap.xml"]
    return HttpResponse("\n".join(lines), content_type="text/plain")


def sitemap_xml(request):
    base = "https://reas.host"
    pages = [("/", "1.0"), ("/features/", "0.9"), ("/pricing/", "0.9"), ("/compliance/", "0.8"),
             ("/about/", "0.6"), ("/contact/", "0.7"), ("/privacy/", "0.3"), ("/terms/", "0.3"),
             ("/cookies/", "0.3"), ("/refund/", "0.3")]
    xml = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    xml += [f"  <url><loc>{base}{p}</loc><priority>{pr}</priority></url>" for p, pr in pages]
    xml.append("</urlset>")
    return HttpResponse("\n".join(xml), content_type="application/xml")
