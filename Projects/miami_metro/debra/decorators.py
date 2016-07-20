import time
import json
import hashlib
import traceback
import inspect
from functools import wraps, partial

from django.conf import settings
from django.core.urlresolvers import reverse
from django.utils.functional import wraps
from django.http import HttpResponseRedirect, Http404
from django.shortcuts import redirect
from django.http import Http404
from django.core.cache import get_cache
from django.http import (HttpResponseForbidden, HttpResponse,\
    HttpResponseBadRequest)


mc_cache = get_cache('memcached')
redis_cache = get_cache('redis')


def custom_cached(func=None, key=None, cache=None, timeout=0):
    if func is None:
        return partial(custom_cached, key=key, cache=cache, timeout=timeout)
    cache = cache or redis_cache
    @wraps(func)
    def _wrapped(*args, **kwargs):
        cache_key = key(args[0]) if callable(key) else key
        data = cache.get(cache_key)
        if data is None:
            data = func(*args, **kwargs)
            cache.set(cache_key, data, timeout=0)
        return data
    return _wrapped


def timeit(method):

    @wraps(method) 
    def timed(*args, **kw):
        ts = time.time()
        result = method(*args, **kw)
        te = time.time()

        print '%r (%r, %r) %2.2f sec' % \
            (method.__name__, args, kw, te-ts)
        return result

    return timed


class cached_property(object):
    """ A property that is only computed once per instance and then replaces
        itself with an ordinary attribute. Deleting the attribute resets the
        property.
    """

    def __init__(self, func):
        self.__doc__ = getattr(func, '__doc__')
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        value = obj.__dict__[self.func.__name__] = self.func(obj)
        return value


class json_field_property(object):

    def __init__(self, func):
        self.__doc__ = getattr(func, '__doc__')
        self.func = func

    def __get__(self, obj, cls):
        if obj is None:
            return self
        try:
            field_value = json.loads(getattr(obj, self.func(obj)))
        except:
            field_value = {}
        value = obj.__dict__[self.func.__name__] = field_value
        return value


def signal_crashed_notification(func):
    @wraps(func)
    def inner(sender, instance, **kwargs):
        try:
            func(sender, instance, **kwargs)
        except:
            from debra.account_helpers import send_msg_to_slack
            send_msg_to_slack(
                'signal-crashes',
                "{asterisks}\n"
                "'{func_name}' signal crashed for sender={sender}, id={instance_id}\n"
                "{asterisks}\n"
                "{traceback}\n"
                "{delimiter}"
                "\n".format(
                    asterisks="*" * 120,
                    delimiter="=" * 120,
                    func_name=func.__name__,
                    sender=sender,
                    instance_id=instance.id,
                    traceback=traceback.format_exc())
            )
            
    return inner


def cached_model_property(method):
    @wraps(method)
    def inner(self, *args, **kwargs):
        key = "%s:%s:%i" % (method.__name__, self.__class__.__name__, self.id)
        cached = mc_cache.get(key)
        if cached is None:
            output = method(self, *args, **kwargs)
            mc_cache.set(key, output)
            return output
        else:
            return cached
    return inner


def user_is_page_user(view):
    @wraps(view)
    def decorator(request, *args, **kwargs):
        user_prof = request.user.userprofile if request.user and request.user.is_authenticated() else None
        if not user_prof or user_prof.id != int(kwargs['user']):
            return HttpResponseRedirect(reverse('debra.widget_views.widgets_home', args=(user_prof.id,)))

        return view(request, *args, **kwargs)

    return decorator


def user_is_brand_user(view):
    @wraps(view)
    def decorator(request, *args, **kwargs):
        if request.user and request.user.is_superuser and request.user.is_staff:
            return view(request, *args, **kwargs)
        brand = request.visitor["base_brand"]
        if not brand:
            return redirect('/')

        return view(request, *args, **kwargs)

    return decorator


def login_required_json(view):
    @wraps(view)
    def decorator(request, *args, **kwargs):
        if request.user and request.user.is_superuser and request.user.is_staff:
            return view(request, *args, **kwargs)
        brand = request.visitor["base_brand"]
        if not request.user.is_authenticated():
            return HttpResponseForbidden({
                'error': 'unauthorized',
            }, content_type='application/json')

        return view(request, *args, **kwargs)

    return decorator


def user_is_brand_user_json(view):
    @wraps(view)
    def decorator(request, *args, **kwargs):
        if request.user and request.user.is_superuser and request.user.is_staff:
            return view(request, *args, **kwargs)
        brand = request.visitor["base_brand"]
        if not brand:
            return HttpResponseForbidden({
                'error': 'unauthorized',
            }, content_type='application/json')

        return view(request, *args, **kwargs)

    return decorator


def brand_view(view):
    @wraps(view)
    def _wrapped(request, *args, **kwargs):
        brand = request.visitor["brand"]
        base_brand = request.visitor["base_brand"]
        if not base_brand or not base_brand.is_subscribed:
            return redirect('/')
        # associated_campaigns = brand.job_posts.exclude(archived=True).filter(oryg_creator=base_brand, published=True)
        return view(request, brand, base_brand, *args, **kwargs)
    return _wrapped


def public_influencer_view(view):
    @wraps(view)
    def _wrapped(request, influencer_id, date_created_hash):
        from debra.models import Influencer
        inf = Influencer.objects.get(id=influencer_id)
        if inf.date_created_hash != date_created_hash:
            raise Http404()
        return view(request, influencer_id)
    return _wrapped


def disable_view(view):
    @wraps(view)
    def decorator(request, *args, **kwargs):
        return redirect(reverse('debra.account_views.home'))
        #raise Http404("Page is currently disabled.")
    return decorator


def include_template(method_field):
    template_name = method_field.__name__.split('get_')[1]
    @wraps(method_field)
    def _wrapped(self, obj):
        data = method_field(self, obj) or {}
        data.update({
            'include_template': dict(self.FIELD_TEMPLATES).get(template_name)
        })
        return data
    return _wrapped


def editable_field(field_type=None, editable=True, placeholder=None,
        related_obj_name=None, field_name=None, model_name=None):
    def _wrap(method_field):
        @wraps(method_field)
        def _wrapped(self, obj, field_name=field_name, model_name=model_name):
            field_name = field_name or method_field.__name__.split('get_')[1]
            editable_obj = obj if related_obj_name is None else getattr(
                obj, related_obj_name)
            data = {
                'include_template': 'snippets/generic_table/editable_field.html',
                'model_name': model_name or editable_obj.__class__.__name__,
                'field_type': field_type,
                'field_name': field_name,
                'field_value': getattr(editable_obj, field_name, None),
                'id': getattr(editable_obj, 'id', None),
                'disable_editing': not editable,
                'placeholder': placeholder,
                'default_values': {},
            }
            data.update(method_field(self, obj) or {})
            return data
        return _wrapped
    return _wrap
