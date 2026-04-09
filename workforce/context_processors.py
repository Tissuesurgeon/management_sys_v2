from django.urls import reverse

from workforce.models import Profile
from workforce.utils import ensure_profile


def workforce_profile(request):
    if not request.user.is_authenticated:
        return {}
    prof = ensure_profile(request.user)
    if prof.role == Profile.Role.ORG_ADMIN:
        profile_url = reverse('workforce:admin_profile')
    else:
        profile_url = reverse('workforce:worker_profile')
    profile_photo_url = prof.photo.url if prof.photo else None
    return {
        'profile': prof,
        'profile_url': profile_url,
        'profile_photo_url': profile_photo_url,
    }
