from django import template

register = template.Library()

@register.filter
def get_display_name(user):
    if user.first_name:
        return f'{user.first_name} {user.last_name}'.strip()
    return user.username
