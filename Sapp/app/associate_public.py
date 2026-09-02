"""
Public-facing associate profile page.

No login required. Shows associate branding, contact details, office
images, company count, and auto-computed compliance accuracy — for SEO
and shareable marketing purposes.
"""

from django.shortcuts import render, get_object_or_404

from Sapp.app.user import associateuser


def associate_public_profile(request, slug):
    associate = get_object_or_404(
        associateuser,
        slug=slug,
        is_public_profile=True,
        is_active=True,
    )

    context = {
        'associate': associate,
        'display_name': associate.public_display_name or associate.user.get_full_name() or associate.user.username,
        'companies_count': associate.companyid.count(),
        'compliance_accuracy': associate.get_compliance_accuracy(),
        'office_images': associate.office_images.all(),
        'meta_title': f"{associate.public_display_name or associate.associate_id} | Revolution Associates",
        'meta_description': (associate.bio[:160] if associate.bio else
                              'HR & payroll compliance associate on Revolution Associates.'),
    }
    return render(request, 'public/associate_profile.html', context)
