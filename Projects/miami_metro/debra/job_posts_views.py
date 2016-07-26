import logging
import time
import traceback
import random
import uuid
import os
import sys
from io import BytesIO

from django.conf import settings
from django.db.models import Q, get_model
from django.shortcuts import render, redirect, get_object_or_404
from django.shortcuts import render_to_response
from django.template.loader import render_to_string, get_template_from_string
from django.template.defaultfilters import filesizeformat
from django.template import RequestContext, Template, Context
from django.utils.safestring import mark_safe
from django.contrib.auth.decorators import login_required
from django.http import (
    HttpResponseForbidden, HttpResponse, HttpResponseBadRequest, Http404,
    HttpResponseRedirect)
from django.core.serializers.json import DjangoJSONEncoder
from django.core.urlresolvers import reverse
from django.core.exceptions import PermissionDenied, ObjectDoesNotExist
from django.core.cache import get_cache
from django.views.generic import RedirectView, View
from django.views.decorators.csrf import csrf_exempt

from mailsnake import MailSnake
from collections import OrderedDict, defaultdict, Counter
import bleach
import pyPdf
import requests
import dateutil
import magic

from debra.templatetags.custom_filters import common_date_format
from debra import mongo_utils
from debra.decorators import user_is_brand_user, brand_view, cached_property
from debra import search_helpers
from debra import account_helpers
from debra import constants
from debra.models import *
from debra.forms import JobPostForm
from debra.serializers import AdminInfluencerSerializer, ConversationSerializer
from debra.partials_baker import *
from debra.helpers import (
    extract_attachments, render_and_send_message,
    send_admin_email_via_mailsnake, convert_camel_case_to_underscore,
    format_filename, OrderedDefaultdict, PageSectionSwitcher,
    name_to_underscore)
from debra.base_views import (BaseView, BaseTableViewMixin)
from masuka.image_manipulator import (
    reassign_campaign_cover, get_bucket, BUCKET_PATH_PREFIX)


log = logging.getLogger('debra.job_post_views')


@brand_view
def list_jobs(request, brand, base_brand):
    posts = BrandJobPost.objects.brand_campaigns(base_brand, brand)

    context = {
        'selected_tab': 'campaign',
        'sub_page': 'brand_assets',
        'posts': posts,
    }
    return render(request, 'pages/job_posts/list.html', context)


@brand_view
def delete(request, brand, base_brand, id):
    job_post = get_object_or_404(BrandJobPost, Q(id=id)&Q(creator=brand)&Q(oryg_creator=base_brand))
    # job_post.delete()
    job_post.archived = True
    job_post.save()
    # bake_list_details_partial_async(brand, base_brand)
    return HttpResponse()


@brand_view
def list_as_bloggers(request, brand, base_brand):
    posts = BrandJobPost.objects.exclude(archived=True).filter(Q(creator=brand)&Q(oryg_creator=base_brand))
    context = {
        'selected_tab': 'outreach',
        'sub_page': 'job_posts',
        'posts': posts,
    }
    return render(request, 'pages/job_posts/list_as_bloggers.html', context)


def upload_campaign_attachment(request):
    allowed_mimes = ['application/pdf']
    brand = request.visitor["base_brand"]
    try:
        rfile = request.FILES['file'].read()
    except Exception, e:
        log.exception("Can't read file.")
    if not brand or not brand.is_subscribed:
        return HttpResponseForbidden()
    if not "file" in request.FILES:
        return HttpResponseBadRequest()
    elif magic.from_buffer(rfile, mime=True) not in allowed_mimes:
        return HttpResponseBadRequest("Should be PDF file.")
    elif len(rfile) > constants.MAX_CAMPAIGN_ATTACHMENT_SIZE:
        return HttpResponseBadRequest("The file size shouldn't exceed {}. If this is critical for your campaign, you can send this file to us directly at laurenj@theshelf.com.".format(filesizeformat(constants.MAX_CAMPAIGN_ATTACHMENT_SIZE)))
    name = "/tmp/%s" % str(uuid.uuid4())
    try:
        f = open(name, 'wb')
        f.write(rfile)
        f.close()
    except Exception, e:
        log.exception("Can't write file to tmp folder - ".format(name))
    request.session["campaign_attachment"] = name
    return HttpResponse()


def upload_message_attachment(request):
    try:
        if not "file" in request.FILES:
            return HttpResponseBadRequest()

        name = "tmp_%s" % str(uuid.uuid4())
        # f = open(name, "wb")
        # f.write(request.FILES["file"].read())
        # f.close()

        bucket = get_bucket('message-attachments-tmp')
        new_key = bucket.new_key(name)

        content = request.FILES["file"].read()
        file_type = magic.from_buffer(content, mime=True)
        new_key.set_contents_from_string(
            content,
            headers={'Content-Type': file_type})
        new_key.set_acl('public-read')

        file_item = {
            'path': name,
            'filename': request.FILES["file"].name
        }
        print file_item
        return HttpResponse(json.dumps(file_item), content_type="application/json")
    except:
        account_helpers.send_msg_to_slack(
            'attachment-crashes',
            "{traceback}\n"
            "{delimiter}"
            "\n".format(
                delimiter="=" * 120,
                traceback=traceback.format_exc(),
            )
        )

    return HttpResponse()


def download_message_attachment(request, message_id, attachment_name):
    from boto.s3.key import Key
    s = BytesIO()
    bucket = get_bucket('theshelf-email-attachments')
    filename = "%i_%s" % (int(message_id), attachment_name)
    key = Key(bucket)
    key.key = filename
    key.get_contents_to_file(s)
    content = s.getvalue()
    mimetype = magic.from_buffer(content, mime=True)

    response = HttpResponse(content)
    response['Content-Type'] = mimetype
    response['Content-Disposition'] = 'attachment; filename=%s' % (attachment_name,)
    return response

    # return HttpResponse(content, mimetype=mimetype)


def upload_attachment_to_s3(brand, base_brand, campaign_id, file_path):
    bucket = get_bucket('campaign-attachments')
    file_name = "%i_%i_%i_attachment.pdf" % (brand.id, base_brand.id, campaign_id)
    try:
        new_key = bucket.new_key(file_name)
        new_key.set_contents_from_filename(file_path, headers={'Content-Type': 'application/pdf'})
        new_key.set_acl('public-read')
        return BUCKET_PATH_PREFIX + 'campaign-attachments/' + file_name
    except Exception, e:
        log.exception('S3 attachment upload exception')

@brand_view
def add(request, brand, base_brand):
    """
    Add campaign
    """
    import datetime
    job_post = BrandJobPost(creator=brand)
    if request.method == "POST":
        form = JobPostForm(request.POST, instance=job_post)

        if form.is_valid():
            post = form.save(commit=False)

            post.creator = brand
            post.oryg_creator = base_brand

            if request.GET.get('publish') == 'true':
                post.published = True
                post.date_publish = date.today()

            if not post.collection:
                post.create_system_collection()

            post.save()

            if "campaign_attachment" in request.session:
                url = upload_attachment_to_s3(brand, base_brand, post.id, request.session["campaign_attachment"])
                post.attachment_url = url
                post.save()
                del request.session["campaign_attachment"]

            if post.cover_img_url and "tmp_cover_img" in post.cover_img_url:
                reassign_campaign_cover(post.id)
            return redirect(reverse('debra.job_posts_views.list_details_jobpost', args=(post.id,)))
    else:
        form = JobPostForm(instance=job_post)
    plan_name = request.visitor["base_brand"].stripe_plan
    context = {
        'selected_tab': 'outreach',
        'sub_page': 'job_posts',
        'collab_types': InfluencerCollaborations.COLLABORATION_TYPES,
        'collections': request.visitor["brand"].influencer_groups.filter(creator_brand=brand, system_collection=False),
        'form': form,
        'op': 'Add',
        'is_edit': False,
        'action': reverse('debra.job_posts_views.add'),
        'max_campaign_attachment_size': constants.MAX_CAMPAIGN_ATTACHMENT_SIZE,
        'min_date': datetime.date.today(),
    }
    context.update(search_helpers.prepare_filter_params(context, plan_name=plan_name))
    return render(request, 'pages/job_posts/create_jobpost.html', context)


@brand_view
def edit(request, brand, base_brand, id):
    """
    Edit campaign
    """
    import datetime
    job_post = get_object_or_404(BrandJobPost, id=id, creator=brand)
    job_post_oryg = BrandJobPost.objects.get(id=id)
    if request.method == "POST":
        form = JobPostForm(request.POST, instance=job_post)
        if form.is_valid():
            post = form.save(commit=False)
            if request.GET.get('publish') == 'true':
                post.published = True
                post.date_publish = date.today()

            if not post.collection:
                if job_post_oryg.collection and job_post_oryg.collection.system_collection:
                    post.collection = job_post_oryg.collection
                else:
                    post.create_system_collection()

            post.save()
            if "campaign_attachment" in request.session:
                url = upload_attachment_to_s3(brand, base_brand, post.id, request.session["campaign_attachment"])
                post.attachment_url = url
                post.save()
                del request.session["campaign_attachment"]

            if post.cover_img_url and "tmp_cover_img" in post.cover_img_url:
                reassign_campaign_cover(post.id)
            post.rebake()
            return redirect(reverse('debra.job_posts_views.list_details_jobpost', args=(job_post.id,)))
    else:
        form = JobPostForm(instance=job_post)
    plan_name = base_brand.stripe_plan
    context = {
        'selected_tab': 'outreach',
        'sub_page': 'job_posts',
        'collab_types': InfluencerCollaborations.COLLABORATION_TYPES,
        'collections': brand.influencer_groups.filter(creator_brand=base_brand, system_collection=False),
        'form': form,
        'op': 'Edit',
        'is_edit': True,
        'job_post': job_post,
        'action': reverse('debra.job_posts_views.edit', args=(id,)),
        'max_campaign_attachment_size': constants.MAX_CAMPAIGN_ATTACHMENT_SIZE,
        'min_date': datetime.date.today(),
    }
    # context.update(search_helpers.prepare_filter_params(context, plan_name=plan_name))
    return render(request, 'pages/job_posts/create_jobpost.html', context)


@brand_view
def view(request, brand, base_brand, id):
    """
    Campaign preview
    """
    from debra.search_helpers import get_social_data

    job_post = get_object_or_404(BrandJobPost, id=id, creator=brand)

    other_camps = job_post.creator.job_posts.all().exclude(archived=True).exclude(id=id)[:4]

    social_data = get_social_data(job_post.creator.pseudoinfluencer, None)

    context = {
        'selected_tab': 'outreach',
        'sub_page': 'job_posts',
        'social_data': social_data,
        'job_post': job_post,
        'hide_sidebar': False,
        'filters': job_post.filter_json and json.loads(job_post.filter_json),
        'other_camps': other_camps,
    }
    return render(request, 'pages/job_posts/view.html', context)


@login_required
def reassign_campaign_cover(request, campaign_id):
    from masuka.image_manipulator import reassign_campaign_cover
    reassign_campaign_cover(campaign_id)
    return HttpResponse()


def invite(request, map_id):
    """
    Campaign invitation page
    """
    from debra.search_helpers import get_social_data

    try:
        mapping = InfluencerJobMapping.objects.get(id=map_id)
    except InfluencerJobMapping.DoesNotExist:
        return invite_old(request, map_id)
    active = mapping.status != InfluencerJobMapping.STATUS_ACCEPTED
    influencer = mapping.influencer
    signed_up = False
    logged_in = False

    next_url = request.get_full_path() + "?next="+request.get_full_path()
    if influencer.shelf_user:
        signed_up = True
        if request.visitor["influencer"] == influencer:
            logged_in = True
            if active:
                mapping.status = InfluencerJobMapping.STATUS_VISITED
                mapping.save()
        elif request.GET.get('next') != request.path:
            return redirect(next_url)

    job_post = mapping.job

    # here we want to retrieve other brand's campaigns to which our
    # visitor influencer has beed invited
    # (we're not checking the status of mapping here)
    other_camps = influencer.invitations.filter(
        Q(job__creator=job_post.creator) & 
        ~(Q(job__archived=True) | Q(job__id=job_post.id)))[:4]

    social_data = get_social_data(job_post.creator.pseudoinfluencer, None)

    context = {
        'selected_tab': 'outreach',
        'sub_page': 'job_posts',
        'job_post': job_post,
        'mapping': mapping,
        'signed_up': signed_up,
        'logged_in': logged_in,
        'active': active,
        'extra_body_class': 'get_rid_of_margin',
        'filters': job_post.filter_json and json.loads(job_post.filter_json),
        'social_data': social_data,
        'other_camps': other_camps,
    }
    return render(request, 'pages/job_posts/invite.html', context)


@brand_view
def send_invitation(request, brand, base_brand, **kwargs):
    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    send_mode = data.get('send_mode', 'normal') or 'normal'
    assert send_mode in ['normal', 'test', 'dev_test']

    userprofile = request.visitor['auth_user'].userprofile

    job_id = data.get('job_id')
    ijm_id = data.get('ijm_id')
    # if not job_id and userprofile.flag_default_invitation_campaign and not data.get('no_job'):
    #     job_id = userprofile.flag_default_invitation_campaign
    group_id = data.get('group_id')
    influencer_id = data.get('influencer_id')
    influencer_analytics_id = data.get('influencer_analytics_id')

    print '* sending invitation: job_id={}, group_id={}, inf_id={}'.format(
        job_id, group_id, influencer_id)

    mp, job, job_mapping = [None] * 3

    influencer = None

    if send_mode in ['test', 'dev_test']:
        if job_id:
            job = BrandJobPost.objects.get(id=job_id)
    else:
        influencer = Influencer.objects.get(id=influencer_id)
        try:
            if ijm_id:
                job_mapping = InfluencerJobMapping.objects.get(
                            id=ijm_id)
                mp = job_mapping.mailbox
            if not mp:
                mp = MailProxy.create_box(base_brand, influencer)
            if not job_id:
                # we have no link to the campaign
                if not group_id:
                    # have no relation to any collection, so just create a new
                    # mailbox
                    pass
                else:
                    # have relation to some collection, so need to create a new
                    # <Influencer, Collection> mapping with its own mailbox
                    InfluencerGroupMapping.objects.create(
                        influencer_id=influencer_id,
                        group_id=group_id,
                        mailbox=mp)
            else:
                job = BrandJobPost.objects.get(id=job_id)
                # we have a link to the campaign
                if not job_mapping and job_id in influencer.job_ids:
                    # user has already been invited to this campaign
                    return HttpResponseBadRequest()
                # influencer has not been invited to this campaign yet
                if not group_id:
                    # just invitation from search page etc
                    # (not from the collection page)
                    if job_mapping:
                        if not job_mapping.mailbox_id:
                            job_mapping.mailbox = mp
                            job_mapping.save()
                    else:
                        job_mapping = InfluencerJobMapping.objects.create(
                            job_id=job_id,
                            mailbox=mp
                        )
                    # Setting campaign stage
                    job_mapping.campaign_stage = InfluencerJobMapping.CAMPAIGN_STAGE_WAITING_ON_RESPONSE
                    job_mapping.save()
                    # if request.user.userprofile.flag_can_edit_contracts:
                    if not job_mapping.contract_id:
                        contract = Contract()
                        contract._ignore_old = True
                        contract.save()

                        job_mapping.contract = contract
                        job_mapping.save()

                        # call the tracking stuff
                        contract = Contract.objects.get(id=contract.id)
                        contract._newly_created = True
                        contract.save()
                else:
                    # invitation sent from particular collection's page
                    try:
                        # just use any Mapping, because we don't need its
                        # mailbox
                        mapping = InfluencerGroupMapping.objects.filter(
                            influencer__id=influencer_id, group__id=group_id
                        )[0]
                    except IndexError:
                        mapping = InfluencerGroupMapping.objects.create(
                            influencer_id, group_id=group_id)
                    job_mapping = InfluencerJobMapping.objects.create(
                        mapping=mapping, job_id=job_id, mailbox=mp)
        except ObjectDoesNotExist:
            return HttpResponseBadRequest()

    sender = request.visitor[
        'dev_user' if send_mode == 'dev_test' else 'auth_user']

    default_subject = """
        We at {} love your blog---interested in working together?""".format(
            brand.name.capitalize())

    resp = render_and_send_message(
        mp=mp,
        brand=brand,
        sender=sender,
        template_name='pages/job_posts/invitation_email.html',
        data=data,
        influencer=influencer,
        job_mapping=job_mapping,
        job=job,
        send_mode=send_mode,
        default_subject=default_subject,
        user=request.visitor["auth_user"],
    )

    if send_mode not in ['test', 'dev_test']:
        account_helpers.intercom_track_event(
            request, "brand-send-invitation", {
                'sent as brand': brand.domain_name,
                'brand': base_brand.domain_name,
                'influencer': influencer.name,
            })

    data = {
        'mandrillResponse': resp,
        'data': {
            'mailboxId': mp.id if mp else None,
        }
    }
    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


@brand_view
def send_response(request, brand, base_brand):
    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    send_mode = data.get('send_mode') or 'normal'
    assert send_mode in ['normal', 'test', 'dev_test']

    mapping = None
    mailbox = None
    influencer = None

    if data.get('thread') == "job":
        mapping = get_object_or_404(
            InfluencerJobMapping, id=data.get('map_id'))
        influencer = mapping.influencer
    elif data.get('thread') == "collection":
        mapping = get_object_or_404(
            InfluencerGroupMapping, id=data.get('map_id'))
        influencer = mapping.influencer
    elif data.get('thread') == "generic" or data.get('thread') is None:
        mailbox = get_object_or_404(MailProxy, id=data.get('map_id'))
        influencer = mailbox.influencer

    if mapping:
        mp = mapping.get_or_create_mailbox()
    else:
        mp = mailbox

    default_subject = "Response from %s" % brand.name.capitalize()
    sender = request.visitor[
        'dev_user' if send_mode == 'dev_test' else 'auth_user']

    try:
        job_mapping = mailbox.candidate_mapping.all()[0]
        job = job_mapping.job
    except IndexError:
        job_mapping = None
        job = None

    if type(data.get('template')) == dict:
        data['subject'] = data['template'].get('subject')
        data['template'] = data['template'].get('body')

    resp = render_and_send_message(
        mp=mp,
        brand=brand,
        sender=sender,
        template_name='pages/job_posts/response_email.html',
        data=data,
        send_mode=send_mode,
        default_subject=default_subject,
        job_mapping=job_mapping,
        job=job,
    )

    print 'WITH LINK:', data.get('with_link', False)

    if send_mode not in ['test', 'dev_test']:
        account_helpers.intercom_track_event(request, "brand-send-response", {
            'sent as brand': brand.domain_name,
            'brand': base_brand.domain_name,
            'influencer id': influencer.id,
        })

    return HttpResponse(resp, content_type="applicants/json")


@brand_view
def send_message(request, brand, base_brand):
    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    send_mode = data.get('send_mode') or 'normal'
    assert send_mode in ['normal', 'test', 'dev_test']

    influencer = get_object_or_404(Influencer, id=data.get('id'))

    mps = MailProxy.objects.filter(
        brand=base_brand,
        influencer=influencer,
        mapping__isnull=True,
        candidate_mapping__isnull=True
    )
    if mps:
        mp = mps[0]
    else:
        mp = MailProxy.create_box(brand=base_brand, influencer=influencer)

    default_subject = "Response from %s" % brand.name.capitalize()
    sender = request.visitor[
        'dev_user' if send_mode == 'dev_test' else 'auth_user']

    resp = render_and_send_message(
        mp=mp,
        brand=brand,
        sender=sender,
        template_name='pages/job_posts/response_email.html',
        data=data,
        send_mode=send_mode,
        default_subject=default_subject,
    )

    if send_mode not in ['test', 'dev_test']:
        account_helpers.intercom_track_event(request, "brand-send-message", {
            'sent as brand': brand.domain_name,
            'brand': base_brand.domain_name,
            'influencer id': influencer.id,
        })

    return HttpResponse(resp, content_type="applicants/json")


def apply_invitation(request, map_id):
    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    try:
        mapping = InfluencerJobMapping.objects.get(id=map_id)
    except InfluencerJobMapping.DoesNotExist:
        return apply_invitation_old(request, map_id)

    job = mapping.job

    context = {
        'influencer': request.visitor["influencer"],
        'mapping': mapping,
        'job': job,
        'note': account_helpers.get_bleached_template(data.get('template')),
    }

    rendered_message = render_to_string(
        'pages/job_posts/apply_email.html', context)
    rendered_message = rendered_message.encode('utf-8')

    mp = mapping.get_or_create_mailbox()

    attachments = extract_attachments(data)

    mp.send_email_as_influencer(
        subject="Invitation accepted",
        body=rendered_message,
        attachments=attachments
    )

    mapping.status = InfluencerJobMapping.STATUS_ACCEPTED
    mapping.save()

    return HttpResponse()


@login_required
@user_is_brand_user
def list_details(request, group_id, **kwargs):

    for_admin = kwargs.get('section') == 'admin'

    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand or not base_brand.is_subscribed or not base_brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        ig = InfluencersGroup.objects.exclude(archived=True)
        group = ig.get(id=group_id, owner_brand=brand, creator_brand=base_brand)
    except InfluencersGroup.DoesNotExist:
        raise Http404()

    # cache = get_cache('long')
    # partial = cache.get("partial_list_details_%s" % group_id)
    partial = None
    if not partial or settings.USE_BAKED_PARTIALS == False:
        partial = bake_list_details_partial(
            group_id, page=request.GET.get('page'),
            for_admin=for_admin, request=request)
        
    account_helpers.intercom_track_event(request, "brand-view-collection", {
        'collection_name': group.name,
    })

    context = {
        'sub_page': 'favorited',
        'selected_tab': 'outreach',
        'partial_content': partial,
    }

    return render(request, 'pages/job_posts/bloggers_favorited_table.html', context)


@login_required
@user_is_brand_user
def list_details_jobpost(request, job_id, **kwargs):
    section = kwargs.get('section')
    if section is not None and section not in ['candidates', 'applicants']:
        return Http404()
    brand = request.visitor["base_brand"]
    if not brand or not brand.is_subscribed or not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        jobs = BrandJobPost.objects.exclude(archived=True)
        job = jobs.get(id=job_id, creator=request.visitor["brand"], oryg_creator=request.visitor["base_brand"])
    except BrandJobPost.DoesNotExist:
        raise Http404()

    # cache = get_cache('long')
    # partial = cache.get("partial_list_details_jobpost_%s" % job_id)
    partial = None
    if not partial or settings.USE_BAKED_PARTIALS == False:
        kw = {
            'show_candidates': section is None or section in ['candidates'],
            'show_applicants': section in ['applicants'],
            'page': request.GET.get('page', 1)
        }
        partial = bake_list_details_jobpost_partial(
            job_id, request=request, **kw)
    context = {
        'partial_content': partial,
        'hide_sidenav': True,
    }
    account_helpers.intercom_track_event(request, "brand-view-job-list", {
        'job_id': job_id,
    })
    return render(request, 'pages/job_posts/job_candidates_list.html', context)


@login_required
def get_job_collection_associations(request, job_id):
    mongo_utils.track_visit(request)

    brand = request.visitor["brand"]
    base_brand = request.visitor["base_brand"]
    if not base_brand:
        return redirect('/')
    if not base_brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    if request.method == "POST":
        try:
            data = json.loads(request.body)
        except ValueError:
            return HttpResponseBadRequest()
        if data.get('value') is None:
            post.create_system_collection()
            return HttpResponse()
        job = get_object_or_404(BrandJobPost, id=job_id, oryg_creator=base_brand, creator=brand)
        collection = get_object_or_404(InfluencersGroup, id=data.get('value'), creator_brand=base_brand, owner_brand=brand)
        job.collection = collection
        job.save()
        return HttpResponse()
    else:
        job = get_object_or_404(BrandJobPost, id=job_id, oryg_creator=base_brand, creator=brand)
        if job.collection and not job.collection.system_collection:
            current = {
                'value': job.collection.id,
                'text': job.collection.name,
            }
        else:
            current = {
                'value': None,
                'text': "Unlinked"
            }
        all_associations = []
        all_associations.append({
            "value": None,
            "text": "Unlinked",
        })
        for collection in InfluencersGroup.objects.filter(owner_brand=brand, creator_brand=base_brand, system_collection=False):
            all_associations.append({
                "value": collection.id,
                "text": collection.name,
            })
        job_association = {
            'current': current,
            'all': all_associations,
        }
        return HttpResponse(json.dumps(job_association), content_type="application/json")


@login_required
def get_post_analytics_collections(request):
    mongo_utils.track_visit(request)

    brand = request.visitor["base_brand"]

    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    post_id = request.GET.get('post')

    try:
        post_id = int(post_id)
    except:
        post_id = None
        post = None
    else:
        post = get_object_or_404(Posts, id=post_id)

    existing = brand.created_post_analytics_collections.exclude(
        archived=True
    ).prefetch_related(
        'postanalytics_set'
    ).order_by(
        'name'
    )

    collections = []
    for collection in existing:
        collection_def = {
            'id': collection.id,
            'name': collection.name,
            'type': 'collection',
            'selected': False
        }

        if post is not None:

            with_post = filter(
                lambda x: x.post_id == post_id,
                collection.postanalytics_set.all()
            )

            if len(with_post) > 0:
                collection_def['selected'] = True
                collection_def['with_post'] = True
                # continue

            # with_post_url = filter(
            #     lambda x: x.post_url == post.url,
            #     collection.postanalytics_set.all()
            # )

            # if len(with_post_url) > 0:
            #     collection_def['selected'] = True
            #     collection_def['with_post_url'] = True

        collections.append(collection_def)

    data = {
        "groups": collections,
        "img_url": post.post_img if post else None
    }
    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


@login_required
def set_post_analytics_collections(request):
    from debra.brand_helpers import handle_post_analytics_urls
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    post_id = data.get('post')
    post_ids = data.get('posts')
    if post_ids:
        urls_data = list(Posts.objects.filter(id__in=post_ids).values_list(
            'id', 'url'))
    else:
        post = get_object_or_404(Posts, id=post_id)
        urls_data = [(post.id, post.url)]

    post_ids = [x[0] for x in urls_data]
    post_urls = [x[1] for x in urls_data]

    groups = data.get('groups')

    qs = PostAnalyticsCollection.objects.filter(
        id__in=[x.get('id') for x in groups],
        creator_brand=brand)
    groups_mapping = {g.id: g for g in qs}

    for group in groups:
        group_id = group.get('id')
        group_selected = group.get('selected', False)

        try:
            group_instance = groups_mapping[group_id]
        except KeyError:
            return HttpResponseBadRequest()

        if group_selected:
            handle_post_analytics_urls(
                post_urls,
                collection=group_instance,
                refresh=True,
                post_ids=post_ids)
        else:
            group_instance.remove(post_urls, post_ids)

    data = {
        'is_bookmarked': any(g.get('selected', False) for g in groups)
    }
    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


@login_required
def get_influencer_groups(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    influencer_id = request.GET.get('influencer')
    brand = request.visitor["base_brand"]

    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    influencer = get_object_or_404(
        Influencer, id=influencer_id) if influencer_id is not None else None

    groups_qs = request.visitor["brand"].influencer_groups.prefetch_related(
        # 'influencers_mapping__influencer__shelf_user__userprofile',
    ).exclude(
        archived=True
    ).filter(
        creator_brand=brand,
        system_collection=False
    ).order_by(
        'name'
    )

    groups = []
    for group in groups_qs:
        group_def = {
            'id': group.id,
            'name': group.name,
            'type': "collection",
            'selected': False,
        }

        influencers_mapping = group.influencers_mapping.exclude(
            status=InfluencerGroupMapping.STATUS_REMOVED
        )

        group_def["selected"] = influencers_mapping.filter(
            influencer__id=influencer_id
        ).exists() if influencer_id is not None else False

        try:
            group_def["img"] = influencers_mapping[0].influencer.profile_pic
        except (IndexError, AttributeError):
            pass

        groups.append(group_def)

    try:
        note = InfluencerBrandUserMapping.objects.filter(
            user_id=request.user.id, influencer_id=influencer_id
        ).values_list('notes', flat=True)[0]
    except IndexError:
        note = None

    data = {
        "groups": groups,
        "img_url": influencer.profile_pic if influencer else None,
        "note": note,
    }
    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


@login_required
def set_influencer_groups(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    print json.dumps(data, indent=4)

    influencer = data.get('influencer')
    influencers = set(data.get('influencers', []))

    try:
        influencer = Influencer.objects.get(id=influencer)
    except Influencer.DoesNotExist:
        if not influencers:
            return HttpResponseBadRequest()
        influencers = Influencer.objects.filter(id__in=influencers)
    else:
        influencers = [influencer]

    groups = data.get('groups')
    bake_jobs = []
    for group in groups:
        if group.get('type') == "job":
            job = BrandJobPost.objects.get(id=group.get('id'))
            if job.collection:
                group_id = job.collection.id
            else:
                group_id = job.create_system_collection().id
        elif group.get('type') == "collection":
            group_id = group.get('id')
        group_selected = group.get('selected', False)
        try:
            group = InfluencersGroup.objects.get(id=group_id, owner_brand=request.visitor["brand"])
        except InfluencersGroup.DoesNotExist:
            return HttpResponseBadRequest()

        if group_selected:
            for influencer in influencers:
                created = group.add_influencer(influencer)
                if data.get('note'):
                    mapping, _ = InfluencerBrandUserMapping.objects.get_or_create(
                        influencer=influencer, user=request.user)
                    mapping.notes = data.get('note')
                    mapping.save()
                if created:
                    mongo_utils.track_query("brand-add-to-collection", {
                        'collection_name': group.name,
                        'blog_url': influencer.blog_url
                    }, {"user_id": request.visitor["auth_user"].id})
                    mongo_utils.influencer_inc_dec_collection(influencer.id, 1);
                    account_helpers.intercom_track_event(request, "brand-add-to-collection", {
                        'collection_name': group.name,
                        'blog_url': influencer.blog_url
                    })
        else:
            for influencer in influencers:
                removed = group.remove_influencer(influencer)
                if removed:
                    mongo_utils.track_query("brand-delete-from-collection", {
                        'collection_name': group.name,
                        'blog_url': influencer.blog_url
                    }, {"user_id": request.visitor["auth_user"].id})
                    mongo_utils.influencer_inc_dec_collection(influencer.id, -1);
                    account_helpers.intercom_track_event(request, "brand-delete-from-collection", {
                        'collection_name': group.name,
                        'blog_url': influencer.blog_url
                    })

    return HttpResponse()


@login_required
def add_post_analytics_collection(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    existing = brand.created_post_analytics_collections.exclude(
        archived=True).filter(name=data.get('name'))

    if existing.exists():
        return HttpResponseBadRequest(
            'Post Analytics Collection with such name already exists',
            content_type='application/json')

    collection = PostAnalyticsCollection()
    collection.name = data.get('name')
    collection.creator_brand = brand
    collection.user = request.user
    collection.items_number = 0
    collection.save()

    data = {
        'id': collection.id,
        'name': collection.name,
        'selected': True,
        'type': 'collection'
    }

    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


@login_required
def edit_post_analytics_collection(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    existing = request.visitor["base_brand"].created_post_analytics_collections.exclude(
        archived=True).exclude(id=data.get('id')).filter(name=data.get('name'))

    if existing.exists():
        return HttpResponseBadRequest(
            'Post Analytics Collection with such name already exists',
            content_type='application/json')

    collection = get_object_or_404(
        PostAnalyticsCollection, id=data.get('id'), creator_brand=brand)

    collection.name = data.get('name')
    collection.save()

    return HttpResponse()


@login_required
def del_post_analytics_collection(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    collection = get_object_or_404(
        PostAnalyticsCollection, id=data.get('id'), creator_brand=brand)

    collection.archived = True
    collection.save()

    return HttpResponse()


@login_required
def add_roi_prediction_report(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    existing = brand.created_roi_prediction_reports.exclude(
        archived=True).filter(name=data.get('name'))

    if existing.exists():
        return HttpResponseBadRequest(
            'ROI-Prediction Report with such name already exists',
            content_type='application/json')

    try:
        collection_id = int(data.get('selected_collection_id'))
    except TypeError:
        collection_id = None
    collection_name = data.get('new_collection_name')

    report = ROIPredictionReport()
    report.name = data.get('name')
    report.creator_brand = brand
    report.user = request.user

    if collection_id is not None:
        try:
            brand.created_post_analytics_collections.exclude(
                archived=True).get(id=collection_id)
        except PostAnalyticsCollection.DoesNotExist:
            return HttpResponseBadRequest(
                'No such post analytics collection',
                content_type='application/json'
            )
        else:
            report.post_collection_id = collection_id
    elif collection_name is not None:
        collection_exists = brand.created_post_analytics_collections.exclude(
            archived=True).filter(name=collection_name).exists()
        if collection_exists:
            return HttpResponseBadRequest(
                'Post Analytics Collection with such name already exists',
                content_type='application/json'
            )
        else:
            new_collection = PostAnalyticsCollection()
            new_collection.name = collection_name
            new_collection.creator_brand = brand
            new_collection.user = request.user
            new_collection.items_number = 0
            new_collection.save()

            report.post_collection_id = new_collection.id
    else:
        return HttpResponseBadRequest('''You should provide name for 
            a new post analytics collection or select existed one.''',
            content_type='application/json'
        )

    report.save()

    return HttpResponse()


@login_required
def edit_roi_prediction_report(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    existing = request.visitor["base_brand"].created_roi_prediction_reports.exclude(
        archived=True).exclude(id=data.get('id')).filter(name=data.get('name'))

    if existing.exists():
        return HttpResponseBadRequest(
            'ROI-Prediction Report with such name already exists',
            content_type='application/json')

    report = get_object_or_404(
        ROIPredictionReport, id=data.get('id'), creator_brand=brand)

    report.name = data.get('name')
    report.save()

    return HttpResponse()


@login_required
def del_roi_prediction_report(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    report = get_object_or_404(
        ROIPredictionReport, id=data.get('id'), creator_brand=brand)

    report.archived = True
    report.save()

    return HttpResponse()


@login_required
def add_influencer_groups(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    brand_groups = request.visitor["brand"].influencer_groups.filter(name=data.get("name"), creator_brand=brand, system_collection=False)

    if brand_groups.exists():
        return HttpResponseBadRequest("Collection with such name already exists",
             content_type="application/json")

    group = InfluencersGroup()
    group.name = data.get("name")
    group.owner_brand = request.visitor["brand"]
    group.creator_brand = request.visitor["base_brand"]
    group.creator_userprofile = request.visitor["user"]
    group.save()

    settings.REDIS_CLIENT.sadd('btags_{}'.format(group.creator_brand.id),
        group.id)

    for job_id in data.get('jobs', []):
        group.job_post.add(BrandJobPost.objects.get(id=job_id))

    data = {
        'id': group.id,
        'name': group.name,
        'selected': True,
        'type': 'collection'
    }

    mongo_utils.track_query("brand-create-collection", {
        'collection_name': group.name,
    }, {"user_id": request.visitor["auth_user"].id})

    account_helpers.intercom_track_event(request, "brand-create-collection", {
        'collection_name': group.name,
    })

    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


@login_required
def edit_influencer_groups(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    group = get_object_or_404(InfluencersGroup, id=data.get('id'), creator_brand=brand, owner_brand=request.visitor["brand"])

    brand_groups = request.visitor["brand"].influencer_groups.exclude(id=group.id).filter(name=data.get("name"), creator_brand=brand, system_collection=False)

    if brand_groups.exists():
        return HttpResponseBadRequest("Collection with such name already exists",
             content_type="application/json")

    group.name = data.get('name')
    group.description = data.get('description')
    group.save()
    group.rebake()
    group.job_post.clear()
    for job_id in data.get('jobs', []):
        group.job_post.add(BrandJobPost.objects.get(id=job_id))

    return HttpResponse()


@login_required
def delete_influencer_groups(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    group = get_object_or_404(InfluencersGroup, id=data.get('id'), creator_brand=brand, owner_brand=request.visitor["brand"])

    for mapping in group.influencers_mapping.all():
        mongo_utils.influencer_inc_dec_collection(mapping.influencer.id, -1);

    mongo_utils.track_query("brand-delete-collection", {
        'collection_name': group.name,
    }, {"user_id": request.visitor["auth_user"].id})

    account_helpers.intercom_track_event(request, "brand-delete-collection", {
        'collection_name': group.name,
    })
    group.archived = True
    group.save()

    return HttpResponse()


@login_required
def remove_influencer_from_groups(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    group = InfluencersGroup.objects.get(id=data.get('group_id'))
    influencer = Influencer.objects.get(id=data.get('id'))

    mongo_utils.track_query("brand-delete-from-collection", {
        'collection_name': group.name,
        'blog_url': influencer.blog_url
    }, {"user_id": request.visitor["auth_user"].id})


    account_helpers.intercom_track_event(request, "brand-delete-from-collection", {
        'collection_name': group.name,
        'blog_url': influencer.blog_url
    })

    group.remove_influencer(influencer)

    return HttpResponse()


@login_required
def remove_candidate_from_campaign(request):
    """
    This should not be allowed
    """
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    mapping = get_object_or_404(InfluencerJobMapping, id=data.get('id'))
    job = mapping.job

    mongo_utils.track_query("brand-delete-from-campaign", {
        'campaign_name': job.title,
        'blog_url': mapping.influencer.blog_url
    }, {"user_id": request.visitor["auth_user"].id})


    account_helpers.intercom_track_event(request, "brand-delete-from-campaign", {
        'campaign_name': job.title,
        'blog_url': mapping.influencer.blog_url
    })

    mapping.status = InfluencerJobMapping.STATUS_REMOVED
    mapping.save()

    return HttpResponse()


@login_required
def edit_influencer_mapping(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    mapping = get_object_or_404(InfluencerGroupMapping, id=data.get('id'))
    mapping.status = data.get('status')
    mapping.save()

    return HttpResponse()


@login_required
def send_email_to_influencers(request):
    mongo_utils.track_visit(request)

    shelf_user = request.user.userprofile
    brand = request.visitor["base_brand"]
    if not brand:
        return redirect('/')
    if not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        return redirect('/')

    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    template = data.get("template", "")
    subject = data.get("subject", "")
    email = data.get("email", request.user.email)
    influencers = Influencer.objects.filter(id__in=data.get("influencer_ids", [])).only("name", "blogname", "email").values("name", "blogname", "email")

    template = template.replace("{{name}}", "*|NAME|*")
    template = template.replace("{{blogname}}", "*|BLOGNAME|*")
    subject = subject.replace("{{name}}", "*|NAME|*")
    subject = subject.replace("{{blogname}}", "*|BLOGNAME|*")

    to_list = []
    merge_list = []
    for influencer in influencers:
        email = influencer["email"].split(",")
        if email:
            email = email[0]
        else:
            continue
        to_list.append({"name": influencer["name"], "email": email})
        merge_data = {
            "rcpt": email,
            "vars": [
                {
                    "name": "name",
                    "content": influencer["name"]
                },
                {
                    "name": "blogname",
                    "content": influencer["blogname"]
                },
            ]
        }
        merge_list.append(merge_data)
    mailsnake = MailSnake(settings.MANDRILL_API_KEY, api='mandrill')
    try:
        mailsnake.messages.send(message={
            'html': template,
            'subject': subject,
            'from_email': email,
            'from_name': brand.name,
            'to': to_list,
            "merge_vars": merge_list
        })
        return HttpResponse()
    except Exception as e:
        print e
        return HttpResponse(status=500)


# backward compat

@login_required
@user_is_brand_user
def favorited_bloggers(request):
    """
    get all bloggers that the logged in brand is following (note: the only way a brand should get here is if they are
    subscribed)
    """
    mongo_utils.track_visit(request)

    brand = request.visitor["base_brand"]
    if not brand or not brand.is_subscribed or not brand.stripe_plan in constants.STRIPE_COLLECTION_PLANS:
        raise PermissionDenied()

    groups = request.visitor["brand"].influencer_groups.exclude(
        archived=True
    ).filter(
        creator_brand=brand,
        system_collection=False
    ).prefetch_related(
        'influencers_mapping__influencer__shelf_user__userprofile'
    ).order_by(
        'name'
    )

    for group in groups:
        group.imgs = []
        # for influencer in list(group.influencers.all())[:4]:
        for influencer in group.influencers[:4]:
            group.imgs.append(influencer.profile_pic)

    campaigns = request.visitor["brand"].job_posts.filter(oryg_creator=brand)

    context = {
        'search_page': True,
        'type': 'followed',
        'sub_page': 'favorited',
        'selected_tab': 'outreach',
        'shelf_user': request.user.userprofile,
        'groups': groups,
        'campaign_list': campaigns,
    }

    return render(request, 'pages/search/bloggers_favorited.html', context)


@brand_view
def get_message_events(request, brand, base_brand, message_id):
    message = get_object_or_404(MailProxyMessage, id=message_id)
    data = ConversationSerializer().get_events(message)
    data = json.dumps(data, cls=DjangoJSONEncoder)
    return HttpResponse(data, content_type="application/json")


@brand_view
def get_conversations(request, brand, base_brand, map_id, thread):
    from aggregate_if import Count, Max
    mailbox, mapping = None, None
    limit = 5

    if thread == "collection":
        mapping = get_object_or_404(
            InfluencerGroupMapping,
            id=map_id,
            group__owner_brand=brand,
            group__creator_brand=base_brand
        )
        mongo_utils.mark_thread_seen(
            request.visitor["auth_user"].id, mapping.mailbox.id)
    elif thread == "job":
        mapping = get_object_or_404(
            InfluencerJobMapping,
            id=map_id,
            job__creator=brand,
            job__oryg_creator=base_brand
        )
        mongo_utils.mark_thread_seen(
            request.visitor["auth_user"].id, mapping.mailbox.id)
    elif thread == "generic":
        mailbox = get_object_or_404(
            MailProxy,
            id=map_id,
            brand=base_brand
        )
        try:
            mapping = InfluencerJobMapping.objects.filter(mailbox=mailbox)[0]
        except:
            pass
        mongo_utils.mark_thread_seen(
            request.visitor["auth_user"].id, mailbox.id)

    try:
        mailbox = mailbox or mapping.get_or_create_mailbox()
    except MailProxy.DoesNotExist:
        data = {
            'data': [],
        }
    else:
        t = time.time()
        conversations = MailProxyMessage.objects.prefetch_related(
            'thread__brand__related_user_profiles__user_profile',
            'thread__influencer',
            'thread__mapping__group',
            'thread__candidate_mapping__job',
        ).filter(
            thread=mailbox,
            type=MailProxyMessage.TYPE_EMAIL
        ).order_by(
            '-ts',
        )

        conversations = MailProxyMessage.objects.filter(
            thread=mailbox,
            type=MailProxyMessage.TYPE_EMAIL
        ).order_by(
            '-ts',
        ).prefetch_related(
            'thread__brand__related_user_profiles__user_profile',
            'thread__influencer',
            'thread__mapping__group',
            'thread__candidate_mapping__job',
        )

        try:
            offset = int(request.GET.get('offset'))
        except:
            offset = None
        else:
            conversations = conversations[offset:offset + limit]

        aggregated_data = MailProxyMessage.objects.filter(
            thread=mailbox
        ).aggregate(
            opens_count=Count(
                'pk', only=(
                    Q(mandrill_id__regex=r'.(.)+') & (
                        Q(type=MailProxyMessage.TYPE_OPEN) |
                        Q(type=MailProxyMessage.TYPE_CLICK)
                    )
                )
            ),
            total_count=Count(
                'pk', only=(
                    # Q(mandrill_id__regex=r'.(.)+') &
                    Q(type=MailProxyMessage.TYPE_EMAIL)
                )
            ),
            last_message=Max(
                'ts', only=(
                    # Q(mandrill_id__regex=r'.(.)+') &
                    Q(type=MailProxyMessage.TYPE_EMAIL)
                )
            ),
            last_sent=Max(
                'ts', only=(
                    # Q(mandrill_id__regex=r'.(.)+') &
                    Q(type=MailProxyMessage.TYPE_EMAIL) &
                    Q(direction=MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER)
                )
            ),
            last_reply=Max(
                'ts', only=(
                    # Q(mandrill_id__regex=r'.(.)+') &
                    Q(type=MailProxyMessage.TYPE_EMAIL) &
                    Q(direction=MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND)
                )
            ),
        )

        data = {
            'mailboxId': mailbox.id,
            'data': ConversationSerializer(conversations, many=True).data,
            'mailboxData': {
                'id': mailbox.id,
                'messagesCount': aggregated_data['total_count'],
                'opensCount': aggregated_data['opens_count'],
                'lastMessage': common_date_format(
                    aggregated_data['last_message'], request.visitor),
                'lastSent': common_date_format(
                    aggregated_data['last_sent'], request.visitor),
                'lastReply': common_date_format(
                    aggregated_data['last_reply'], request.visitor),
                'recentDate': 'last_sent' if aggregated_data['last_sent'] == aggregated_data['last_message'] else 'last_reply',
                'subject': mailbox.subject,
            },
            'brandLogo': mapping.job.profile_img_url if mapping else None,
            'limit': limit,
        }

        print '* getting conversations list:', time.time() - t
        mailbox.has_been_read_by_brand = True
        mailbox.save()

    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type="application/json")
    # return HttpResponse("<body><pre>{}</pre></body>".format(data))

    # I'm not sure about the following peace of code, should we leave it or no?
    # What it does is extends mailbox of choosen mapping (job or collection)
    # with messages from another type of mapping this influencer has

    # if thread == "job" and mapping.mapping and mapping.mapping.group:
    #     conversations.extend(get_json(mapping.mapping, None))
    # if thread == "collection":
    #     for job in mapping.jobs.all():
    #         conversations.extend(get_json(job, None))

    # conversations.sort(key=lambda x: x.ts, reverse=True)


# deprecated functions

def apply_invitation_old(request, map_id):
    try:
        data = json.loads(request.body)
    except ValueError:
        return HttpResponseBadRequest()

    mapping = get_object_or_404(InfluencerGroupMapping, id=map_id, influencer=request.visitor["influencer"])

    job = mapping.group.job_post.all()[0]

    context = {
        'influencer': request.visitor["influencer"],
        'mapping': mapping,
        'job': job,
        'note': account_helpers.get_bleached_template(data.get('template')),
    }

    rendered_message = render_to_string('pages/job_posts/apply_email.html', context)

    mp = mapping.get_or_create_mailbox()
    mp.send_email_as_influencer(subject="Invitation accepted", body=rendered_message)

    mapping.status = InfluencerGroupMapping.STATUS_ACCEPTED
    mapping.save()

    return HttpResponse()


def invite_old(request, map_id):
    try:
        mapping = InfluencerGroupMapping.objects.get(id=map_id)
    except InfluencerGroupMapping.DoesNotExist:
        return redirect('/')
    active = mapping.status != InfluencerGroupMapping.STATUS_ACCEPTED
    influencer = mapping.influencer
    signed_up = False
    logged_in = False

    next_url = request.get_full_path() + "?next="+request.get_full_path()
    if influencer.shelf_user:
        signed_up = True
        if request.visitor["influencer"] == influencer:
            logged_in = True
            if active:
                mapping.status = InfluencerGroupMapping.STATUS_VISITED
                mapping.save()
        elif request.GET.get('next') != request.path:
            return redirect(next_url)


    job_post = mapping.group.job_post.all()[0]

    context = {
        'selected_tab': 'outreach',
        'sub_page': 'job_posts',
        'job_post': job_post,
        'mapping': mapping,
        'signed_up': signed_up,
        'logged_in': logged_in,
        'active': active,
        'extra_body_class': 'get_rid_of_margin',
        'filters': job_post.filter_json and json.loads(job_post.filter_json),
    }
    return render(request, 'pages/job_posts/invite.html', context)


class FixRedirectView(RedirectView):

    def get_redirect_url(self, group_id, origin_url):
        return 'http://' + origin_url


def contract_sending_view(request, contract_id, blogger_hash):
    from debra.models import Contract
    from debra.docusign import client, login_information
    from debra.constants import MAIN_DOMAIN

    contract = Contract.objects.get(id=contract_id)

    blogger = contract.influencerjobmapping.influencer

    if blogger_hash != blogger.date_created_hash:
        return redirect('debra.account_views.brand_home')

    context = {'signed': False}

    return_url = ''.join([
        MAIN_DOMAIN,
        reverse(
            'debra.job_posts_views.blogger_document_sign_complete',
            args=(contract.id, blogger_hash,)
        )
    ])
    signer = client.get_envelope_recipients(contract.envelope)['signers'][0]
    resp = client.post_sender_view(
        authenticationMethod='email',
        email='suhanovpavel@gmail.com',
        userId=login_information['loginAccounts'][0]['userId'],
        envelopeId='857c9baa-6500-401d-9592-f2e254235e11',
        userName='Pavel Sukhanov',
        returnUrl=return_url)
    context.update({
        'signed': False,
        'signing_url': resp['url'],
    })

    return render(
        request, 'pages/job_posts/blogger_document_sign.html', context)

def contract_signing_view(request, contract_id, blogger_hash):
    from debra.models import Contract
    from debra.docusign import client, ContractSender
    from debra.constants import MAIN_DOMAIN

    contract = Contract.objects.get(id=contract_id)

    blogger = contract.blogger

    if blogger_hash != blogger.date_created_hash:
        return redirect('debra.account_views.brand_home')

    context = {
        'contract': contract,
    }

    if not contract.envelope:
        contract_sender = ContractSender(contract)
        contract_sender.create_and_send_envelope()

    if contract.status in [Contract.STATUS_SIGNED, Contract.STATUS_DECLINED]:
        context['signed'] = True
    else:
        return_url = ''.join([
            MAIN_DOMAIN,
            reverse(
                'debra.job_posts_views.blogger_document_sign_complete',
                args=(contract.id, blogger_hash,)
            )
        ])
        signer = client.get_envelope_recipients(contract.envelope)['signers'][0]
        resp = client.post_recipient_view(
            clientUserId=signer['clientUserId'],
            envelopeId=contract.envelope,
            userId=signer['userId'],
            returnUrl=return_url)
        context.update({
            'signed': False,
            'signing_url': resp['url'],
        })

    return render(
        request, 'pages/job_posts/blogger_document_sign.html', context)


def blogger_document_sign_complete(request, contract_id, blogger_hash):
    from json2html import json2html
    from debra.models import Contract
    from debra.helpers import send_admin_email_via_mailsnake

    contract = Contract.objects.get(id=contract_id)
    blogger = contract.blogger

    if blogger_hash != blogger.date_created_hash:
        return redirect('debra.account_views.brand_home')

    try:
        data = dict(request.GET.iterlists())
        data_html = json2html.convert(json=data)
    except:
        data_html = ''

    send_admin_email_via_mailsnake(
        'BLOGGER_DOCUMENT_SIGN_COMPLETE',
        '{}'.format(data_html)
    )

    if request.GET.get('event') == 'signing_complete':
        contract.status = contract.STATUS_SIGNED
    elif request.GET.get('event') == 'decline':
        contract.status = contract.STATUS_DECLINED
    contract.save()

    return render(
        request, 'pages/job_posts/blogger_document_sign_complete.html', {
            'contract': contract,
            'event': request.GET.get('event'),
        })
    # return redirect(
    #     'debra.job_posts_views.blogger_tracking_page',
    #     args=(contract.id, contract.tracking_hash_key)
    # )


def blogger_shipment_received(request, contract_id, blogger_hash):
    from debra.models import Contract

    contract = Contract.objects.get(id=contract_id)
    blogger = contract.blogger

    if blogger_hash != blogger.date_created_hash:
        return redirect('debra.account_views.brand_home')

    contract.shipment_status = 2
    contract.shipment_received_date = datetime.now()
    contract.save()

    return render(
        request, 'pages/job_posts/shipment_complete.html', {
            'contract': contract,
        })


def edit_contract(request, contract_id):
    from debra.models import Contract

    if request.method == 'POST':
        data = json.loads(request.body)

        print '* fields updating: {}'.format(data.keys())

        contract = Contract.objects.get(id=contract_id)
        influencer_analytics = contract.influencerjobmapping.influencer_analytics
        if data.get('influencer_notes') and influencer_analytics:
            influencer_analytics.notes = data.get('influencer_notes')
            del data['influencer_notes']
        contract.__dict__.update(data)
        contract.save()

    return HttpResponse()


@login_required
def load_document_specific_fields(request, contract_id=None):
    from debra.models import Contract
    from debra.docusign import ContractSender

    if contract_id is None:
        contract_id = request.GET.get('contract_id')
    contract = get_object_or_404(Contract, id=contract_id)

    sender = ContractSender(contract)

    data = {
        'data': [{
            'id': doc_id,
            'name': doc_data.get('name', doc_id),
            'fields': [{
                "name": ' '.join([w.capitalize() for w in k.split('_')]),
                "value": v,
                "key": k,
            } for k, v in sender.document_specific_tabs.get(doc_id, {}).items()]
        } for doc_id, doc_data in contract.docusign_documents.items()]
    }

    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


def send_contract(request, contract_id):
    from debra.models import Contract
    from debra.docusign import ContractSender

    contract = get_object_or_404(Contract, id=contract_id)

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except:
            body = {}
        blogger = contract.blogger
        campaign = contract.campaign
        brand = contract.brand
        mailbox = contract.influencerjobmapping.mailbox

        sender = request.visitor['auth_user']

        data = {
            'subject': "Re: {}".format(mailbox.subject),
            'attachments': [],
        }

        if body.get('template'):
            data['template'] = body.get('template').get('body')
            if not mailbox.subject:
                data['subject'] = body.get('template').get('subject')
        else:
            collect_details_template = contract.campaign.info_json.get(
                'collect_details_template', {})
            if collect_details_template.get('template'):
                if not mailbox.subject:
                    data['subject'] = collect_details_template.get('subject')
                data['template'] = Template(
                    collect_details_template.get('template')
                ).render(Context({
                    'user': {
                        'first_name': contract.blogger.first_name,
                        'collect_info_link': mark_safe(
                            '<a href="{link}">{link}</a>'.format(
                                link=contract.blogger_tracking_url + "#/5")
                        ),
                        'contract_sign_link': mark_safe(
                            '<a href="{link}">{link}</a>'.format(
                                link=contract.link
                            )
                        )
                    }
                }))

        contract.status = contract.STATUS_NON_SENT
        contract.save()

        if not contract.envelope:
            contract_sender = ContractSender(contract)
            contract_sender.create_and_send_envelope()

        resp = render_and_send_message(
            mp=mailbox,
            brand=brand,
            influencer=blogger,
            sender=sender,
            template_name='pages/job_posts/contract_invitation_email.html',
            data=data,
            user=request.visitor['auth_user'],
            job_mapping=contract.influencerjobmapping,
        )

        contract.status = contract.STATUS_SENT
        contract.save()

    data = {
        'data': {
            'status': {
                'value': contract.status,
                'name': contract.status_name,
                'color': contract.status_color,
            }
        }
    }
    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


def get_email_template_context(request, contract_id):
    from debra.models import Contract
    from debra.serializers import CampaignSerializer
    contract = Contract.objects.get(id=contract_id)
    data = {
        'user': {
            'first_name': contract.blogger.first_name,
            'shipment_tracking_code': contract.shipment_tracking_code,
            'shipment_received_url': contract.blogger_shipment_received_url,
            'blogger_page': contract.blogger_tracking_url,
            'blogger_page_tracking_section': '{}#/14'.format(
                contract.blogger_tracking_url),
            'blogger_page_post_approval_section': '{}#/17'.format(
                contract.blogger_tracking_url),
            'blogger_page_posts_section': '{}#/16'.format(
                contract.blogger_tracking_url),
            'collect_info_link': mark_safe(
                '<a href="{link}">{link}</a>'.format(
                    link=contract.blogger_tracking_url)
            ),
            'contract_signing_page': contract.link,
        },
        'campaign_overview_link': CampaignSerializer().get_overview_page_link(
            contract.campaign),
        'data': {
            'subject': "Re: {}".format(
                contract.mailbox.subject) if contract.mailbox else None,
        }

    }
    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')    


def send_tracking_code(request, contract_id):
    from debra.models import Contract

    contract = get_object_or_404(Contract, id=contract_id)

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except:
            body = {}

        contract.tracking_status = contract.TRACKING_STATUS_NON_SENT
        contract.save()

        if contract.tracking_status == contract.TRACKING_STATUS_NON_SENT:
            print '* sending tracking code'
            data = {
                # 'subject': u"Tracking Settings for '{}' campaign".format(
                #     contract.campaign.title),
                'subject': "Re: {}".format(contract.mailbox.subject),
                'attachments': [],
            }

            if body.get('template'):
                data['template'] = body.get('template').get('body')
                if not contract.mailbox.subject:
                    data['subject'] = body.get('template').get('subject')
            else:
                reminder_template = contract.campaign.info_json.get(
                    'reminder_template', {})
                if reminder_template.get('template'):
                    if not contract.mailbox.subject:
                        data['subject'] = reminder_template.get('subject')
                    data['template'] = Template(
                        reminder_template.get('template')
                    ).render(Context({
                        'user': {
                            'first_name': contract.blogger.first_name,
                            'collect_info_link': mark_safe(
                                '<a href="{link}">{link}</a>'.format(
                                    link=contract.blogger_tracking_url + "#/5")
                            ),
                            'contract_sign_link': mark_safe(
                                '<a href="{link}">{link}</a>'.format(
                                    link=contract.link
                                )
                            )
                        }
                    }))

            if not contract.is_tracking_info_generated:
                contract.generate_tracking_info()

            resp = render_and_send_message(
                mp=contract.mailbox,
                brand=contract.brand,
                influencer=contract.blogger,
                contract=contract,
                sender=request.visitor['auth_user'],
                template_name='pages/job_posts/tracking_code_email.html',
                data=data,
                user=request.visitor['auth_user'],
            )

            contract.tracking_status = contract.TRACKING_STATUS_SENT
            contract.save()

    data = {
        'data': {
            'status': {
                'value': contract.tracking_status,
                'name': contract.tracking_status_name,
                'color': contract.tracking_status_color,
            }
        }
    }
    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


def send_collect_data_link(request, contract_id):
    from debra.models import Contract
    from debra.docusign import ContractSender

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except:
            body = {}
        contract = get_object_or_404(Contract, id=contract_id)

        contract.details_collected_status = 0
        contract.save()

        data = {
            # 'subject': u"Please provide us with details",
            'attachments': [],
        }
        subject = "Re: {}".format(contract.mailbox.subject)
        data['subject'] = subject

        if not contract.is_tracking_info_generated:
            contract.generate_tracking_info()

        if body.get('template'):
            data['template'] = body.get('template').get('body')
            if not contract.mailbox.subject:
                data['subject'] = body.get('template').get('subject')
        else:
            stage_settings = contract.campaign.info_json.get(
                'stage_settings', {}).get(
                    str(InfluencerJobMapping.CAMPAIGN_STAGE_FINALIZING_DETAILS), {})

            if stage_settings.get('use_standard_template'):
                # data['bleach'] = False
                if not contract.mailbox.subject:
                    data['subject'] = contract.default_subject
                data['template'] = Template(
                    contract.campaign.outreach_template_json.get('template', '')
                ).render(Context({
                    'user': {
                        'first_name': contract.blogger.first_name,
                        'collect_info_link': mark_safe(
                            '<a href="{link}">{link}</a>'.format(
                                link=contract.blogger_tracking_url + "#/5")
                        ),
                        'contract_sign_link': mark_safe(
                            '<a href="{link}">{link}</a>'.format(
                                link=contract.link
                            )
                        )
                    }
                }))
            if stage_settings.get('send_contract'):
                contract_sender = ContractSender(contract)
                contract_sender.create_and_send_envelope()

            collect_details_template = contract.campaign.info_json.get(
                'collect_details_template', {})
            if collect_details_template.get('template'):
                data['subject'] = collect_details_template.get('subject')
                data['template'] = Template(
                    collect_details_template.get('template')
                ).render(Context({
                    'user': {
                        'first_name': contract.blogger.first_name,
                        'collect_info_link': mark_safe(
                            '<a href="{link}">{link}</a>'.format(
                                link=contract.blogger_tracking_url + "#/5")
                        ),
                        'contract_sign_link': mark_safe(
                            '<a href="{link}">{link}</a>'.format(
                                link=contract.link
                            )
                        )
                    }
                }))

        resp = render_and_send_message(
            mp=contract.mailbox,
            brand=contract.brand,
            influencer=contract.blogger,
            contract=contract,
            sender=request.visitor['auth_user'],
            template_name='pages/job_posts/collect_data_email.txt',
            data=data,
            user=request.visitor['auth_user'],
        )

        contract.details_collected_status = 1
        contract.save()

    data = {
        'data': {
            'status': {
                'value': contract.details_collected_status,
                'name': contract.details_collected_status_name,
                'color': contract.details_collected_status_color,
            }
        }
    }
    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


def send_followup_message(request, contract_id):
    from debra.models import Contract

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except:
            body = {}
        contract = get_object_or_404(Contract, id=contract_id)

        contract.followup_status = 0
        contract.save()

        data = {
            'attachments': [],
        }
        subject = "Re: {}".format(contract.mailbox.subject)
        data['subject'] = subject

        if body.get('template'):
            data['template'] = body.get('template').get('body')
            if not contract.mailbox.subject:
                data['subject'] = body.get('template').get('subject')

        resp = render_and_send_message(
            mp=contract.mailbox,
            brand=contract.brand,
            influencer=contract.blogger,
            contract=contract,
            sender=request.visitor['auth_user'],
            template_name='pages/job_posts/followup_email.html',
            data=data,
            user=request.visitor['auth_user'],
        )

        contract.followup_status = 1
        contract.save()

    data = {
        'data': {
            'status': {
                'value': contract.followup_status,
                'name': contract.followup_status_name,
                'color': contract.followup_status_color,
            }
        }
    }
    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


def send_posts_adding_notification(request, contract_id):
    from debra.models import Contract

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except:
            body = {}
        contract = get_object_or_404(Contract, id=contract_id)

        contract.posts_adding_status = 0
        contract.save()

        data = {
            'attachments': [],
        }
        subject = "Re: {}".format(contract.mailbox.subject)
        data['subject'] = subject

        if body.get('template'):
            data['template'] = body.get('template').get('body')
            if not contract.mailbox.subject:
                data['subject'] = body.get('template').get('subject')

        resp = render_and_send_message(
            mp=contract.mailbox,
            brand=contract.brand,
            influencer=contract.blogger,
            contract=contract,
            sender=request.visitor['auth_user'],
            template_name='pages/job_posts/followup_email.html',
            data=data,
            user=request.visitor['auth_user'],
        )

        contract.posts_adding_status = 1
        contract.save()

    data = {
        'data': {
            'status': {
                'value': contract.posts_adding_status,
                'name': contract.posts_adding_status_name,
                'color': contract.posts_adding_status_color,
            }
        }
    }
    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


def send_shipment_notification(request, contract_id):
    from debra.models import Contract

    if request.method == 'POST':
        try:
            body = json.loads(request.body)
        except:
            body = {}
        contract = get_object_or_404(Contract, id=contract_id)

        contract.shipment_status = 1
        if contract.ship_date is None:
            contract.ship_date = datetime.now().date()
        contract.save()

        data = {
            # 'subject': u"Please provide us with details",
            'subject': "Re: {}".format(contract.mailbox.subject),
            'attachments': [],
        }

        if body.get('template'):
            data['template'] = body.get('template').get('body')
            if not contract.mailbox.subject:
                data['subject'] = body.get('template').get('subject')
        else:
            shipping_template = contract.campaign.info_json.get(
                'shipping_template', {})
            if shipping_template.get('template'):
                if not contract.mailbox.subject:
                    data['subject'] = shipping_template.get('subject')
                data['template'] = Template(
                    shipping_template.get('template')
                ).render(Context({
                    'user': {
                        'first_name': contract.blogger.first_name,
                        'collect_info_link': mark_safe(
                            '<a href="{link}">{link}</a>'.format(
                                link=contract.blogger_tracking_url + "#/5")
                        ),
                        'contract_sign_link': mark_safe(
                            '<a href="{link}">{link}</a>'.format(
                                link=contract.link
                            )
                        ),
                        'shipment_received_url': contract.blogger_shipment_received_url,
                        'shipment_tracking_code': contract.shipment_tracking_code,
                    }
                }))

        if not contract.is_tracking_info_generated:
            contract.generate_tracking_info()

        resp = render_and_send_message(
            mp=contract.mailbox,
            brand=contract.brand,
            influencer=contract.blogger,
            contract=contract,
            sender=request.visitor['auth_user'],
            template_name='pages/job_posts/shipment_notification.html',
            data=data,
            user=request.visitor['auth_user'],
        )

    data = {
        'data': {
            'status': {
                'value': contract.shipment_status,
                'name': contract.shipment_status_name,
                'color': contract.shipment_status_color,
            }
        }
    }
    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


def mark_payment_complete(request, contract_id):
    from debra.models import Contract

    if request.method == 'POST':
        contract = get_object_or_404(Contract, id=contract_id)

        contract.payment_complete = not contract.payment_complete
        contract.save()

    data = {
        'data': {
            'status': {
                'value': contract.payment_complete,
                'name': '',
                'color': '',
            }
        }
    }

    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


def send_add_post_link(request, contract_id):
    from debra.models import Contract

    if request.method == 'POST':
        contract = get_object_or_404(Contract, id=contract_id)

        contract.posts_adding_status = contract.POSTS_ADDING_STATUS_NON_SENT
        contract.save()

        if contract.posts_adding_status not in [contract.POSTS_ADDING_STATUS_DONE]:
            data = {
                # 'subject': u"Add Your Posts for '{}' campaign".format(
                #     contract.campaign.title),
                'subject': "Re: {}".format(contract.mailbox.subject),
                'attachments': [],
            }

            if not contract.is_tracking_info_generated:
                contract.generate_tracking_info()

            resp = render_and_send_message(
                mp=contract.mailbox,
                brand=contract.brand,
                influencer=contract.blogger,
                contract=contract,
                sender=request.visitor['auth_user'],
                template_name='pages/job_posts/add_posts_email.html',
                data=data,
                user=request.visitor['auth_user'],
            )

            contract.posts_adding_status = contract.POSTS_ADDING_STATUS_SENT
            contract.save()

    data = {
        'data': {
            'status': {
                'value': contract.posts_adding_status,
                'name': contract.posts_adding_status_name,
                'color': contract.posts_adding_status_color,
            }
        }
    }
    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


def send_paypal_info_request(request, contract_id):
    from debra.models import Contract

    if request.method == 'POST':
        contract = get_object_or_404(Contract, id=contract_id)

        contract.posts_adding_status = contract.PAYPAL_INFO_STATUS_NON_SENT
        contract.save()

        data = {
            # 'subject': u"Enter Paypal Information",
            'subject': "Re: {}".format(contract.mailbox.subject),
            'attachments': [],
        }

        resp = render_and_send_message(
            mp=contract.mailbox,
            brand=contract.brand,
            influencer=contract.blogger,
            contract=contract,
            sender=request.visitor['auth_user'],
            template_name='pages/job_posts/paypal_info_email.html',
            data=data,
            user=request.visitor['auth_user'],
        )

        contract.paypal_info_status = contract.PAYPAL_INFO_STATUS_SENT
        contract.save()

    data = {
        'data': {
            'status': {
                'value': contract.paypal_info_status,
                'name': contract.paypal_info_status_name,
                'color': contract.paypal_info_status_color,
            }
        }
    }

    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


def blogger_tracking_page(request, contract_id, hash_key):
    from debra.models import Contract

    contract = get_object_or_404(Contract, id=contract_id)

    if not contract.is_tracking_info_generated:
        contract.generate_tracking_info()
    contract.generate_google_doc()

    if contract.tracking_hash_key != hash_key:
        raise Http404()

    if request.method == 'POST':
        data = json.loads(request.body)
    else:
        campaign_checklist = []
        print contract.campaign.info_json
        if contract.campaign.info_json.get('signing_contract_on') or contract.campaign.info_json.get('payment_details_on'):
            campaign_checklist.append(12)
        if contract.campaign.info_json.get('sending_product_on'):
            campaign_checklist.append(13)
        if contract.campaign.info_json.get('tracking_codes_on'):
            campaign_checklist.append(14)
        if contract.campaign.creator.flag_post_approval_enabled:
            campaign_checklist.append(17)
        print 'Checklist:', campaign_checklist
        context = {
            'contract': contract,
            'campaign': contract.campaign,
            'campaign_checklist': campaign_checklist,
            'initial_form_preview': request.GET.get('initial_form_preview'),
            'should_display_payment': contract.campaign.info_json.get(
                'payment_details_on') and (
                    contract.status == contract.STATUS_SIGNED
                    if contract.campaign.info_json.get('signing_contract_on')
                    else True),
            'rand': random.random(),
        }

        return render(request, 'pages/landing/blogger_tracking_page.html', context)


def campaign_overview_page(request, campaign_id):
    from debra.models import BrandJobPost
    campaign = get_object_or_404(BrandJobPost, id=campaign_id)
    context = {
        'campaign': campaign,
    }
    return render(request, 'pages/landing/blogger_tracking_page.html', context)


def blogger_tracking_link(request, contract_id, hash_key):
    from debra.models import Contract

    contract = get_object_or_404(Contract, id=contract_id)

    if contract.tracking_hash_key != hash_key:
        raise Http404()

    context = {
        'contract': contract,
    }

    if contract.tracking_status == contract.TRACKING_STATUS_NON_SENT:
        raise Http404()

    return render(request, 'pages/landing/blogger_tracking_link.html', context)


def blogger_tracking_link_complete(request, contract_id, hash_key):
    from debra.models import Contract
    from debra.account_helpers import influencer_tracking_verification

    contract = get_object_or_404(Contract, id=contract_id)

    if contract.tracking_hash_key != hash_key:
        raise Http404()

    context = {
        'contract': contract,
    }

    if contract.tracking_status == contract.TRACKING_STATUS_NON_SENT:
        raise Http404()
    elif contract.tracking_status in [contract.TRACKING_STATUS_VERIFICATION_PROBLEM, contract.TRACKING_STATUS_SENT]:
        # influencer_tracking_verification(contract.id, 2, 10)
        influencer_tracking_verification.apply_async(
            [contract.id], queue="influencer_tracking_verification")
        contract.tracking_status = contract.TRACKING_STATUS_VERIFYING
        contract.save()

    if request.is_ajax() and request.method == 'POST':
        return HttpResponse()
    else:
        return render(
            request, 'pages/landing/blogger_tracking_link.html', context)


def download_contract_document(request, contract_id):
    from debra.docusign import client
    from debra.models import Contract

    contract = Contract.objects.get(id=contract_id)

    file_name = 'theshelf_contract_signed_{}_{}.pdf'.format(
        contract_id, format_filename(contract.blogger.blog_url or 'None'))

    output = pyPdf.PdfFileWriter()

    docs = client.get_envelope_document_list(contract.envelope)[:-1]
    for doc_data in docs:
        raw = client.get_envelope_document(
            envelopeId=contract.envelope, documentId=doc_data['documentId'])
        input_pdf = pyPdf.PdfFileReader(StringIO(raw.data))
        for page_num in xrange(input_pdf.getNumPages()):
            output.addPage(input_pdf.getPage(page_num))

    merged_pdf = StringIO()
    output.write(merged_pdf)

    resp = HttpResponse(content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename="%s"' % (file_name,)
    resp.write(merged_pdf.getvalue())

    merged_pdf.close()

    return resp


def download_contract_document_preview(request, contract_id):
    from debra.docusign import ContractSender
    from debra.models import Contract

    contract = Contract.objects.get(id=contract_id)
    file_name = 'theshelf_contract_{}_{}_preview.pdf'.format(
        contract_id, format_filename(contract.blogger.blog_url or 'None'))

    output = pyPdf.PdfFileWriter()

    sender = ContractSender(contract)

    for document in sender.documents:
        input_pdf = pyPdf.PdfFileReader(document.output_buffer)
        for page_num in xrange(input_pdf.getNumPages()):
            output.addPage(input_pdf.getPage(page_num))

    merged_pdf = StringIO()
    output.write(merged_pdf)

    resp = HttpResponse(content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename="%s"' % (file_name,)
    resp.write(merged_pdf.getvalue())

    merged_pdf.close()

    return resp


def download_campaign_contract_document_preview(request, campaign_id):
    from debra.docusign import ContractSender
    from debra.models import BrandJobPost

    campaign = BrandJobPost.objects.get(id=campaign_id)
    file_name = 'theshelf_contract_{}_{}_preview.pdf'.format(
        campaign_id, format_filename(campaign.title or 'Test Campaign'))

    output = pyPdf.PdfFileWriter()

    sender = ContractSender(campaign)

    for document in sender.documents:
        input_pdf = pyPdf.PdfFileReader(document.output_buffer)
        for page_num in xrange(input_pdf.getNumPages()):
            output.addPage(input_pdf.getPage(page_num))

    merged_pdf = StringIO()
    output.write(merged_pdf)

    resp = HttpResponse(content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename="%s"' % (file_name,)
    resp.write(merged_pdf.getvalue())

    merged_pdf.close()

    return resp


def test_document(request, contract_id):
    from debra.models import Contract

    contract = Contract.objects.get(id=contract_id)

    file_name = "test_document.pdf"

    pdf_file = open(constants.DOCUSIGN_TEST_DOCUMENT_PATH, 'rb')

    resp = HttpResponse(content_type='application/pdf')
    resp['Content-Disposition'] = 'attachment; filename="%s"' % (file_name,)

    labels, page_offsets = get_default_labels(contract)

    test_document = put_text_fields(pdf_file, labels, page_offsets)
    resp.write(test_document.getvalue())

    test_document.close()

    return resp


@csrf_exempt
def docusign_callback(request):
    from pydocusign.parser import DocuSignCallbackParser
    from debra.models import Contract
    from debra.helpers import send_admin_email_via_mailsnake

    parser = DocuSignCallbackParser(xml_source=request.body)

    try:
        for contract_id, data in parser.recipients.items():
            contract = Contract.objects.get(id=contract_id)
            if data.get('Status') == 'Sent':
                contract.status = Contract.STATUS_SENT
            elif data.get('Status') == 'Delivered':
                contract.status = Contract.STATUS_DELIVERED
            elif data.get('Status') == 'Signed':
                contract.status = Contract.STATUS_SIGNED
            elif data.get('Status') == 'Completed':
                contract.status = Contract.STATUS_SIGNED
            elif data.get('Status') == 'Declined':
                contract.status = Contract.STATUS_DECLINED
            elif data.get('Status') == 'Voided':
                contract.status = Contract.STATUS_VOIDED
            contract.save()
    except:
        send_admin_email_via_mailsnake(
            'DocuSign Callback Exception', traceback.format_exc())

    return HttpResponse()


def update_model(request, model_id=None):
    from debra.helpers import update_model

    if request.method == 'POST':
        data = json.loads(request.body)
        if data.get('list'):
            data_list = data.get('list')
        else:
            data_list = [data]
        for data in data_list:
            data['id'] = model_id or data.get('id')
            print data
            update_model(data)

    return HttpResponse()


@login_required
def get_post_analytics_collection_stats(request, collection_id):
    from debra.models import PostAnalyticsCollection

    collection = get_object_or_404(PostAnalyticsCollection, id=collection_id)

    data = {
        'data': {
            'clicks': collection.clicks_stats,
            'views': collection.views_stats,
        }
    }

    data = json.dumps(data, cls=DjangoJSONEncoder, indent=4)
    return HttpResponse(data, content_type='application/json')


@login_required
def set_messages_visible_columns(request):
    if request.method == 'POST':
        up = request.visitor["user"]
        if up:
            data = json.loads(request.body)
            up.flag_messages_columns_visible = data['columns']
            up.save()
    return HttpResponse()


def campaign_report(request, campaign_id, section=None, hash_key=None):
    from debra.serializers import CampaignReportTableSerializer
    from debra import search_helpers, feeds_helpers
    from debra.models import Platform, MailProxy
    from debra.mail_proxy import mailsnake_send
    from debra.serializers import InfluencerSerializer

    campaign = get_object_or_404(BrandJobPost, id=campaign_id)

    if hash_key is None:
        if not request.user.is_authenticated():
            raise Http404()
    elif campaign.report_hash_key != hash_key:
        raise Http404()

    sections = OrderedDict([
        ('campaign_overview', {'text': 'Campaign Overview'}),
        # ('influencer_stats', {'text': 'Influencer Stats'}),
        ('post_stats', {'text': 'Post Stats'}),
        ('user_generated_content', {'text': 'All User-generated Content'}),
    ])

    section = section or 'campaign_overview'
    try:
        sections[section]['selected'] = True
    except KeyError:
        raise Http404()

    post_type = request.GET.get('post_type')

    # qs = campaign.post_collection.get_unique_post_analytics().exclude(
    #     post__platform__isnull=True
    # ).exclude(
    #     post__platform__platform_name='Instagram',
    #     post__post_image__isnull=True
    # )

    campaign.get_or_create_post_collection()

    if request.method == 'POST':
        if request.GET.get('send_invitation_to_public_report'):
            data = json.loads(request.body)
            mandrill_message = {
                'html': data.get('body'),
                'subject': data.get('subject'),
                # 'from_email': request.user.email,
                'from_email': '{}_b_{}_id_{}@reply.theshelf.com'.format(
                    request.user.email.split('@')[0],
                    request.visitor['base_brand'].id,
                    request.user.id),
                'from_name': request.visitor["user"].name,
                'to': data.get('toList', [{
                    'email': data.get('toEmail'),
                    'name': data.get('toName')
                }]),
            }
            print mandrill_message
            mail_proxy.mailsnake_send(mandrill_message)
            return HttpResponse()
    
    qs = campaign.participating_post_analytics.exclude(
        post__platform__platform_name='Instagram',
        post__post_image__isnull=True
    )

    post_type_counts = dict(
        (d['post__platform__platform_name'], d['post__platform__platform_name__count'])
        for d in qs.values('post__platform__platform_name').annotate(Count('post__platform__platform_name'))
    )

    for pl in Platform.BLOG_PLATFORMS:
        post_type_counts['Blog'] = post_type_counts.get('Blog', 0) + post_type_counts.get(pl, 0)
        try:
            del post_type_counts[pl]
        except KeyError:
            pass

    influencers_count = qs.values(
        'post__influencer'
    ).filter(
        post__influencer__isnull=False).distinct('post__influencer').count()

    if post_type:
        qs = qs.filter(
            # Q(post_type=post_type) | Q(post__platform__platform_name=post_type)
            Q(post__platform__platform_name__in=Platform.BLOG_PLATFORMS if post_type == 'Blog' else [post_type])
        )

    print post_type_counts

    post_types = [
        {'value': None, 'text': 'All', 'count': sum(post_type_counts.values()), 'class': None},
        {'value': 'Blog', 'text': 'Blog Posts', 'color': 'black', 'class': 'social_globe3',},
        {'value': 'Youtube', 'text': 'Youtube', 'color': '#df0404', 'class': 'social_youtube',},
        {'value': 'Instagram', 'text': 'Instagrams', 'color': '#d0bf01', 'class': 'social_instagram2',},
        {'value': 'Pinterest', 'text': 'Pins', 'color': '#c92320', 'class': 'social_pinterest',},
        {'value': 'Facebook', 'text': 'Facebooks', 'color': '#2d58a4', 'class': 'social_facebook',},
        {'value': 'Twitter', 'text': 'Tweets', 'color': '#00adf2', 'class': 'social_twitter',},
    ]

    for p in post_types:
        p['count'] = p.get('count', post_type_counts.get(p['value'], 0))
        if p['value'] == post_type:
            p['selected'] = True

    context = {}

    if section == 'user_generated_content':
        if request.is_ajax() or request.GET.get('ajax_mode'):
            if post_type:
                qs = qs.filter(
                    post__platform__platform_name__in=Platform.BLOG_PLATFORMS if post_type == 'Blog' else [post_type])
            post_ids = list(qs.values_list('post', flat=True))
            print '* Post IDs:', post_ids
            # if post_type:
            feed_json = feeds_helpers.get_feed_handler_for_platform(post_type)
            # else:
            #     feed_json = feeds_helpers.all_feed_json
            platform_preference = None if post_type else ['Instagram']
            data = feed_json(
                request,
                no_cache=True,
                with_post_ids=post_ids,
                platform_preference=platform_preference,
                limit_size=20)
            print '* Total:', data['total']
            data = json.dumps(data, cls=DjangoJSONEncoder)
            return HttpResponse(data, content_type="application/json")
        else:
            context.update({
                'filter_key': feeds_helpers.platform_name_2_filter_key(
                    post_type if post_type else 'All'),
            })
    elif section == 'post_stats':
        qs = qs.prefetch_related(
            'post__influencer__platform_set',
            'post__influencer__shelf_user__userprofile',
            'post__platform',
        )
        qs = qs.with_campaign_counters(
            platform_preference=None if post_type else ['Instagram'])

        hidden_fields = []
        if post_type == 'Instagram':
            hidden_fields.append('post_shares')
        elif post_type == 'Blog':
            hidden_fields.append('post_likes')
            hidden_fields.append('post_shares')
            hidden_fields.append('impressions')
        if post_type not in ['Blog']:
            hidden_fields.extend([
                'count_impressions',
                'count_clickthroughs',
                'count_fb_shares',
                'count_tweets',
                'count_gplus_plusone',
                'count_pins',
            ])

        context.update(
            search_helpers.generic_reporting_table_context(
                request,
                queryset=qs,
                serializer_class=CampaignReportTableSerializer,
                include_total=False,
                default_order_params=None if post_type else [('platform_order', 0)],
                annotation_fields={
                    'post_shares': 'agr_post_shares_count',
                    'post_num_comments': 'agr_post_comments_count',
                    'post_total': 'agr_post_total_count',
                    'count_fb_shares': 'agr_fb_count',
                },
                hidden_fields=hidden_fields,
            )
        )
    elif section == 'campaign_overview':
        if request.is_ajax() or request.GET.get('ajax_mode'):
            if request.GET.get('influencer_locations'):
                locs = set(qs.exclude(
                    post__influencer__isnull=True
                ).values_list(
                    'post__influencer__demographics_location_lat',
                    'post__influencer__demographics_location_lon',
                    'post__influencer__name',
                    'post__influencer__blogname',
                    'post__influencer__demographics_location_normalized',
                    'post__influencer__demographics_locality__city',
                    'post__influencer__demographics_locality__state',
                    'post__influencer__demographics_locality__country',
                ).distinct('post__influencer'))
                locs_dict = defaultdict(dict)
                for lat, lon, name, blogname, loc, city, state, country in locs:
                    if lat is None or lon is None:
                        continue
                    place = locs_dict[(lat, lon)]
                    place['influencers'] = place.get('influencers', [])
                    locs_dict[(lat, lon)]['influencers'].append({
                        'name': name,
                        'blogname': blogname,
                    })
                    place['location'] = {
                        'loc': loc,
                        'city': city,
                        'state': constants.get_state_abbreviation(state),
                        'country': country,
                    }
                    place['latitude'] = lat
                    place['longitude'] = lon
                state_stats = defaultdict(int)
                for loc in locs_dict.values():
                    state_stats[loc['location'].get('state', '')] += len(
                        loc.get('influencers', []))
                data = {
                    'settings': {
                        'type': 'world' if campaign.id in [815, 872] else 'usa',
                        'projection': campaign.id in [815, 872],
                        'scale': 350,
                        'center': {
                            # 'lat': sum(x['latitude'] for x in locs_dict.values()) / float(len(locs_dict)),\
                            # 'long': sum(x['longitude'] for x in locs_dict.values()) / float(len(locs_dict)),
                            'lat': 45,
                            'long': 47,
                        },
                    },
                    'bubbles': locs_dict.values(),
                    'state_stats': {
                        'lowest': min(state_stats.values() or [0]),
                        'highest': max(state_stats.values() or [0]),
                        'stats': state_stats,
                    }
                    # 'heatmap': heatmap,
                }
            elif request.GET.get('post_stats'):
                from aggregate_if import Sum

                qs = qs.with_campaign_counters().values(
                    'post__platform__platform_name',
                    'agr_post_total_count',
                    'agr_post_shares_count',
                    'agr_post_comments_count',
                    'post__engagement_media_numlikes',
                    'post__impressions',
                    'count_tweets',
                    'count_fb_likes',
                    'count_fb_shares',
                    'count_fb_comments',
                    'count_gplus_plusone',
                    'count_pins',
                    # 'count_clickthroughs',
                    # 'count_impressions',
                )
                counts = OrderedDefaultdict(
                    lambda: OrderedDefaultdict(lambda: OrderedDefaultdict(int)))
                post_counts = defaultdict(int)

                _t0 = time.time()

                try:
                    latest_collection_stats = campaign.post_collection.time_series.order_by('-snapshot_date')[0]
                except IndexError:
                    pass
                else:
                    counts['Blog']['clicks'] = {
                        'count': latest_collection_stats.count_clicks,
                        'title': 'Clicks'
                    }
                    counts['Blog']['views'] = {
                        'count': latest_collection_stats.count_views,
                        'title': 'Views',
                    }

                print 'latest_collection_stats: {}'.format(time.time() - _t0)

                _t0 = time.time()

                for val in qs:
                    pl = val['post__platform__platform_name']
                    if pl in Platform.BLOG_PLATFORMS:
                        pl = 'Blog'
                    counts[pl]['comments']['count'] += val['agr_post_comments_count'] or 0; counts[pl]['comments']['title'] = pl + ' Comments' if pl in ['Blog'] else 'Comments'
                    if pl in ['Blog']:
                        counts[pl]['tweets']['count'] += val['count_tweets'] or 0; counts[pl]['tweets']['title'] = 'Twitter Virality';
                        counts[pl]['facebook']['count'] += (val['count_fb_likes'] or 0) + (val['count_fb_shares'] or 0) + (val['count_fb_comments'] or 0); counts[pl]['facebook']['title'] = 'Facebook Virality';
                        counts[pl]['gplus']['count'] += val['count_gplus_plusone'] or 0; counts[pl]['gplus']['title'] = 'Google+ Virality'
                        counts[pl]['pins']['count'] += val['count_pins'] or 0; counts[pl]['pins']['title'] = 'Pinterest Virality'
                    if pl not in ['Instagram', 'Blog']:
                        counts[pl]['shares']['count'] += val['agr_post_shares_count'] or 0; counts[pl]['shares']['title'] = 'Shares'
                    if pl not in ['Blog']:
                        counts[pl]['likes']['count'] += val['post__engagement_media_numlikes'] or 0; counts[pl]['likes']['title'] = 'Likes'
                    if pl in ['Instagram', 'Facebook']:
                        counts[pl]['impressions']['count'] += val['post__impressions'] or 0; counts[pl]['impressions']['title'] = 'Views (for Videos)'
                    counts[pl]['total']['count'] += val['agr_post_total_count'] or 0; counts[pl]['total']['title'] = 'Total'
                    for n, item in enumerate(counts[pl].values(), start=1):
                        item['order'] = n
                    post_counts[pl] += 1

                print 'counts: {}'.format(time.time() - _t0)

                _t0 = time.time()

                generic_counts = {}
                # generic_counts['Post Impressions'] = {
                #     'total_blog_impressions': {
                #         'title': 'Total Blog Impressions',
                #         'count': campaign.get_total_impressions(blog_only=True),
                #         'order': 1,
                #     },
                #     'total_potential_social_impressions': {
                #         'title': 'Total Potential Social Impressions',
                #         'count': campaign.get_total_impressions(social_only=True),
                #         'order': 2,
                #     },
                #     'total_potential_unique_social_impressions': {
                #         'title': 'Total Potential Unique Social Impressions',
                #         'count': campaign.get_unique_impressions(social_only=True),
                #         'order': 3,
                #     },
                #     'all_impressions': {
                #         'title': 'All Impressions',
                #         'count': campaign.get_total_impressions(),
                #         'order': 4,
                #     },
                # }

                print 'generic_counts: {}'.format(time.time() - _t0)

                data = OrderedDict([
                    ('post_counts', post_counts),
                    ('counts', counts),
                    ('generic_counts', generic_counts),
                ])
            elif request.GET.get('top_influencers'):
                qs = qs.with_campaign_counters().order_by(
                    '-agr_post_total_count',
                ).values_list(
                    'post__influencer', 'agr_post_total_count',
                )
                inf_ids = []
                for inf_id, count in qs:
                    if len(inf_ids) == 4:
                        break
                    if inf_id not in inf_ids:
                        inf_ids.append(inf_id)
                infs = {
                    inf.id:inf
                    for inf in Influencer.objects.filter(
                        id__in=inf_ids
                    ).prefetch_related('platform_set')
                }
                inf_results = [infs[inf_id].feed_stamp for inf_id in inf_ids]
                if not request.user.is_authenticated():
                    for inf_data in inf_results:
                        inf_data['details_url'] = reverse(
                            'debra.search_views.blogger_info_json_public',
                            args=(inf_data['id'], inf_data['date_created_hash'],)
                        )
                data = {
                    'top': inf_results,
                    'total_count': influencers_count
                }
            elif request.GET.get('top_posts'):
                # post_ids = [x[0] for x in qs.with_campaign_counters().order_by(
                #     '-agr_post_total_count',
                # ).values_list('post', 'agr_post_total_count')[:4]]
                qs = qs.with_campaign_counters().order_by(
                    '-agr_post_total_count',
                ).values_list(
                    'post', 'post__influencer', 'agr_post_total_count',
                )
                inf_ids = []
                post_ids = []
                for post_id, inf_id, count in qs:
                    if len(inf_ids) == 4:
                        break
                    if inf_id not in inf_ids:
                        inf_ids.append(inf_id)
                        post_ids.append(post_id)
                feed_json = feeds_helpers.get_feed_handler_for_platform(None)
                data = {
                    'top': feed_json(
                        request,
                        no_cache=True,
                        with_post_ids=post_ids,
                        preserve_order=True,
                        include_products=False,
                        limit_size=4)
                }
            elif request.GET.get('engagement_distribution'):
                qs = qs.with_campaign_counters().values_list(
                    'post__platform__platform_name', 'agr_post_total_count')
                counts = {}
                for pl, count in qs:
                    if pl in Platform.BLOG_PLATFORMS:
                        pl = 'Blog'
                    counts[pl] = counts.get(pl, 0) + count
                data = {
                    'total_count': sum(counts.values()),
                    'counts': counts,
                }
            elif request.GET.get('engagement_timeline'):
                qs = campaign.post_collection.postanalytics_set.exclude(
                    post__platform__isnull=True
                ).exclude(
                    post__platform__platform_name='Instagram',
                    post__post_image__isnull=True
                ).with_campaign_counters().values_list(
                    'post_url',
                    # 'agr_post_total_count',
                    'count_clickthroughs',
                    'count_unique_clickthroughs',
                    'count_impressions',
                    'count_unique_impressions',
                    'post__platform__platform_name',
                    'created',
                ).order_by(
                    'post_url',
                    'created',
                )
                post_timelines = defaultdict(lambda: defaultdict(list))
                for url, count_clicks, count_unique_clicks, count_views, count_unique_views, pl, date in qs:
                    pl = 'Blog' if pl in Platform.BLOG_PLATFORMS else pl
                    post_timelines[pl][url].append({
                        'count_clicks': count_clicks or 0,
                        'count_unique_clicks': count_unique_clicks or 0,
                        'count_views': count_views or 0,
                        'count_unique_views': count_unique_views or 0,
                        'date': date,
                    })

                # limit = max(Counter([x[0] for x in qs]).values())
                max_date = max(x[6] for x in qs) 
                min_date = min(x[6] for x in qs)
                date_range = (min_date, min_date + timedelta(hours=12))

                timelines = defaultdict(list)

                while date_range[1] <= max_date:
                    for pl, pl_data in post_timelines.items():
                        count_clicks = 0
                        count_views = 0
                        count_unique_clicks = 0
                        count_unique_views = 0
                        for url, post_data_list in pl_data.items():
                            should_count = True
                            while len(post_data_list) > 0 and date_range[0] < post_data_list[0]['date'] <= date_range[1]:
                                if should_count:
                                    count_clicks += post_data_list[0]['count_clicks']
                                    count_views += post_data_list[0]['count_views']
                                    count_unique_clicks += post_data_list[0]['count_unique_clicks']
                                    count_unique_views += post_data_list[0]['count_unique_views']
                                    should_count = False
                                post_data_list.pop(0)
                        timelines[pl].append({
                            'count_clicks': max(count_clicks, timelines[pl][-1]['count_clicks'] if timelines[pl] else 0),
                            'count_views': max(count_views, timelines[pl][-1]['count_views'] if timelines[pl] else 0),
                            'count_unique_clicks': max(count_unique_clicks, timelines[pl][-1]['count_unique_clicks'] if timelines[pl] else 0),
                            'count_unique_views': max(count_unique_views, timelines[pl][-1]['count_unique_views'] if timelines[pl] else 0),
                            'date': date_range[0],
                        })
                    date_range = date_range[1], date_range[1] + timedelta(hours=12)                        

                timelines_chart_data = []
                should_count = True
                while should_count:
                    obj = {}
                    should_count = False
                    for pl, pl_list in timelines.items():
                        if pl_list:
                            should_count = True
                        else:
                            continue
                        obj[pl + '_clicks'] = pl_list[0]['count_clicks']
                        obj[pl + '_views'] = pl_list[0]['count_views']
                        obj[pl + '_unique_clicks'] = pl_list[0]['count_unique_clicks']
                        obj[pl + '_unique_views'] = pl_list[0]['count_unique_views']
                        obj['date'] = pl_list[0]['date']
                        timelines_chart_data.append(obj)
                        pl_list.pop(0)

                # data = {
                #     'post_timelines': post_timelines,
                #     'blog_count': len(post_timelines['Blog']),
                #     # 'original_timelines': timelines,
                #     'timelines': timelines_chart_data,
                #     'ykeys': sorted(timelines.keys()),
                #     'labels': sorted(timelines.keys()),
                # }
                clicks = [{
                    'count_clicks': x['Blog_clicks'],
                    'count_unique_clicks': x['Blog_unique_clicks'],
                    'date': x['date'],
                } for x in timelines_chart_data]
                views = [{
                    'count_views': x['Blog_views'],
                    'count_unique_views': x['Blog_unique_views'],
                    'date': x['date'],
                } for x in timelines_chart_data]
                data = {
                    'clicks': clicks,
                    'views': views,
                }
            elif request.GET.get('instagram_photos'):
                qs = qs.filter(
                    post__platform__platform_name='Instagram'
                ).with_campaign_counters().order_by(
                    '-agr_post_total_count'
                ).values_list(
                    'post__url', 'post__post_image','agr_post_total_count'
                )[:30]
                data = {
                    'instagram_photos': [{
                        'url': url,
                        'img': img
                    } for url, img, _ in qs]
                } 
            else:
                data = []
            data = json.dumps(OrderedDict([('data', data)]), indent=4, cls=DjangoJSONEncoder)
            return HttpResponse(data, content_type="application/json")

    context.update({
        # 'sub_page': 'roi_prediction_reports',
        'campaign_switcher': PageSectionSwitcher(
            constants.CAMPAIGN_SECTIONS, 'reporting',
            url_args=(campaign.id,),
            extra_url_args={'influencer_approval': (campaign.report_id,)},
            hidden=[] if campaign.info_json.get('approval_report_enabled', False) else ['influencer_approval'],
            ),
        'hash_key': hash_key,
        'table_id': 'campaign_report_table',
        'search_page': True,
        'landing_page': not request.user.is_authenticated(),
        'modern_page': True,
        'campaign': campaign,
        'sections': sections,
        'section': section,
        'post_types': post_types,
        'selected_tab': 'campaign',
        'influencers_count': influencers_count,
        'public_link': ''.join([
            constants.MAIN_DOMAIN,
            reverse(
                'debra.job_posts_views.campaign_report',
                args=(
                    campaign.id, 'campaign_overview', campaign.report_hash_key,
                )
            )
        ]),
    })

    return render(
        request, 'pages/job_posts/campaign_report_details_new.html', context)


@login_required
def campaign_create(request, campaign_id=None):
    from debra.serializers import InfluencerApprovalReportTableSerializer
    from debra.mail_proxy import (
        collect_attachments, upload_message_attachments_to_s3)
    from debra.helpers import (
        update_model, PageSectionSwitcher, extract_attachments)
    from masuka.image_manipulator import reassign_campaign_cover

    if campaign_id:
        campaign = get_object_or_404(BrandJobPost, id=campaign_id)
    else:
        campaign = None

    if request.method == 'POST':
        data = json.loads(request.body)
        print data
        attachments = data.get('campaign', {}).get('json_fields', {}).get(
            'outreach_template', {}).get('attachments')
        if attachments:
            attachments = extract_attachments({'attachments': attachments})
            _, s3_attachments = collect_attachments(attachments)
            attachments = upload_message_attachments_to_s3(None, s3_attachments)
            print 'attachments', attachments
            data['campaign']['json_fields']['outreach_template']['attachments'] = attachments

        campaign = update_model(data.get('campaign'))
        if campaign.cover_img_url and "tmp_cover_img" in campaign.cover_img_url:
            reassign_campaign_cover(campaign)

        if campaign.creator_user is None:
            campaign.creator_user = request.user
            campaign.save()

        # call to create all necessary fields
        print '* Influencer collection ID: ', campaign.influencer_collection.id
        report_data = data.get('report')
        if report_data:
            report_data['id'] = campaign.report_id
            report = update_model(report_data)

        if not campaign.client_url and not campaign.client_name:
            campaign.client_url = 'http://{}'.format(
                campaign.creator.domain_name)
            campaign.client_name = campaign.creator.name
            campaign.save()

        campaign.get_or_create_post_collection()

        data = {
            'redirectUrl': '{}?after_create=1'.format(reverse(
                'debra.job_posts_views.campaign_create', args=(campaign.id,))),
            'id': campaign_id,
        }
        data = json.dumps(data, indent=4, cls=DjangoJSONEncoder)
        return HttpResponse(data, content_type="application/json")
    else:
        return redirect(
            reverse('debra.job_posts_views.campaign_edit') + '#/{}'.format(
                campaign_id)
        )


@login_required
def campaign_edit(request):
    context = {
        'selected_tab': 'campaign',
    }
    return render(
        request, 'pages/job_posts/campaign_create.html', context)


@login_required
def list_messages(request, **kwargs):
    from email import message_from_string
    from aggregate_if import Count, Max
    from debra import serializers

    section = kwargs.get('section')
    if section is not None and section not in ['direct', 'campaigns', 'collections']:
        raise Http404()
    section_id = int(kwargs.get('section_id', 0))
    stage = int(request.GET.get('stage', 0))

    if section in ['collections']:
        associated_collections = list(
            request.visitor["base_brand"].influencer_groups.filter(
                creator_brand=request.visitor["base_brand"]
            ).exclude(
                archived=True
            ).order_by('id').only('id', 'archived', 'name')
        )
    else:
        associated_collections = None

    search_query = request.GET.get('q')

    campaign_id = section_id if section in ['campaigns'] else None
    collection_id = section_id if section in ['collections'] else None

    qs = request.visitor["base_brand"].mails.exclude(
        threads__isnull=True
    )

    stage_enabled = qs.filter(stage__isnull=False).exists()

    if campaign_id is not None:
        if campaign_id == 0:
            qs = qs.filter(candidate_mapping__isnull=False)
        else:
            qs = qs.filter(candidate_mapping__job_id=campaign_id)
    elif collection_id is not None:
        if collection_id == 0:
            qs = qs.filter(mapping__isnull=False)
        else:
            qs = qs.filter(mapping__group_id=collection_id)
    elif section in ['direct']:
        qs = qs.filter(
            candidate_mapping__isnull=True,
            mapping__isnull=True,
        )

    qs = qs.annotate(
        agr_opened_count=Count(
            'threads',
            only=(
                Q(threads__mandrill_id__regex=r'.(.)+') &
                (
                    Q(threads__type=MailProxyMessage.TYPE_OPEN) |
                    Q(threads__type=MailProxyMessage.TYPE_CLICK)
                )
            )
        ),
        agr_emails_count=Count(
            'threads',
            only=(
                # Q(threads__mandrill_id__regex=r'.(.)+') &
                Q(threads__type=MailProxyMessage.TYPE_EMAIL)
            )
        ),
        agr_last_message=Max(
            'threads__ts',
            only=(
                # Q(threads__mandrill_id__regex=r'.(.)+') &
                Q(threads__type=MailProxyMessage.TYPE_EMAIL)
            )
        ),
        agr_last_sent=Max(
            'threads__ts',
            only=(
                # Q(threads__mandrill_id__regex=r'.(.)+') &
                Q(threads__type=MailProxyMessage.TYPE_EMAIL) &
                Q(threads__direction=MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER)
            )
        ),
        agr_last_reply=Max(
            'threads__ts',
            only=(
                # Q(threads__mandrill_id__regex=r'.(.)+') &
                Q(threads__type=MailProxyMessage.TYPE_EMAIL) &
                Q(threads__direction=MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND)
            )
        ),
    )

    qs = qs.exclude(agr_emails_count=0)

    if search_query:
        qs = qs.filter(
            Q(influencer__name__icontains=search_query) |
            Q(influencer__blogname__icontains=search_query) |
            Q(influencer__blog_url__icontains=search_query)
        )

    def get_counts(qs):
        counts = list(
            qs.values_list('stage', 'has_been_read_by_brand', 'id')
        )
        stage_counts = Counter(x for x, _, _ in counts)
        stage_counts[-1] = sum(stage_counts.values())
        unread_counts = defaultdict(int)
        for stage, mark, mailbox_id in counts:
            if mailbox_id:
                unread_counts[stage] += int(not mark)
        unread_counts[-1] = sum(unread_counts.values())

        return {
            'stage_counts': stage_counts,
            'unread_counts': unread_counts,
            'total_count': stage_counts[-1],
        }

    counts = get_counts(qs)

    if stage >= 0:
        qs = qs.filter(stage=stage)

    qs = qs.prefetch_related(
        'influencer__platform_set',
        'influencer__shelf_user__userprofile',
    )

    def pre_serialize_processor(paginated_qs):
        thread_2_message = dict(MailProxyMessage.objects.filter(
            type=1,
            thread_id__in=[x.id for x in paginated_qs]
        ).order_by(
            'thread', 'ts'
        ).distinct('thread').values_list('thread', 'msg'))
        get_subject = lambda msg: message_from_string(
            msg.encode('utf-8'))['subject']
        for p in paginated_qs:
            p.agr_mailbox_subject = get_subject(
                thread_2_message.get(p.id)
            )

        brand_user_mapping = {
            x.influencer_id: x
            for x in InfluencerBrandUserMapping.objects.filter(
                influencer__in=[p.influencer for p in paginated_qs],
                user=request.user
            )
        }

        for p in paginated_qs:
            p.agr_brand_user_mapping = brand_user_mapping.get(
                p.influencer.id)
            if p.agr_brand_user_mapping:
                p.agr_notes = p.agr_brand_user_mapping.notes
            else:
                p.agr_notes = None

    # 'has_been_read_by_brand', '-reply_stamp_agr'

    context = search_helpers.generic_reporting_table_context(
        request,
        queryset=qs,
        serializer_class=serializers.UnlinkedMessagesTableSerializer,
        serializer_context={},
        include_total=False,
        # visible_columns=campaign.info_json.get(
        #     'visible_columns', {}
        # ).get(
        #     str(campaign_stage),
        #     serializer_class.VISIBLE_COLUMNS
        # ),
        # order_params=['post__influencer'],
        hidden_fields=['mailbox_stage'] if not stage_enabled else [],
        default_order_params=[('has_been_read_by_brand', 0), ('agr_last_message', 1)],
        pre_serialize_processor=pre_serialize_processor,
        # distinct=['post__influencer'],
    )

    # stages = [(-1, 'All')] + MailProxy.STAGE
    stages = MailProxy.STAGE

    context.update({
        # 'campaign_switcher': PageSectionSwitcher(
        #     constants.CAMPAIGN_SECTIONS, 'campaign_setup',
        #     url_args=(campaign.id,),
        #     extra_url_args={'influencer_approval': (campaign.roi_report.id,)},
        #     hidden=[] if pre_outreach_enabled else ['influencer_approval'],
        # ),
        'switcher': PageSectionSwitcher(
            stages, stage,
            counts=counts['stage_counts'],
            urls=['?stage={}'.format(n) for n, _ in stages],
            extra={
                'unread_count': counts['unread_counts'],
            },
        ),
        'section_switcher': PageSectionSwitcher([]),
        'table_id': 'unlinked_messages',
        'table_classes': ' '.join([
            'messages-table',
        ]),
        'messages_count': counts['total_count'],
        'show_conversations': True,
        'InfluencerJobMapping': InfluencerJobMapping,
        'selected_tab': 'outreach',
        'campaign_id': campaign_id,
        'campaigns': request.visitor["campaigns"] if section in ['campaigns'] else [],
        'collection_id': collection_id,
        'collections': associated_collections,
        'section': section,
    })

    return render(
        request, 'pages/job_posts/unlinked_messages_details.html', context)


def edit_notes(request):
    if request.method == 'POST':
        data = json.loads(request.body)
        mapping, _ = InfluencerBrandUserMapping.objects.get_or_create(
            influencer_id=data.get('influencer_id'), user_id=request.user.id)
        mapping.notes = data.get('notes')
        mapping.save()
    return HttpResponse()


class BrandTaxonomyView(BaseTableViewMixin, BaseView):

    def set_params(self, request, *args, **kwargs):
        super(BrandTaxonomyView, self).set_params(request, *args, **kwargs)

    def get(self, request, *args, **kwargs):
        self.set_params(request, *args, **kwargs)
        return render(request, 'pages/job_posts/brand_taxonomy.html',
            self.context)

    @cached_property
    def queryset(self):
        return BrandTaxonomy.objects.all()

    @cached_property
    def filtered_queryset(self):
        qs = super(BrandTaxonomyView, self).filtered_queryset
        tags = []
        if self.request.GET.get('style_tag'):
            tags.append(Q(style_tag__iexact=self.request.GET.get('style_tag')))
        if self.request.GET.get('product_tag'):
            tags.append(Q(product_tag__iexact=self.request.GET.get(
                'product_tag')))
        if self.request.GET.get('price_tag'):
            tags.append(Q(price_tag__iexact=self.request.GET.get('price_tag')))
        if tags:
            qs = qs.filter(reduce(lambda a, b: a | b, tags))
        return qs

    @cached_property
    def default_order_params(self):
        return [('id', 1),]

    @cached_property
    def serializer_class(self):
        from debra.serializers import BrandTaxonomyTableSerializer
        return BrandTaxonomyTableSerializer


brand_taxonomy = login_required(BrandTaxonomyView.as_view())


from debra.pipeline_views import (LoadInfluencersView, BloggerApprovalView,
    CampaignPipelineView,)


campaign_load_influencers = login_required(LoadInfluencersView.as_view())


campaign_approval = login_required(BloggerApprovalView.as_view())


campaign_setup = login_required(CampaignPipelineView.as_view())
