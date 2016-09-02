from django import template


register = template.Library()

@register.filter(name='dget')
def dget(d, key):
    return d.get(key, '')

