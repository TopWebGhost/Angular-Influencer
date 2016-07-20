import json
from django.core.serializers.json import DjangoJSONEncoder
from django.http import HttpResponse
from django.middleware.csrf import get_token
from debra.forms import ContactUsForm, AddNewUserForm


def contact_us_form(request):

    data = {}
    form = ContactUsForm()
    form.is_bound = True
    form.fields["name"].widget.attrs["class"] = "req"
    form.fields["email"].widget.attrs["class"] = "req email"
    form.fields["subject"].widget.attrs["class"] = "req"
    form.fields["message"].widget.attrs["class"] = "req"
    form.fields["captcha"].widget.attrs["class"] = "req captcha"
    data["name"] = str(form["name"])
    data["email"] = str(form["email"])
    data["subject"] = str(form["subject"])
    data["message"] = str(form["message"])
    data["captcha"] = str(form["captcha"])
    data["token"] = get_token(request)
    if request.is_ajax():
        data = json.dumps(data, cls=DjangoJSONEncoder, default=lambda obj: None)
        return HttpResponse(data, content_type="application/json")
    else:
        data = json.dumps(data, cls=DjangoJSONEncoder, default=lambda obj: None, indent=4)
        return HttpResponse("<body><pre>%s</pre></body>" % data)


def add_new_user_form(request):

    data = {}
    form = AddNewUserForm()
    form.is_bound = True

    data["name"] = str(form["name"])
    data["email"] = str(form["email"])
    # data["captcha"] = str(form["captcha"])
    data["token"] = get_token(request)

    if request.is_ajax():
        data = json.dumps(data, cls=DjangoJSONEncoder, default=lambda obj: None)
        return HttpResponse(data, content_type="application/json")
    else:
        data = json.dumps(data, cls=DjangoJSONEncoder, default=lambda obj: None, indent=4)
        return HttpResponse("<body><pre>%s</pre></body>" % data)