from django import template

register = template.Library()

def paginator(context, adjacent_pages=2, object_list=None, request=None):
    start_page = max(object_list.number - adjacent_pages, 1)
    if start_page <= 3:
        start_page = 1
    end_page = object_list.number + adjacent_pages + 1
    if end_page >= object_list.paginator.num_pages - 1:
        end_page = object_list.paginator.num_pages + 1
    page_numbers = [n for n in xrange(start_page, end_page) \
        if n > 0 and n <= object_list.paginator.num_pages]
    old_params = request.GET.copy()
    try:
        del old_params['page']
    except KeyError:
        pass
    try:
        del old_params['only_partial']
    except KeyError:
        pass
    return {
        'object_list': range(30) if object_list is None else object_list,
        'show_first': 1 not in page_numbers,
        'show_last': object_list.paginator.num_pages not in page_numbers,
        'request': request,
        'old_params': old_params
    }

register.inclusion_tag('snippets/paginator.html', takes_context=True)(paginator)