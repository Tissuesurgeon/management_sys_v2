from functools import wraps

from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from workforce.models import Profile
from workforce.utils import ensure_profile


def _get_profile(user):
    return ensure_profile(user)


def org_admin_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if _get_profile(request.user).role != Profile.Role.ORG_ADMIN:
            return redirect('workforce:home')
        return view_func(request, *args, **kwargs)

    return _wrapped


def worker_required(view_func):
    @login_required
    @wraps(view_func)
    def _wrapped(request, *args, **kwargs):
        if _get_profile(request.user).role != Profile.Role.WORKER:
            return redirect('workforce:home')
        return view_func(request, *args, **kwargs)

    return _wrapped
