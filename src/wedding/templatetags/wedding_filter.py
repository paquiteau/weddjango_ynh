from django import template

register = template.Library()

@register.filter
def get_field(form, field_name):
    """
    Allows getting a field from a form by its string name.
    Used for dynamically accessing attendance fields in the RSVP template.
    """
    return form[field_name]
