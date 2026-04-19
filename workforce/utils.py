from workforce.models import Profile


def ensure_profile(user) -> Profile:
    """Return Profile, creating one if missing. Superusers default to facility manager (org_admin)."""
    prof, created = Profile.objects.get_or_create(
        user=user,
        defaults={'role': Profile.Role.WORKER},
    )
    if created and user.is_superuser:
        prof.role = Profile.Role.ORG_ADMIN
        prof.save(update_fields=['role'])
    return prof
