from django import template

register = template.Library()


@register.simple_tag
def nav_active(request, *names):
    if not request.resolver_match:
        return False
    return request.resolver_match.url_name in names
