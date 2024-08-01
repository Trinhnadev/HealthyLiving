from django import template

register = template.Library()

@register.filter(name='get_order_total')
def get_order_total(order_totals, order_id):
    return order_totals.get(order_id, 0)



@register.filter(name='isinstanceof')
def isinstanceof(value, arg):
    return value.__class__.__name__ == arg
