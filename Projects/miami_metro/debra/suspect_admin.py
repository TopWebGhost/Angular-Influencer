from debra import models
from debra import constants
from debra import serializers
from django.shortcuts import render, redirect, render_to_response, get_object_or_404
from django.template import RequestContext
from django.contrib.admin import AdminSite, ModelAdmin
from django.conf.urls.defaults import patterns, include, url
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseRedirect
from debra import admin_helpers
import json
import pdb
import datetime


# helpers
def table_page(options):
    if options["request"].method == 'POST':

        try:
            body = json.loads(options["request"].body)        
        except ValueError:
            body = options["request"].POST

        obj = get_object_or_404(options["model"], id=body.get('pk'))
        if obj.qa:
            obj.qa = " ".join((obj.qa, options["request"].visitor["auth_user"].username))
        else:
            obj.qa = options["request"].visitor["auth_user"].username
        obj.save()

        name = body.get('name')

        if name == "update_collections":
            selected_collections = body.get('collections', [])
            groups = models.InfluencersGroup.objects.filter(
                id__in=constants.ATUL_COLLECTIONS_IDS)
            for group in groups:
                if group.id in selected_collections:
                    group.add_influencer(obj.influencer)
                else:
                    group.remove_influencer(obj.influencer)
            return HttpResponse()
        if name == "append_comment":
            data = body
            comment = data.get("new_comment")
            inf = models.Influencer.objects.get(id=data.get("influencer"))
            inf.append_comment(comment, user=options["request"].visitor["auth_user"])
            return HttpResponse(serializers.transform_customer_comments(value=inf.customer_comments))
        if name == "action:update":
            obj = None
            for k, v in options["request"].POST.iteritems():
                print("Inside action:update. [k,v]=[%r,%r]" % (k,v))
                if k.startswith("update:"):
                    k = k.split(':')
                    objtype = k[1]
                    fieldname = k[2]
                    print("objtype: [%r] fieldname: [%r]" % (objtype, fieldname))
                    # WTF is this ??? 
                    if len(k) == 3:
                        row_id = k[3]
                    else:
                        row_id = options["request"].POST.get('iid')
                    if objtype == "i":
                        obj = get_object_or_404(models.Influencer, id=row_id)
                    elif objtype == "p":
                        obj = get_object_or_404(models.Platform, id=row_id)
                    print("Obj: [%r]" % obj)
                    if hasattr(obj, fieldname):
                        print("Setting %r field [%r] to %r, current: [%r]" % (obj, fieldname, v, getattr(obj, fieldname)))
                        setattr(obj, fieldname, v)
                        obj.save()
                        if objtype == "i":
                            if fieldname == "blog_url":
                                admin_helpers.handle_blog_url_change(obj, v)
                            else:
                                #how to handle platforms which has no url in influencer model?
                                admin_helpers.handle_social_handle_updates(obj, fieldname, v)
            obj = get_object_or_404(options["model"], id=options["request"].POST.get('pk'))
            obj.status = models.InfluencerCheck.STATUS_MODIFIED
            obj.save()
            return HttpResponse()
        if name == "action:noproblem":

            obj = get_object_or_404(options["model"], id=options["request"].POST.get('pk'))
            obj.status = models.InfluencerCheck.STATUS_MODIFIED
            obj.save()
            print("Inside action:noproblem. [%r]" % obj)
            return HttpResponse()
        if name == "action:blacklist":
            row_id = options["request"].POST.get('iid')
            obj = get_object_or_404(models.Influencer, id=row_id)
            obj.set_blacklist_with_reason('suspicion_table')
            print("Inside action:blacklist. [%r]" % obj)
            obj = get_object_or_404(options["model"], id=options["request"].POST.get('pk'))
            obj.status = models.InfluencerCheck.STATUS_MODIFIED
            obj.save()

            return HttpResponse()
        if name == "action:blacklist_rel":
            print("Inside action:blacklist_rel. Not sure what this is")
            obj = get_object_or_404(options["model"], id=options["request"].POST.get('pk'))
            try:
                data_json = json.loads(obj.data_json)
            except:
                return HttpResponse()
            obj.status = models.InfluencerCheck.STATUS_MODIFIED
            obj.save()
            rel_obj = getattr(models, data_json[0][0]).objects.get(id=data_json[0][1])
            rel_obj.set_blacklist_with_reason('suspicion_table')
            return HttpResponse()
        if name == "action:report":
            pass
        row_id = options["request"].POST.get('pk')
        obj = get_object_or_404(options["model"], id=row_id)
        value = options["request"].POST.get('value')
        data = {
            name: value
        }
        serializer = options["store_serializer"](obj, data=data, partial=True)
        if serializer.is_valid():
            serializer.save()
        else:
            return HttpResponseBadRequest(serializer.errors)
        return HttpResponse()
    else:
        if options.get("debug"):
            query = options["query"]
            data = admin_helpers.get_objects(options["request"], query, options["load_serializer"], context=options['context'])
            return HttpResponse("<body></body>")
        if options["request"].is_ajax():
            query = options["query"]
            data = admin_helpers.get_objects(options["request"], query, options["load_serializer"], context=options['context'])
            return HttpResponse(data, content_type="application/json")
        else:
            return render(options["request"], options["template"],
                options["context"],
                context_instance=RequestContext(options["request"]))


class SuspectItemsAdminSite(AdminSite):

    def _defaults(self, request, query):
        return {
            "request": request,
            "load_serializer": serializers.InfluencerCheckSerializer,
            "store_serializer": serializers.InfluencerCheckSerializer,
            "context": {
                'statuses': models.InfluencerCheck.STATUSES,
                'causes': models.InfluencerCheck.CAUSES,
                'atul_collections': constants.get_atul_collections()
            },
            "query": query.prefetch_related(
                'influencer__group_mapping',
                'influencer__platform_set',
                'influencer__influencer_customer_comments'
            ),
            "model": models.InfluencerCheck,
            "template": 'pages/admin/check_tables/base.html',
        }

    def get_urls(self):
        urls = super(SuspectItemsAdminSite, self).get_urls()
        my_urls = patterns('',
            url(r'^by_cause/(?P<cause_id>.*?)/$', self.admin_view(self.suspect_by_cause), name="suspect_by_cause"),
            url(r'^broken_url/$', self.admin_view(self.broken_url), name="broken_url"),
            url(r'^broken_email/$', self.admin_view(self.broken_email), name="broken_email"),
            url(r'^similar_blog_blogger_name/$', self.admin_view(self.similar_blog_blogger_name), name="similar_blog_blogger_name"),
            url(r'^suspect_blogname/$', self.admin_view(self.suspect_blogname), name="suspect_blogname"),
            url(r'^suspect_description/$', self.admin_view(self.suspect_description), name="suspect_description"),
            url(r'^suspect_location/$', self.admin_view(self.suspect_location), name="suspect_location"),
            url(r'^suspect_high_comments/$', self.admin_view(self.suspect_high_comments), name="suspect_high_comments"),
            url(r'^suspect_social_followers/$', self.admin_view(self.suspect_social_followers), name="suspect_social_followers"),
            url(r'^suspect_low_social_platforms/$', self.admin_view(self.suspect_low_social_platforms), name="suspect_low_social_platforms"),
            url(r'^suspect_big_publication/$', self.admin_view(self.suspect_big_publication), name="suspect_big_publication"),


            #### NOT USED ####
            url(r'^suspect_social_dup/$', self.admin_view(self.suspect_social_dup), name="suspect_social_dup"),
            url(r'^suspect_social_mainstream/$', self.admin_view(self.suspect_social_mainstream), name="suspect_social_mainstream"),


            url(r'^suspect_high_followers/$', self.admin_view(self.suspect_high_followers), name="suspect_high_followers"),
            url(r'^suspect_high_posts/$', self.admin_view(self.suspect_high_posts), name="suspect_high_posts"),
            url(r'^suspect_social_handle/$', self.admin_view(self.suspect_social_handle), name="suspect_social_handle"),
            url(r'^suspect_social_nocomments/$', self.admin_view(self.suspect_social_nocomments), name="suspect_social_nocomments"),
            url(r'^suspect_url_changed/$', self.admin_view(self.suspect_url_changed), name="suspect_url_changed"),
            url(r'^suspect_similar_content/$', self.admin_view(self.suspect_similar_content), name="suspect_similar_content"),
            url(r'^suspect_similar_blog/$', self.admin_view(self.suspect_similar_blog), name="suspect_similar_blog"),
            url(r'^suspect_no_content/$', self.admin_view(self.suspect_no_content), name="suspect_no_content"),
        )
        return my_urls + urls

    def suspect_by_cause(self, request, cause_id):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=cause_id)
        return table_page({
            "request": request,
            "load_serializer": serializers.InfluencerCheckSerializer,
            "store_serializer": serializers.InfluencerCheckSerializer,
            "context": {
                'statuses': models.InfluencerCheck.STATUSES,
                'causes': models.InfluencerCheck.CAUSES
            },
            "template": 'pages/admin/check_tables/broken_url.html',
            "query": query,
            "model": models.InfluencerCheck,
            #"debug": True
        })

    def broken_url(self, request):
        query = models.InfluencerCheck.objects.filter(
            influencer__relevant_to_fashion=True,
            status=models.InfluencerCheck.STATUS_NEW,
            cause=models.InfluencerCheck.CAUSE_NON_EXISTING_URL
        )
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'custom_message',
                "sTitle": 'ERROR MESSAGE',
                "editable": False,
            }, {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", "blog_url"],
            },{
                "mData": 'fields',
                "sTitle": 'QUESTIONABLE URL',
                "transform": 'fields'
            }, {
                "mData": 'all_platforms',
                "sTitle": 'Platforms',
                "editable": False
            }, {
                "mData": 'autovalidated_platforms',
                "sTitle": 'Autovalidated',
                "editable": False
            }, {
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'No Problem',
                        "cb": ["upload_fixed", "action:noproblem"]
                    },
                    {
                        "label": 'Blacklist',
                        "cb": ["upload_fixed", "action:blacklist"]  
                    },
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", "action:update"]
                    }
                ]
            }, {
                "mData": 'customer_comments',
                "sTitle": "Report",
                "add_comment": "customer_comments"
            }, {
                "mData": 'id',
                "sTitle": "Collections",
                "collections": True
            }
        ])
        return table_page(options)

    def broken_email(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_EMAIL)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'email_for_advertising_or_collaborations',
                "sTitle": 'For brands',
                "transform": 'email_for_advertising_or_collaborations'
            },{
                "mData": 'email_all_other',
                "sTitle": 'Remaining',
                "transform": 'email_all_other'
            },{
                "mData": 'contact_form_if_no_email',
                "sTitle": 'Contact Form',
                "transform": 'contact_form_if_no_email'
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }, {
                "mData": 'customer_comments',
                "sTitle": "Report",
                "add_comment": "customer_comments"
            }, {
                "mData": 'id',
                "sTitle": "Collections",
                "collections": True
            }
        ])
        return table_page(options)

    def suspect_blogname(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_NAME_BLOGNAME)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'blogname',
                "sTitle": 'Blog name',
                "transform": 'blogname'
            }, {
                "mData": 'name',
                "sTitle": 'Blogger name',
                "transform": 'name'
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)

    def similar_blog_blogger_name(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_NAME_BLOGNAME)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'blogname',
                "sTitle": 'Blog name',
                "transform": 'blogname'
            }, {
                "mData": 'name',
                "sTitle": 'Blogger name',
                "transform": 'name'
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }, {
                "mData": 'customer_comments',
                "sTitle": "Report",
                "add_comment": "customer_comments"
            }, {
                "mData": 'id',
                "sTitle": "Collections",
                "collections": True
            }
        ])
        return table_page(options)


    def suspect_description(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_DESCRIPTION)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'description',
                "sTitle": 'Description',
                "transform": 'description'
            }, {
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)

    def suspect_location(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__show_on_search=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_LOCATION)
        query = query.exclude(influencer__blacklisted=True).exclude(influencer__source__icontains='brands')
        query = query.distinct()
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'demographics_location',
                "sTitle": 'Location',
                "transform": 'demographics_location'
            }, {
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }, {
                "mData": 'customer_comments',
                "sTitle": "Report",
                "add_comment": "customer_comments"
            }, {
                "mData": 'id',
                "sTitle": "Collections",
                "collections": True
            }
        ])
        return table_page(options)

    def suspect_social_followers(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__show_on_search=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_SOCIAL_PLATFORM_OUTLIER_FOLLOWERS)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'platform_details',
                "sTitle": 'QUESTIONABLE Url',
                "transform": 'platform_details'
            },{
                "mData": 'socials',
                "sTitle": 'Social Url',
                "transform": 'socials'
            }, {
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }, {
                "mData": 'customer_comments',
                "sTitle": "Report",
                "add_comment": "customer_comments"
            }, {
                "mData": 'id',
                "sTitle": "Collections",
                "collections": True
            }
        ])
        return table_page(options)

    def suspect_low_social_platforms(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_HIGH_COMMENTS_LOW_SOCIAL_URLS)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'socials',
                "sTitle": 'Social Url',
                "transform": 'socials'
            }, {
                "mData": 'id',
                "sTitle": 'Add handle',
                "add_handle": True,
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }, {
                "mData": 'customer_comments',
                "sTitle": "Report",
                "add_comment": "customer_comments"
            }, {
                "mData": 'id',
                "sTitle": "Collections",
                "collections": True
            }
        ])
        return table_page(options)

    def suspect_big_publication(self, request):
        """
        Table should have
        <influencer blog url> <blogger name> <#of posts/month> <Actions>

        Actions:
            a) Blacklist as Large publication
        """
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_BIG_PUBLICATION)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'socials',
                "sTitle": 'Social Url',
                "transform": 'socials'
            }, {
                "mData": 'id',
                "sTitle": 'Add handle',
                "add_handle": True,
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }, {
                "mData": 'customer_comments',
                "sTitle": "Report",
                "add_comment": "customer_comments"
            }, {
                "mData": 'id',
                "sTitle": "Collections",
                "collections": True
            }
        ])
        return table_page(options)


    ##################################################################################################
    ##################################################################################################
    ##################################################################################################
    ##################################################################################################
    ################################################# BELOW NOT USED RIGHT NOW #######################
    ##################################################################################################






    def suspect_social_dup(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_DUPLICATE_SOCIAL)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", "blog_url"],
            },{
                "mData": 'socials',
                "sTitle": 'Influencer socials',
                "transform": 'socials'
            },{
                "mData": 'related',
                "sTitle": 'Related socials',
                "transform": 'related.0.socials'
            }, {
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'No Problem',
                        "cb": ["upload_fixed", "action:noproblem"]
                    },
                    {
                        "label": 'Blacklist Influencer',
                        "cb": ["upload_fixed", "action:blacklist"]
                    },
                    {
                        "label": 'Blacklist Related',
                        "cb": ["upload_fixed", "action:blacklist_rel"]
                    },
                    {
                        "label": 'Update Url',
                        "cb": ["upload_fixed", "action:update"]
                    },
                ]
            }
        ])
        return table_page(options)

    def suspect_social_mainstream(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_BROKEN_SOCIAL)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'custom_message',
                "sTitle": 'ERROR MESSAGE',
                "editable": False,
            },{
                "mData": 'fields',
                "sTitle": 'Social Url',
                "transform": 'fields'
            }, {
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)


    def suspect_high_comments(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_HIGH_COMMENTS_LOW_SOCIAL_URLS)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'custom_message',
                "sTitle": 'ERROR MESSAGE',
                "editable": False,
            },{
                "mData": 'socials',
                "sTitle": 'Social Url',
                "transform": 'socials'
            },{
                "mData": 'id',
                "sTitle": 'Add handle',
                "add_handle": True,
            }, {
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)




    def suspect_high_followers(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_HIGH_FOLLOWERS_LOW_SOCIAL_URLS)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'socials',
                "sTitle": 'Social Url',
                "transform": 'socials'
            },{
                "mData": 'id',
                "sTitle": 'Add handle',
                "add_handle": True,
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)

    def suspect_high_posts(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_HIGH_POSTS_LOW_SOCIAL_URLS)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'socials',
                "sTitle": 'Social Url',
                "transform": 'socials'
            }, {
                "mData": 'id',
                "sTitle": 'Add handle',
                "add_handle": True,
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)

    def suspect_social_handle(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_SOCIAL_HANDLES)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'platform_details',
                "sTitle": 'Handle',
                "transform": 'platform_details'
            }, {
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)

    def suspect_social_nocomments(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_NO_COMMENTS)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'BLOG URL',
                "editable": False,
                "fnRender":  ["render_link", 'blog_url'],
            },{
                "mData": 'platform_details',
                "sTitle": 'Handle',
                "transform": 'platform_details'
            }, {
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)

    def suspect_url_changed(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_URL_CHANGED)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'Blog url',
                "transform": 'blog_url'
            },{
                "mData": 'custom_message',
                "sTitle": 'message',
                "editable": False,
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)

    def suspect_no_content(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_NO_CONTENT)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'Blog url',
                "transform": 'blog_url'
            },{
                "mData": 'custom_message',
                "sTitle": 'message',
                "editable": False,
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)

    def suspect_similar_content(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_SIMILAR_CONTENT)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'Blog url',
                "transform": 'blog_url'
            },{
                "mData": 'custom_message',
                "sTitle": 'message',
                "editable": False,
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)

    def suspect_similar_blog(self, request):
        query = models.InfluencerCheck.objects.filter(influencer__relevant_to_fashion=True, status=models.InfluencerCheck.STATUS_NEW, cause=models.InfluencerCheck.CAUSE_SUSPECT_SIMILAR_BLOG_URLS)
        options = self._defaults(request, query)
        options["context"]["columns"] = json.dumps([
            {
                "mData": 'blog_url',
                "sTitle": 'Blog url',
                "transform": 'blog_url'
            },{
                "mData": 'custom_message',
                "sTitle": 'message',
                "editable": False,
            },{
                "mData": 'id',
                "sTitle": 'ACTIONS',
                "actions": [
                    {
                        "label": 'Save',
                        "cb": ["upload_fixed", 'action:update']
                    },
                ]
            }
        ])
        return table_page(options)

suspect_admin_site = SuspectItemsAdminSite(name="suspect_admin", app_name="suspect_admin")
