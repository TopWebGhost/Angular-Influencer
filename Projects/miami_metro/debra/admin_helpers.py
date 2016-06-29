from celery.decorators import task

import re
import math
import json
import operator
import datetime

from django.db.models import Q
from django.contrib.auth.models import Group
from django.core.serializers.json import DjangoJSONEncoder
from django.core.exceptions import FieldError
from platformdatafetcher import fetchertasks, fetcher, postprocessing, pbfetcher, geocoding, platformutils

from debra.helpers import multikeysort
from debra.decorators import cached_property
from debra.models import Influencer, UserProfile, InfluencersGroup
from debra import constants


def get_objects(request, queryset, klass_serializer, no_slices=None, current_slice=None, context=None, options=None):
    """
        :param request: ``HttpRequest`` instance
        :param queryset: queryset to be serialized
        :param klass_serializer: serializer class
        :param columns_def: definition of columns

            columns_def= [
                {
                    'field': 'fieldname',       # name of field
                    'title': 'Title',           # title used
                    'type': 'text',             # type of field: text or bool
                    'filtering': True,          # should be able to filter column values
                    'sortable': True,           # should be able to sort values according to column value
                    'editable': True            # can we edit that column
                },
                ...
            ]

        do not allow to sort/filter/edit function values!

        :return: string - serialized data

    """

    #slicing code
    if no_slices and current_slice:
        no_slices = int(no_slices)
        current_slice = int(current_slice)
        total = len(queryset) if type(queryset) == list else queryset.count()
        id_sorted = sorted(queryset, key=lambda x: x.id) if type(queryset) == list else queryset.order_by('id')
        slice_size = int(round(float(total) / no_slices))
        slice_start = max(0, min(total-1, (current_slice - 1) * slice_size))
        slice_end = max(0, min(total-1, current_slice * slice_size))
        slice_start_id = id_sorted[slice_start].id
        slice_end_id = id_sorted[slice_end].id
        if type(queryset) == list:
            queryset = [item
                for item in queryset if item.id in xrange(slice_start_id, slice_end_id)]
        else:
            queryset = queryset.filter(id__gte=slice_start_id, id__lt=slice_end_id)

    sSearch = request.GET.get('sSearch')

    serializer_instance = klass_serializer()

    options = options or {}
    options.update({
        'model': klass_serializer.Meta.model,
    })

    if sSearch:
        searches = []
        for name, field in serializer_instance.get_fields().items():
            if field.source:
                source = field.source
            elif hasattr(field, 'method_name'):
                # do not implement search by SerializerMethodField values
                pass
            else:
                source = name
            source = '__'.join(source.split('.'))
            if source.endswith('_id'):
                source = source[:-3]
            q_list = []
            try:
                int(sSearch)
                q_list.append(Q(**{"%s" % source: sSearch}))
            except ValueError:
                q_list.append(Q(**{"%s__icontains" % source: sSearch}))
            q_expr = reduce(lambda x, y: x | y, q_list)
            try:
                queryset.filter(q_expr)
            except (FieldError, ValueError, TypeError) as e:
                print ' *** (failed) ', source
            else:
                print ' *** ', source
                searches.append(q_expr)
        if type(queryset) == list:
            # @todo: implement filtering for lists
            pass
        else:
            queryset = queryset.filter(reduce(lambda a, b: a | b, searches))

    iTotalRecords = len(queryset) if type(queryset) == list else queryset.count()

    sortCols = []
    col_id_name = {}
    sortables = {}
    sort_dirs = {}
    for (key, value) in request.GET.iteritems():
        #print key, value
        if key.startswith("iSortCol_"):
            sortCols.append((key.split("iSortCol_")[1], value))
        if key.startswith("mDataProp_"):
            col_id_name[key.split("mDataProp_")[1]] = value
        if key.startswith("sSortDir_"):
            sort_dirs[key.split("sSortDir_")[1]] = value
        if key.startswith("bSearchable_"):
            sortables[key.split("bSearchable_")[1]] = value == 'true'

    iDisplayStart = int(request.GET.get('iDisplayStart', '0'))
    iDisplayLength = int(request.GET.get('iDisplayLength', '10'))
    sEcho = request.GET.get('sEcho', '')

    sortCols.sort()
    #print sortCols
    #print col_id_name
    #print sortables
    #print sort_dirs
    order_by = []
    # brand_fields_set = set(x.attname for x in queryset.model._meta.fields)
    contains_flags = False
    for priority, sortCol in sortCols:
        if sortables[sortCol]:
            field_name = col_id_name[sortCol]

            field = serializer_instance.get_fields().get(field_name)
            if field.source:
                source = field.source
            else:
                source = field_name

            source = '__'.join(source.split('.'))
            if source.endswith('_id'):
                source = source[:-3]

            try:
                options["model"].objects.order_by(source)
            except (FieldError, ValueError, TypeError):
                source = 'flag_{}'.format(source)
                contains_flags = True

            if sort_dirs[priority] == 'asc':
                order_by.append(source)
            else:
                order_by.append('-' + source)
    #print order_by

    if order_by:
        print 'ORDER BY:'
        print '\n'.join(["* {}".format(x) for x in order_by])
        if not contains_flags and type(queryset) != list:
            queryset = queryset.order_by(*order_by)
        else:
            queryset = list(queryset)
            queryset = multikeysort(
                queryset, order_by,
                getter=options.get("getter", operator.attrgetter)
            )
    else:
        orderby = options.get('orderby', [])
        fields = [x.name for x in options["model"]._meta.fields if not x.rel]
        if "date_validated" in fields:
            orderby.append("-date_validated")
        if "date_edited" in fields:
            orderby.append("-date_edited")
        orderby.append("-id")
        if type(queryset) == list:
            queryset = multikeysort(
                queryset, orderby, getter=options.get('getter', operator.attrgetter))
        else:
            queryset = queryset.order_by(*orderby)

    queryset = queryset[iDisplayStart:iDisplayStart+iDisplayLength]
    try:
        queryset = context.get('sliced_queryset_handler')(queryset)
    except (AttributeError, KeyError, TypeError):
        pass
    #iTotalDisplayRecords = query.count()
    aaData = klass_serializer(queryset, many=True, context=context).data
    data = {
        'sEcho': sEcho,
        'iTotalRecords': iTotalRecords,
        'iTotalDisplayRecords': iTotalRecords,
        'aaData': aaData
    }

    # filters = {}
    # ordering = None
    # for key, value in request.GET.iteritems():
    #     if key.startswith("filter"):
    #         fkey = re.findall("filter\[(.*?)\]", key)
    #         if len(fkey):
    #             filters[fkey[0]+"__icontains"] = value
    #     if key.startswith("sorting"):
    #         skey = re.findall("sorting\[(.*?)\]", key)
    #         if len(skey):
    #             if value == 'asc':
    #                 ordering = skey[0]
    #             else:
    #                 ordering = '-'+skey[0]

    # page = int(request.GET.get("page", 1))
    # count = int(request.GET.get("count", 50))

    # total = queryset.filter(**filters)
    # if ordering:
    #     total = total.order_by(ordering)
    # objs = total[(page-1)*count:page*count]
    # objs_data = klass_serializer(objs, many=True).data
    # data = {
    #     'total': total.count(),
    #     'columns': columns_def,
    #     'result': {v['id']: v for v in objs_data}.values()
    # }

    return json.dumps(data, cls=DjangoJSONEncoder)


def handle_blog_url_change(influencer, new_blog_url):
    """
    we should first update the influencer.blog_url and then update the platform url
    we then need to make sure to redetect the platform name
    """
    print "updating blog_url to this %r for %r " % (new_blog_url, influencer)
    old_url = influencer.blog_url
    influencer.blog_url = new_blog_url
    influencer.save()
    plat = influencer.blog_platform
    print "Found %s platforms " % plat
    if plat:
        plat.url=new_blog_url
        plat.save()
    else:
        print "ok, creating a new blog platform"
        plat = fetcher.create_platforms_from_urls([new_blog_url], platform_name_fallback=True)[0]
        plat.influencer = influencer
        plat.save()

    postprocessing.do_redetect_platform_name.apply_async(args=[plat.id], queue='celery')
    print "For %s, we needed to resubmit the name detection" % plat


def update_or_create_new_platform(influencer, platform_name, platform_url):
    from debra.models import Platform
    dups = Platform.find_duplicates(influencer, platform_url, platform_name, exclude_url_not_found_true=False)
    if dups and len(dups) > 0:
        print "Found duplicates for %r " % platform_url
        d = dups[0]
        d = d.handle_duplicates()
        d.url_not_found = False
        d.validated = True
        d.url = platform_url
        d.save()
        print "Handled duplicates, final platform staying: %r " % d
        return d
    else:
        d = Platform.objects.create(influencer=influencer, url=platform_url, platform_name=platform_name)
        d.validated = True
        d.save()
        print "Created a new platform: %r " % d
        return d


def handle_social_handle_updates(influencer, url_field, new_val):
    """
    Not using celery because it can cause race-condition errors.
    """
    #task_handle_social_handle_updates.apply_async([influencer.id, url_field, new_val], queue='celery')
    task_handle_social_handle_updates(influencer.id, url_field, new_val)

@task(name='debra.admin_helpers.task_handle_social_handle_updates', ignore_result=True)
def task_handle_social_handle_updates(influencer_id, url_field, new_val):

    """
    Algorithm:
    if the url_field is a demographics_location, we just re-run the API handler for normalizing the location
        return

    find all existing platforms for the given platform name
    find all that are entered by the Q/A person: new_val.split(' ')
        for each such entry, check
            if this already exists, mark it as validated=True and (if url_not_found=True => change it to False)
            if it doesn't exist yet, create a new platform and then mark it validated=True
    now, for all the validated platforms, start indepth crawl for them
    """
    from debra.models import Influencer, Platform
    from debra import constants
    from django.conf import settings

    influencer = Influencer.objects.get(id=influencer_id)
    print("Social_handle_change started for %r %r %r" % (influencer, url_field, new_val))

    if url_field == 'demographics_location':
        influencer.demographics_location_normalized = None
        influencer.save()
        geocoding.normalize_location.apply_async((influencer.id,))
        return

    if not url_field in Influencer.field_to_platform_name.keys():
        print("%r is not a social url " % url_field)
        return

    new_plat_urls = new_val.split(' ') if new_val else []
    platform_name = Influencer.field_to_platform_name[url_field]
    assert getattr(influencer, url_field) == new_val

    plats = Platform.objects.filter(influencer=influencer, platform_name=platform_name)
    # first set url_not_found to True and reset validated_handle for all
    for o in plats:
        platformutils.set_url_not_found('admin_helpers_social_handle_change', o)
    print("plats that are marked url_not_found: %s " % plats)

    # unset the profile picture url so that new picture is used from the new url
    # only if the influencer has not already updated the profile (so she could have updated the profile pic as well)
    if not (influencer.validated_on and constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED in influencer.validated_on):
        influencer.profile_pic_url = None
        influencer.set_profile_pic()
        influencer.save()

    # now create or update those that were found in the new_val
    for new_url in new_plat_urls:
        if len(new_url.strip()) < 5:
            print("This url %r is not a valid url, skipping " % new_url)
            continue
        plat = update_or_create_new_platform(influencer, platform_name, new_url)
        ## TODO : Change it later to so that we do an indepth fetch right away but this is preventing us right now
        ## TODO : from fetching data for new folks quickly. So, invoking daily fetch for 1 page only based on
        ## TODO : RelevantToFashionPolicy policy in pbfetcher.py
        #fetchertasks.submit_indepth_platform_task(fetchertasks.indepth_fetch_platform_data, plat)
        #fetchertasks.submit_platform_task(fetchertasks.fetch_platform_data, plat)
        #policy = pbfetcher.policy_for_platform(plat)
        #if policy is not None and plat.platform_name in settings.DAILY_FETCHED_PLATFORMS:
        #    print("Fetching %s" % plat)
        #    fetchertasks.fetch_platform_data(plat.id, policy.name)

    #influencer.denormalize_fast()
    print("Finished Social_handle_change for %r " % influencer)


def admin_update_influencer_fields(influencer_id, **kwargs):
    admin_task_update_influencer_fields.apply_async([influencer_id, kwargs], queue='celery')


@task(name='debra.admin_helpers.admin_task_update_influencer_fields', ignore_result=True)
def admin_task_update_influencer_fields(influencer_id, **kwargs):
    from debra.models import Influencer
    inf = Influencer.objects.filter(id=influencer_id)
    inf.update(**kwargs)


def update_stripe_info():
    pass


def influencers_informations_nonvalidated_query(uuid=None):
    from debra.models import Influencer
    from admin import ADMIN_TABLE_INFLUENCER_INFORMATIONS,\
        ADMIN_TABLE_INFLUENCER_SELF_MODIFIED
    if uuid:
        query = Influencer.objects.filter(
            validation_queue__uuid=uuid, validation_queue__state=1).distinct()
    else:
        query = Influencer.objects.filter(
            accuracy_validated=True
        ).exclude(
            show_on_search=True
        )

    query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    query = query.exclude(validated_on__contains=ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)
    query = query.exclude(blacklisted=True)
    # these influencers will be in a separate table (at least in the beginning)
    query = query.exclude(blog_url__contains='theshelf.com')
    # quick fix to make sure QAs are working on real blogs
    # query = query.filter(blog_url__icontains='blogspot')
    #query = query.filter(classification='blog')
    return query


class QABloggersQueryBuilder(object):

    def __init__(self, user_profile, base_query=None, qa_group=None,
            exclude_validated=True):
        self._base_query = Influencer.objects.none() if base_query is None else base_query
        self.user_profile = user_profile
        self.qa_group = qa_group or Group.objects.get(name='QA')
        self.exclude_validated = exclude_validated

    @cached_property
    def base_query(self):
        return self._base_query

    @cached_property
    def allocated_bloggers(self):
        infs = self.user_profile.influencers_for_check.all()
        infs = infs.filter(id__in=list(self.base_query.values_list('id', flat=True)))
        infs = infs.exclude(
            validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED
        )
        if self.exclude_validated:
            infs = infs.exclude(
                validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS
            )
        return infs

    @cached_property
    def free_bloggers(self):
        return self.base_query.filter(qa_user_profile__isnull=True)

    def _build_qa_query(self):
        missing_amount = UserProfile.QA_INFLUENCERS_TO_CHECK_NUMBER\
            - self.allocated_bloggers.count()
        if missing_amount > 0:
            if self.base_query is None:
                query = self.allocated_bloggers
            else:
                query = self.allocated_bloggers | self.free_bloggers
            ids = query.values_list('id',
                flat=True)[:UserProfile.QA_INFLUENCERS_TO_CHECK_NUMBER]
            result_query = Influencer.objects.filter(id__in=ids)
        else:
            result_query = self.allocated_bloggers
        return result_query

    def _build_non_qa_query(self):
        return self.base_query

    def build_query(self):
        print '* building a query for {}'.format(self.user_profile.user)
        if self.qa_group and self.user_profile.user in self.qa_group.user_set.all():
            print '** {} is in the QA group'.format(self.user_profile.user)
            res = self._build_qa_query()
            res.update(qa_user_profile=self.user_profile)
        else:
            print '** {} is not in the QA group'.format(self.user_profile.user)
            res = self._build_non_qa_query()
        return res.order_by('id')


class NonvalidatedBloggersQueryBuilder(QABloggersQueryBuilder):

    @cached_property
    def new_qa_team_work_start_date(self):
        return datetime.date(2016, 6, 12)

    @cached_property
    def base_query(self):
        dd = datetime.date(2016, 6, 12)
        coll = InfluencersGroup.objects.get(id=1964)
        ids = coll.influencer_ids
        coll2 = InfluencersGroup.objects.get(id=1995)
        ids2 = coll2.influencer_ids
        ids.extend(ids2)
        query = Influencer.objects.filter(
            id__in=ids
        ).exclude(date_validated__gte=self.new_qa_team_work_start_date)#.exclude(blog_url__contains='http://www.theshelf.com/artificial_blog')
        query = query.filter(profile_pic_url__isnull=False)
        return query

    @cached_property
    def allocated_bloggers(self):
        infs = super(NonvalidatedBloggersQueryBuilder, self).allocated_bloggers
        infs = infs.exclude(date_validated__gte=self.new_qa_team_work_start_date)
        return infs
