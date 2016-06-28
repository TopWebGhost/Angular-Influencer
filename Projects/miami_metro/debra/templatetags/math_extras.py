from django import template

register = template.Library()

@register.filter(name='mult')
def mult(value, arg):
    "Multiplies the arg and the value"
    return int(value) * int(arg)

# Not used right now
def sub(value, arg):
    "Subtracts the arg from the value"
    return int(value) - int(arg)

def div(value, arg):
    "Divides the value by the arg"
    return int(value) / int(arg)