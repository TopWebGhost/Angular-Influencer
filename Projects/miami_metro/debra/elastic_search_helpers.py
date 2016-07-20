from copy import deepcopy
import json
import itertools
import collections
from datetime import datetime, timedelta
import logging
import operator
import requests
import time
from requests.exceptions import ConnectionError
import us
from django.db.models import Q
from debra.constants import ELASTICSEARCH_URL, ELASTICSEARCH_INDEX, ELASTICSEARCH_TAGS_INDEX, ELASTICSEARCH_TAGS_TYPE
from django.conf import settings
import xpathscraper
from xpathscraper.utils import domain_from_url
from debra import clickmeter
import re

from debra.es_requests import make_es_get_request, make_es_delete_request, make_es_post_request


clickmeter_api = clickmeter.ClickMeterApi()


# This value determines the minimum amount of posts with required categories which should return
# as a result in from ES query. If an influencer has lesser posts of required category than this value,
# then this influencer is ignored.
MINIMUM_POST_CATEGORIES = 6
# OR = 1
# AND = 2


# Helper functions for getting ES subqueries/filters
def term_query_string(field, value):
    return {
        "query_string": {
            "query": "%s:*%s*" % (field, value),
        }
    }


def term_match(field, value):
    return {
        "match": {
            field: value
        }
    }


def term_match_phrase(field, value):
    return {
        "match_phrase": {
            field: value
        }
    }


def term_wildcard(field, value):
    return {
        "wildcard": {
            field: value
        }
    }


def term_term(field, value):
    return {
        "term": {
            field: value
        }
    }


def term_terms(field, value):
    return {
        "terms": {
            field: value
        }
    }


def term_range(field, range_min, range_max):
    term = {
        "range": {
            field: {
            }
        }
    }
    if range_min is not None:
        term["range"][field]["gte"] = range_min
    if range_max is not None:
        term["range"][field]["lte"] = range_max
    return term


def term_multimatch(fields, query, type=None):
    term = {
        "multi_match": {
            "fields": fields,
            "query": query
        }
    }
    term["multi_match"]["type"] = "phrase"
    return term

def range_filter(values):
    ''' range_filter returns a range query object. '''
    if 'field' in values:
        over = {}

        if 'min' in values:
            over['gte'] = values['min']
        if 'max' in values:
            over['lte'] = values['max']

        return {
            'range': {
                values['field']: over
            }
        }
    return None

def expand_location(location):
    ''' expand_location expands a location to include states and territories. '''
    return {
        'usa': ['usa'] + [state.name for state in us.STATES_AND_TERRITORIES]
    }.get(location.lower(), [location])

def expand_locations(locations):
    ''' expand_locations expands all locations in locations. '''
    locs = []

    for location in locations:
        locs.extend(expand_location(location))

    return locs

def _transform_filter(key, options):
    data = options[key]
    del options[key]
    return data


def escape_for_query_string(query_str):
    """
    This function escapes special characters in query string to be used with query_string query of Elasticsearch.
    :param query_str: query string
    :return: escaped query string
    """
    query_string_reserved_characters = ['\\',
                                        ' ', '+', '-', '=', '&&', '||', '>', '<', '!', '(', ')',
                                        '{', '}', '[', ']', '^', '"', '~', '*', '?', ':', '/'
                                        ]

    query_str = ''.join(['\\%s' % c if c in query_string_reserved_characters else c for c in query_str])
    return query_str

# TODO: if obsolete - remove it
def social_platform_subquery(data_dict, value_type):
    """
    This is a helper function to search over Influencer's nested Platforms in ES index
    by ranges for social, likes, shares, numcomments
    :param data_dict: dict like {'value': 'Instagram', 'range_min': 10, 'range_max': 1000}
    :param value_type: in range: ['social', 'likes', 'shares', 'comments']
    :return:
    """
    # adding LIKES search clause
    subquery = {
        "nested": {
            "query": {
                "bool": {
                    "must": [
                    ]
                }
            },
            "path": "social_platforms"
        }
    }

    if data_dict is not None:
        value = data_dict.get('value')
        if value is not None:
            subquery['nested']['query']['bool']['must'].append(
                term_term("social_platforms.name", value if value_type == 'social' else "%s_%s" % (value, value_type))
            )
        range_min = data_dict.get('range_min')
        range_max = data_dict.get('range_max')
        if range_min or range_max:
            subquery['nested']['query']['bool']['must'].append(
                term_range('social_platforms.num_followers',
                           range_min,
                           range_max)
            )

    return subquery

is_correct_domain_pattern = re.compile(
    "^[a-zA-Z0-9][a-zA-Z0-9-_]{0,61}[a-zA-Z0-9]{0,1}\.([a-zA-Z]{1,6}|[a-zA-Z0-9-]{1,30}\.[a-zA-Z]{2,3})$"
)
def is_correct_domain(domain=None):
    """
    Checks if the given domain is correctly formed.
    :param domain:
    :return:
    """
    if domain is None:
        return False
    else:
        return True if is_correct_domain_pattern.match(domain) else False


def es_influencer_query_builder_v3(parameters, page_size=20, page=0, source=False, brand=None):
    """
    Builds a json for influencers ES query by parameters, page and page_size
    :param parameters: dict of parameters for search query of ES
    :param page: desired page number of results
    :param page_size: quantity of results per page
    :param brand: the brand who is running this request
    :return: ES query json
    """
    assert brand is not None
    print("Brand %r" % brand)
    brand_id = brand.id
    max_influencers_size = (page+1)* 60

    print ('page %d max_influencers = %d' % (page, max_influencers_size))

    from debra.models import ActivityLevel

    # no tags are set into query
    has_tags = bool(parameters.get('filters', {}).get('tags', None))
    keywords = parameters.get('keyword')
    query = {

        "size": 0,

        "query": {
            "filtered": {
                "filter": get_query_filter_v2(
                    settings.DEBUG,
                    # If specific influencer_ids provided, then show them even if they are blacklisted
                    exclude_blacklisted=('influencer_ids' not in parameters),
                    has_tags=has_tags
                ),
                "query": {
                    "bool": {
                        "minimum_should_match": 1,
                        "must_not": [],
                        "should": [],
                        "must": []
                    }
                }
            }
        },
        "aggs": {
            "influencer_wise": {
                "terms": {
                    "field": "influencer.id",
                    "size": max_influencers_size,
                },
                "aggs": {
                    "inf_data": {
                        "top_hits": {
                            "size": 1,
                            "_source": [
                                "influencer.id",
                                "influencer.name",
                                "influencer.blog_name",
                                "influencer.social_platforms.profile_pic",
                                "influencer.social_platforms.cover_pic",
                                "influencer.avg_numcomments_overall",
                                "influencer.location",
                                "influencer.popularity",
                                "influencer.score_engagement_overall",
                                "influencer.tags",

                                "influencer.social_platforms.bloglovin.num_followers",
                                "influencer.social_platforms.blogspot.num_followers",
                                "influencer.social_platforms.facebook.num_followers",
                                "influencer.social_platforms.gplus.num_followers",
                                "influencer.social_platforms.instagram.num_followers",
                                "influencer.social_platforms.pinterest.num_followers",
                                "influencer.social_platforms.squarespace.num_followers",
                                "influencer.social_platforms.tumblr.num_followers",
                                "influencer.social_platforms.wordpress.num_followers",
                                "influencer.social_platforms.youtube.num_followers",
                                "influencer.social_platforms.distibutions.dist_age_0_19",
                                "influencer.social_platforms.distibutions.dist_age_20_24",
                                "influencer.social_platforms.distibutions.dist_age_25_29",
                                "influencer.social_platforms.distibutions.dist_age_30_34",
                                "influencer.social_platforms.distibutions.dist_age_35_39",
                                "influencer.social_platforms.distibutions.dist_age_40",


                                "influencer.blog_url",
                                "influencer.categories",
                                "influencer.custom_brand_data.%s.ethnicity" % brand_id,
                                "influencer.custom_brand_data.%s.cell_phone" % brand_id,
                                "influencer.custom_brand_data.%s.representation" % brand_id,
                                "influencer.custom_brand_data.%s.rep_email_address" % brand_id,
                                "influencer.custom_brand_data.%s.rep_phone" % brand_id,
                                "influencer.custom_brand_data.%s.language" % brand_id,
                                "influencer.custom_brand_data.%s.zip_code" % brand_id,
                                "influencer.custom_brand_data.%s.mailing_address" % brand_id,
                                "influencer.custom_brand_data.%s.categories" % brand_id,
                                "influencer.custom_brand_data.%s.occupation"% brand_id,
                                "influencer.custom_brand_data.%s.tags" % brand_id,
                                "influencer.custom_brand_data.%s.notes" % brand_id,
                                "influencer.custom_brand_data.%s.date_of_birth" % brand_id,

                                # "influencer.social_platforms.youtube.num_impressions",
                                # "influencer.social_platforms.facebook.url",
                                # "influencer.social_platforms.facebook.url_not_found",
                                # "influencer.social_platforms.facebook.username",
                                # "influencer.social_platforms.instagram.url",
                                # "influencer.social_platforms.instagram.url_not_found",
                                # "influencer.social_platforms.instagram.username",
                                #
                                # "platform_id",
                            ]
                        }
                    }
                }
            },
            "total_unique_influencers": {
                "cardinality": {
                    "field": "influencer.id"
                }
            }
        }
    }
    print keywords
    if not keywords:
        print("OK GOING IN")
        query['aggs']['influencer_wise']['terms']['field'] = "influencer.popularity"
        query['aggs']['influencer_wise']['terms']['order'] = {"_term": "desc"}


    if source is not True:
        query['_source'] = {
            'exclude': [],
            'include': ['influencer.id']
        }
    else:
        #stripping those who has no profile_pic, no popularity, or if 'brands' in source.
        pass
        # query['query']['filtered']['query']['bool']['must_not'] = [
        #     term_wildcard("influencer.social_platforms.source", "*brands*"),
        # ]


    print(u'* PARAMETERS: %s' % parameters)

    # adding KEYWORD search clause
    # This concatenator defines logic INSIDE groups of keywords. Can be OR ('or') or AND ('and').
    concatenator = parameters.get('concatenator', 'or')  # concatenator defining AND or OR logic when searching

    # This concatenator defines logic BETWEEN groups of keywords of POSTS filters.
    # Can be OR ('or'), AND_SAME ('and_same'), AND_ACROSS ('and_across).
    # 'and_same' means that AT LEAST ONE of the keywords from each group should appear IN THE SAME post.
    # 'and_across' means that AT LEAST ONE of the keywords from each group should appear in AT LEAST SOME post.
    group_concatenator = parameters.get('group_concatenator', 'or')

    keywords = parameters.get('keyword')
    keyword_type = parameters.get('type', 'all')
    keyword_types = parameters.get('keyword_types', [])
    if not keyword_types and keywords:
        keyword_types = [keyword_type] * len(keywords)

    groups = parameters.get('groups', [])

    post_keywords = None

    no_keywords = True
    no_post_keywords = True

    if keywords:
        no_keywords = False
        field_keyword_types = ['brand', 'hashtag', 'mention', 'blogname', 'blogurl', 'name', 'content']
        and_or = all(kt not in field_keyword_types for kt in keyword_types)

        if parameters.get('and_or_filter_on') and and_or:
            # here we create a map of lists of tuples, instead of list of lists of lists
            post_keywords = collections.defaultdict(list)
            for keyword, keyword_type, group in zip(keywords, keyword_types, groups):
                post_keywords[group].append((keyword_type, keyword))
            print '* Post Keywords: ', post_keywords
        else:
            keyword_map = collections.defaultdict(list)
            # Possible keyword types:
            # [all, brand, hashtag, mention, blogname, blogurl, name]
            for keyword, keyword_type in zip(keywords, keyword_types):
                keyword_map[keyword_type].append(keyword)

            print('* Concatenator: %s' % concatenator)
            print('* Keyword map : %s' % keyword_map)

            # splitting that 'all' keywords into subfields to get AND concatenation working
            if 'all' in keyword_map:
                for kwt in field_keyword_types:
                    if kwt not in keyword_map:
                        keyword_map[kwt] = []

                for kw in keyword_map['all']:
                    keyword_map['name'].append(kw)
                    keyword_map['brand_all'].append(kw)
                    keyword_map['hashtag'].append(kw)
                    keyword_map['mention'].append(kw)
                    keyword_map['blogname'].append(kw)
                    keyword_map['blogurl_all'].append(kw)
                    keyword_map['content'].append(kw)

            expression = u''
            ctr = 0
            for key, value in keyword_map.items():
                if key != 'all':
                    if 0 < ctr < len(keyword_map):
                        expression += u' OR '
                    expression += u'('
                    expression += (u' AND ' if concatenator == 'and' else u' OR ').join([u"'%s'" % v for v in value])
                    expression += ' in %s)' % key
                    ctr += 1

            # import ipdb; ipdb.set_trace()

            #print u'Give me the influencers who has "{}"'.format(expression)
            import datetime as dddt
            keyword_subquery = {
                "bool": {
                    "minimum_should_match": 1,
                    "must": [
                        {
                            "range": {
                                "create_date": {
                                    "lte": "now",
                                    #"gte": dddt.date(2016, 8, 1).strftime("%Y-%m-%dT%H:%M:%S.000000"),
                                }
                            }
                        }
                    ],
                    "should": []
                }
            }

            # setting keyword conditions
            append = False
            for keyword_type, keywords in keyword_map.items():
                append = True
                if keyword_type == 'brand' or keyword_type == 'brand_all':

                    brand_names = []
                    brand_domains = []
                    for keyword in keywords:

                        # print('***BRAND: %s' % brand)
                        if keyword_type == 'brand_all':
                            brand_names.append(keyword)
                            if is_correct_domain(keyword):
                                brand_domains.append(keyword)
                        else:
                            brand = brand_from_keyword(keyword)
                            if brand is not None:
                                brand_names.append(brand.name)
                                if keyword_type == 'brand' or is_correct_domain(brand.domain_name):
                                    brand_domains.append(brand.domain_name)
                            else:
                                brand_names.append(keyword)
                                if is_correct_domain(keyword):
                                    brand_domains.append(keyword)

                    if len(brand_names) > 0:
                        keyword_subquery['bool']['should'].append(
                            {
                                "bool": {
                                    "must" if concatenator == 'and' else 'should': [
                                        term_multimatch(["brands", "product_names", "designer_names"],
                                                        brand_name) for brand_name in brand_names
                                    ]
                                }
                            }
                        )

                    if len(brand_domains) > 0:
                        keyword_subquery['bool']['should'].append(
                            {
                                "bool": {
                                    "must" if concatenator == 'and' else 'should': [
                                        term_multimatch(["brand_domains", "product_urls"],
                                                        brand_domain) for brand_domain in brand_domains
                                    ]
                                }
                            }
                        )

                elif keyword_type == 'hashtag':
                    keyword_subquery['bool']['should'].append(
                        {
                            "bool": {
                                "must" if concatenator == 'and' else 'should': [
                                    term_multimatch(["content_hashtags",
                                                     "title_hashtags"],
                                                    u"#%s" % keyword) for keyword in keywords
                                ]
                            }
                        }
                    )
                elif keyword_type == 'mention':
                    keyword_subquery['bool']['should'].append(
                        {
                            "bool": {
                                "must" if concatenator == 'and' else 'should': [
                                    term_multimatch(["content_mentions",
                                                     "title_mentions"],
                                                    u"@%s" % keyword) for keyword in keywords
                                ]
                            }
                        }
                    )
                elif keyword_type == 'blogname':
                    keyword_subquery['bool']['should'].append(
                        {
                            "bool": {
                                "must" if concatenator == 'and' else 'should': [
                                    {"match_phrase": {'influencer.blog_name': keyword}} for keyword in keywords
                                ]
                            }
                        }
                    )

                # TODO: 'c/meo' ==> 'c'
                elif keyword_type == 'blogurl' or keyword_type == 'blogurl_all':

                    nodes = []
                    for keyword in keywords:
                        # dependent on if the url is given with http:// / https:// or if there is only domain
                        # if keyword.startswith('http://') or keyword.startswith('https://'):
                        #     node = term_match_phrase("blog_url", keyword)
                        # else:
                        #     node = {
                        #         "query_string": {
                        #             "default_field": "blog_url",
                        #             "default_operator": "AND",
                        #             "query": "*%s*" % escape_for_query_string(keyword),
                        #             "analyze_wildcard": True
                        #         }
                        #     }

                        try:
                            keyword = xpathscraper.utils.domain_from_url(keyword)
                        except Exception as e:
                            pass

                        if keyword_type == 'blogurl' or is_correct_domain(keyword):

                            node = {
                                "bool": {
                                    "minimum_should_match": 1,
                                    "should": [
                                        {
                                            "wildcard": {
                                                "influencer.blog_url": "*%s*" % keyword
                                            }
                                        },
                                        {
                                            "match_phrase": {
                                                "influencer.blog_url": {
                                                    "query": "%s" % keyword,
                                                    "analyzer": "lowercase_by_folding"
                                                }
                                            }
                                        }
                                    ]
                                }
                            }

                            nodes.append(node)
                    if len(nodes) > 0:
                        keyword_subquery['bool']['should'].append(
                            {
                                "bool": {
                                    "must" if concatenator == 'and' else 'should': nodes
                                }
                            }
                        )

                elif keyword_type == 'name':
                    keyword_subquery['bool']['should'].append(
                        {
                            "bool": {
                                "must" if concatenator == 'and' else 'should': [
                                    {"match_phrase": {'influencer.name': keyword}} for keyword in keywords
                                ]
                            }
                        }
                    )

                elif keyword_type == 'content':
                    keyword_subquery['bool']['should'].append(
                        {
                            "bool": {
                                "must" if concatenator == 'and' else 'should': [
                                    # {"match_phrase": {'content': keyword}} for keyword in keywords
                                    term_multimatch(["title", "content"], keyword) for keyword in keywords
                                ]
                            }
                        }
                    )

            if append is True:
                query['query']['filtered']['query']['bool']['should'].append(keyword_subquery)

    # performing post_keywords filters
    if post_keywords is not None:
        group_nodes = []
        no_post_keywords = False
        for group in post_keywords.values():

            # nodes, of which does this group of conditions consists
            group_subnodes = []
            for kw_type, kw in group:

                if kw_type == 'post_content' or kw_type == 'all':
                    # group_subnodes.append(
                    #     term_match_phrase("content", kw)
                    # )

                    brand_name = kw
                    brand_domain = kw

                    brand = brand_from_keyword(kw)
                    if brand is not None:
                        brand_name = brand.name
                        brand_domain = brand.domain_name

                    group_subnote = {
                        "bool": {
                            "should": [
                                term_match_phrase("title", kw),
                                term_match_phrase("content", kw),
                                term_multimatch(["content_hashtags", "title_hashtags"], u"#%s" % kw),
                                term_multimatch(["content_mentions", "title_mentions"], u"@%s" % kw),
                                term_multimatch(["brands", "product_names", "designer_names"], brand_name),
                                # term_multimatch(["brand_domains", "product_urls"], brand_domain),
                            ],
                            "minimum_should_match": 1
                        }
                    }

                    if is_correct_domain(brand_domain):
                        group_subnote["bool"]["should"].append(
                            term_multimatch(["brand_domains", "product_urls"], brand_domain)
                        )

                    group_subnodes.append(group_subnote)

                elif kw_type == 'post_title':
                    group_subnodes.append(
                        term_match_phrase("title", kw)
                    )

                elif kw_type == 'post_hashtag':
                    group_subnodes.append(
                        term_multimatch(["content_hashtags", "title_hashtags"], u"#%s" % kw)
                    )

                elif kw_type == 'post_mention':
                    group_subnodes.append(
                        term_multimatch(["content_mentions", "title_mentions"], u"@%s" % kw)
                    )

            if len(group_subnodes) > 0:

                group_node = {
                    "bool": {
                        "must" if concatenator == 'and' else 'should': group_subnodes
                    }
                }
                group_nodes.append(group_node)

        if len(group_nodes) > 0:
            if group_concatenator == 'or':
                query['query']['filtered']['query']['bool']['should'].extend(group_nodes)

            elif group_concatenator == 'and_same':
                query['query']['filtered']['query']['bool']['must'].extend(group_nodes)

            elif group_concatenator == 'and_across':
                all_groups_node = [{
                    "constant_score": {
                        "query": {
                            "bool": {
                                "must": gn
                            }
                        },
                        "boost": 1.0
                    }
                } for gn in group_nodes]

                query['query']['filtered']['query']['bool']['must'].extend(all_groups_node)
    print("KEYWORDS: %r POST_KEYWORDS: %r" % (no_keywords, no_post_keywords))
    if no_post_keywords and no_keywords:
        # so we can just fetch one post for each influencer and it should be enough for finding influencers
        import datetime as dddt
        st = dddt.datetime.today()
        ed = st - dddt.timedelta(days=365)
        keyword_subquery = {
            "bool": {
                "minimum_should_match": 1,
                "must": [
                    {
                        "range": {
                            "create_date": {
                                "lte": "now",
                                "gte": ed.strftime("%Y-%m-%dT%H:%M:%S.000000"),
                            }
                        }
                    }
                ],
                "should": []
            }
        }
        query['query']['filtered']['query']['bool']['should'].append(keyword_subquery)

    # performing 'filters' element in parameters dict
    filters = parameters.get('filters')
    if filters:

        #adding TAGS search clause
        tags = filters.get('tags')
        if tags:
            inf_ids_in_tags = get_influencers_for_set_of_tags(None, tags)
            query['query']['filtered']['filter']['bool']['must'].append({
                "terms": {
                    "influencer.id": inf_ids_in_tags
                }
            })

        exclude_tags = filters.get('exclude_tags')
        if exclude_tags:
            inf_ids_in_tags = get_influencers_for_set_of_tags(None, exclude_tags)
            query['query']['filtered']['filter']['bool']['must_not'].append({
                "terms": {
                    "influencer.id": inf_ids_in_tags
                }
            })


        # this is for custom influencer fields
        custom_brand_categories = [w.lower() for w in filters.get('customCategories', [])]
        custom_brand_occupation = [w.lower() for w in filters.get('customOccupation', [])]
        custom_brand_ethnicity = [w.lower() for w in filters.get('customEthnicity', [])]
        custom_brand_tags = [w.lower() for w in filters.get('customTags', [])]
        custom_brand_age = filters.get('customAge')

        custom_brand_sex = [w.lower() for w in filters.get('customSex', [])]
        custom_brand_language = [w.lower() for w in filters.get('customLanguage', [])]


        if custom_brand_categories:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.categories" % brand_id, custom_brand_categories))
        if custom_brand_occupation:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.occupation" % brand_id, custom_brand_occupation))
        if custom_brand_ethnicity:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.ethnicity" % brand_id, custom_brand_ethnicity))
        if custom_brand_tags:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.tags" % brand_id, custom_brand_tags))
        if custom_brand_age:
            custom_brand_age_min = custom_brand_age.get('range_min')
            custom_brand_age_max = custom_brand_age.get('range_max')
            query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.custom_brand_data.%s.age' % brand_id, custom_brand_age_min, custom_brand_age_max)
            )

        # @TODO: ATUL, WHAT ABOUT THOSE?
        if custom_brand_sex:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.sex" % brand_id, custom_brand_sex))
        if custom_brand_language:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.language" % brand_id, custom_brand_language))

        # adding CATEGORIES search clause
        categories = filters.get('categories')
        if categories:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.categories", categories))

        # adding GENDER search clause
        # gender consists of list with parameters: ['Female', 'Male'], index needs lowercase first letter
        gender = filters.get('gender')
        if gender:
            query['query']['filtered']['query']['bool']['must'].append(
                term_terms("influencer.gender", [g[:1].lower() for g in gender if len(g) > 1])
            )

        # adding SOCIAL search clause
        social = filters.get('social')
        if social:
            social_value = social.get('value')
            range_min = social.get('range_min')
            range_max = social.get('range_max')

            if social_value is not None:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.num_followers' % social_value.lower(), range_min, range_max)
                )

        # adding LIKES search clause
        likes = filters.get('likes')
        if likes:
            social_value = likes.get('value')
            range_min = likes.get('range_min')
            range_max = likes.get('range_max')

            if social_value is not None:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.like_count' % social_value.lower(), range_min, range_max)
                )

        # adding SHARES search clause
        shares = filters.get('shares')
        if shares:
            social_value = shares.get('value')
            range_min = shares.get('range_min')
            range_max = shares.get('range_max')

            if social_value is not None:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.share_count' % social_value.lower(), range_min, range_max)
                )

        # adding COMMENTS search clause
        comments = filters.get('comments')
        if comments:
            social_value = comments.get('value')
            range_min = comments.get('range_min')
            range_max = comments.get('range_max')

            if social_value is not None:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.comment_count' % social_value.lower(), range_min, range_max)
                )

        # adding SOURCE search clause
        source = filters.get('source')
        if source:
            for s in source:
                if s is not None and len(s) > 0:
                    query['query']['filtered']['query']['bool']['must'].append(
                        term_wildcard("influencer.social_platforms.source", "*%s*" % s)
                    )

        # adding BRAND_EMAILED search clause
        brand_emailed = filters.get('brand_emailed')
        if brand_emailed:
            query['query']['filtered']['query']['bool']['must'].append(
                term_terms("influencer.social_platforms.brand_emailed", brand_emailed),
            )

        # Adding ACTIVITY search clause
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        activity = filters.get('activity')
        if activity:

            platform = activity.get('platform')
            if platform.lower() == 'blog':
                platform = ["Blogspot", "Wordpress", "Custom", "Tumblr", "Squarespace"]
            else:
                platform = [platform, ]

            activity_level = activity.get('activity_level')
            if hasattr(ActivityLevel, activity_level):
                activity_level = ActivityLevel._ENUM[activity_level]

            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            term_range("influencer.social_platforms.%s.activity_level" % plat.lower(), 0, activity_level) for plat in platform
                        ]
                    }
                }
            )

        # adding AGE DISTRIBUTION filter
        distr_age = filters.get('avgAge')
        if distr_age:
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter(
                                {
                                    'field': 'influencer.social_platforms.distibutions.dist_age_%s' % group_name,
                                    'min': 25
                                }
                            ) for group_name in distr_age if group_name in ('0_19', '20_24', '25_29',
                                                                            '30_34', '35_39', '40')
                        ]
                    }
                }
            )

        # adding TRAFFIC PER MONTH filter
        traffic_per_month = filters.get('traffic_per_month')
        if traffic_per_month:

            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            term_range("influencer.social_platforms.%s.traffic_per_month" % plat.lower(), 0, traffic_per_month) for plat in platform
                        ]
                    }
                }
            )

        # adding ALEXA RANK filter
        alexa_rank = filters.get('alexa_rank')
        if alexa_rank:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.alexa_rank" % plat.lower(),
                                          'min': alexa_rank}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC SEARCH filter
        traffic_search = filters.get('traffic_search')
        if traffic_search:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_search" % plat.lower(),
                                          'min': traffic_search}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC DIRECT filter
        traffic_direct = filters.get('traffic_direct')
        if traffic_direct:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_direct" % plat.lower(),
                                          'min': traffic_direct}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC SOCIAL filter
        traffic_social = filters.get('traffic_social')
        if traffic_social:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_social" % plat.lower(),
                                          'min': traffic_social}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC REFERRAL filter
        traffic_referral = filters.get('traffic_referral')
        if traffic_referral:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_referral" % plat.lower(),
                                          'min': traffic_referral}) for plat in platform
                        ]
                    }
                }
            )

        # adding MOZ DOMAIN AUTHORITY filter
        moz_domain_authority = filters.get('moz_domain_authority')
        if moz_domain_authority:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            # TODO: Blogspot_moz_domain_authority
                            range_filter({'field': "influencer.social_platforms.%s.Blogspot_moz_domain_authority" % plat.lower(),
                                          'min': moz_domain_authority}) for plat in platform
                        ]
                    }
                }
            )

        # adding MOZ EXTERNAL LINKS filter
        moz_external_links = filters.get('moz_external_links')
        if moz_external_links:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            # TODO: Blogspot_moz_external_links
                            range_filter({'field': "influencer.social_platforms.%s.Blogspot_moz_external_links" % plat.lower(),
                                          'min': moz_external_links}) for plat in platform
                        ]
                    }
                }
            )

        # ENGAGEMENT
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        engagement = filters.get('engagement')
        if engagement:
            range_min = engagement.get('range_min')
            range_max = engagement.get('range_max')
            if range_min or range_max:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.avg_numcomments_overall', range_min, range_max)
                )

        # adding LOCATION search clause
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        location = filters.get('location')
        if location and len(location) > 0:
            # locations = expand_locations(location)
            query['query']['filtered']['query']['bool']['must'].append(
                # term_terms('location', [l.lower() for l in locations])
                {
                    "query_string": {
                        "default_field": "influencer.location",
                        "query": " OR ".join(["\"%s\"" % loc for loc in location])
                    }
                }
            )

        # adding PRICERANGES search clause
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        price_ranges = filters.get('priceranges')
        if price_ranges and len(price_ranges) > 0:
            prices_dict = {
                "Cheap": "cheap",
                "Mid-level": "middle",
                "Expensive": "expensive"
            }
            prices_values = []

            for price in price_ranges:
                prices_values.append(prices_dict.get(price, price))

            if prices_values:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_terms('influencer.price_range', prices_values)
                )

        # adding posts time range search clause
        time_range = filters.get('time_range')
        if time_range:
            try:
                from_date_str = time_range.get('from', "").split('T')[0]
                if from_date_str:
                    from_date = datetime.strptime(from_date_str, "%Y-%m-%d")\
                        .replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=4)
                    from_date_str = from_date.strftime("%Y-%m-%dT%H:%M:%S.000000")

                to_date_str = time_range.get('to', "").split('T')[0]
                if to_date_str:
                    to_date = datetime.strptime(to_date_str, "%Y-%m-%d")\
                        .replace(hour=23, minute=59, second=59, microsecond=999) + timedelta(hours=4)
                    to_date_str = to_date.strftime("%Y-%m-%dT%H:%M:%S.999999")

                query['query']['filtered']['query']['filter']['must'].append(
                    term_range("create_date", from_date_str, to_date_str)
                )
            except TypeError:
                pass

        # adding POPULARITY search clause
        popularity = filters.get('popularity')
        if isinstance(popularity, list) and 0 < len(popularity) < 3:
            from debra.search_helpers import get_popularity_filter
            from debra.models import Influencer
            ranges = []
            for p in popularity:
                treshold = get_popularity_filter(
                    p,
                    Influencer.objects.filter(show_on_search=True).exclude(blacklisted=True)
                )
                if treshold is not None:
                    ranges.append(term_range('influencer.popularity', treshold.get('min', None), treshold.get('max', None)))

                query['query']['filtered']['query']['bool']['must'].append(
                    {
                        "bool": {
                            "should": ranges
                        }
                    }
                )

        # only having platforms PLATFORM filtering
        post_platforms = filters.get('post_platform', [])

        if isinstance(post_platforms, list) and len(post_platforms) > 0:
            query['query']['filtered']['filter']['bool']['must'].append({
                "terms": {
                    "platform_name": post_platforms
                }
            })

    query["sort"] = [
            {
                "influencer.popularity": {
                    "order": "desc"
                }
            }
        ]

    # used for main search form, excludes influencers with artificial blog urls
    # no_artificial_blogs = parameters.get('no_artificial_blogs', False)
    # if has_tags is not True and no_artificial_blogs:
    #     query['query']['filtered']['query']['bool']['must_not'].append(
    #         {
    #             "query_string": {
    #                 "analyze_wildcard": True,
    #                 "default_field": "influencer.blog_url",
    #                 "default_operator": "AND",
    #                 "query": "*theshelf.com\\/artificial*"
    #             }
    #         }
    #     )

    # clean unused nodes
    bool_node = query['query']['filtered']['query']['bool']
    if len(bool_node['must']) == 0:
        bool_node.pop('must')
    if len(bool_node['should']) == 0:
        bool_node.pop('should')
        bool_node.pop('minimum_should_match')
    if len(bool_node['must_not']) == 0:
        bool_node.pop('must_not')

    if len(bool_node) == 0:
        query['query']['filtered']['query'].pop('bool')
        query['query']['filtered']['query'] = {
            "match_all": {}
        }

    return query



def es_post_query_builder_v3(parameters, page=0, page_size=50, highlighted_first=False, brand=None):
    """
    Builds a json for posts ES query by parameters, page and page_size. (using nested fields)
    Flattened model is used.

    If we seek posts only for designated influencers, list of their ids should be passed as "direct_influencers_ids"
    list in parameters.

    :param parameters: dict of parameters for search query of ES
    :param page: desired page number of results
    :param page_size: quantity of results per page
    :param highlighted_first: flag indicating that highlighted posts by keywords must go first in result
    :return: ES query json
    """

    from debra.models import ActivityLevel

    print(u'* PARAMETERS: %s' % parameters)
    brand_id = brand.id if brand else None

    # We want to show default posts (i.e., without any queries applied). Then, Pavel will implement a new button
    # that will allow the users to click on to see relevant posts.
    default_posts_only = parameters.get('default_posts', None)
    influencer_ids = parameters.get('influencer_ids', None)

    # no tags are set into query
    has_tags = bool(parameters.get('filters', {}).get('tags', None))

    try:
        page = int(page)
    except TypeError:
        page = 0

    if default_posts_only is not None and influencer_ids is not None:

        query = {
            "_source": [
                "create_date"
            ],

            "from": page*page_size,
            "size": page_size,

            "sort": [
                {
                    "create_date": {
                        "order": "desc"
                    }
                }
            ],

            "query": {
                "filtered": {
                    "filter": {
                        "bool": {
                            "must": [
                                {
                                    "terms": {
                                        "influencer.id": influencer_ids
                                    }
                                }
                            ]
                        }
                    },
                    "query": {
                        "bool": {
                            "minimum_should_match": 1,
                            "must_not": [
                                # TODO: skipping generic posts
                                # {
                                #     "query_string": {
                                #         "analyze_wildcard": True,
                                #         "default_field": "influencer.blog_url",
                                #         "default_operator": "AND",
                                #         "query": "*theshelf.com\\/artificial*"
                                #     }
                                # }
                            ],
                            "should": [],
                            "must": []
                        }
                        # commenting this out for now
                        #"match_all": {}
                    }
                }
            }

        }

        if default_posts_only == "about":
            query["query"]["filtered"]["filter"]["bool"]["must"].append({
                "terms": {
                    "platform_name": [
                        "Blogspot",
                        "Wordpress",
                        "Custom",
                        "Tumblr",
                        "Squarespace",
                        "Youtube",
                        "Instagram",
                        "Facebook",
                        "Pinterest",
                    ]
                }
            })
        elif default_posts_only == "about_all":
            query["query"]["filtered"]["filter"]["bool"]["must"].append({
                "terms": {
                    "platform_name": [
                        "Blogspot",
                        "Wordpress",
                        "Custom",
                        "Tumblr",
                        "Squarespace",
                        "Instagram",
                        "Facebook",
                        "Pinterest",
                        "Twitter",
                        "Youtube",
                    ]
                }
            })
        elif default_posts_only == "about_insta":
            query["query"]["filtered"]["filter"]["bool"]["must"].append({
                "terms": {
                    "platform_name": [
                        "Instagram",
                    ]
                }
            })
            # query["query"]["filtered"]["filter"]["bool"]["must"].append({
            #     "range": {
            #         "create_date": {
            #             "lte": "now"
            #         }
            #     }
            # })
        elif default_posts_only == "about_pins":
            query["query"]["filtered"]["filter"]["bool"]["must"].append({
                "terms": {
                    "platform_name": [
                        "Pinterest",
                    ]
                }
            })
        elif default_posts_only == "about_tweets":
            query["query"]["filtered"]["filter"]["bool"]["must"].append({
                "terms": {
                    "platform_name": [
                        "Twitter",
                    ]
                }
            })
        elif default_posts_only == "about_facebook":
            query["query"]["filtered"]["filter"]["bool"]["must"].append({
                "terms": {
                    "platform_name": [
                        "Facebook",
                    ]
                }
            })
        elif default_posts_only == "about_youtube":
            query["query"]["filtered"]["filter"]["bool"]["must"].append({
                "terms": {
                    "platform_name": [
                        "Youtube",
                    ]
                }
            })
        elif default_posts_only == "profile":
            query["query"]["filtered"]["filter"]["bool"]["must"].append({
                "terms": {
                    "platform_name": [
                        "Blogspot",
                        "Wordpress",
                        "Custom",
                        "Tumblr",
                        "Squarespace",
                        "Instagram",
                        "Facebook",
                    ]
                }
            })

        #return query
    else:
        query = {
            "_source": [
                "influencer.id"
            ],

            "from": page*page_size,
            "size": page_size,

            "sort": [
                {
                    "create_date": {
                        "order": "desc"
                    }
                }
            ],

            "query": {
                "filtered": {
                    "filter": get_query_filter_v2(
                        settings.DEBUG,
                        # If specific influencer_ids provided, then show them even if they are blacklisted
                        exclude_blacklisted=('influencer_ids' not in parameters),
                        has_tags=has_tags
                    ),
                    "query": {
                        "bool": {
                            "minimum_should_match": 1,
                            "must_not": [
                                # # TODO: skipping generic posts
                                # {
                                #     "query_string": {
                                #         "analyze_wildcard": True,
                                #         "default_field": "influencer.blog_url",
                                #         "default_operator": "AND",
                                #         "query": "*theshelf.com\\/artificial*"
                                #     }
                                # }
                            ],
                            "should": [],
                            "must": []
                        }
                    }
                }
            }

        }

    if default_posts_only is not True:
        # Highlighting here is used for finding out highlighted posts fo user's profile
        query["highlight"] = {
            "fields": {
                "content": {"number_of_fragments": 1, "fragment_size": 1},
                "brands": {"number_of_fragments": 1, "fragment_size": 1},
                "content_hashtags": {"number_of_fragments": 1, "fragment_size": 1},
                "title_hashtags": {"number_of_fragments": 1, "fragment_size": 1},
                "content_mentions": {"number_of_fragments": 1, "fragment_size": 1},
                "title_mentions": {"number_of_fragments": 1, "fragment_size": 1}
            }
        }

    # Adding should clause with match_all to get all posts if we need highlighted first
    # if default_posts_only is not True and highlighted_first:
    #     query['query']['filtered']['query']['bool']['should'].append(
    #         {
    #             # this should clause will give remaining results of user's posts
    #             "constant_score": {
    #                 "query": {
    #                     "match_all": {}
    #                 },
    #                 "boost": 1.0
    #             }
    #         }
    #     )

    # adding direct influencers if any
    influencer_ids = parameters.get('influencer_ids', None)
    if influencer_ids:
        query['query']['filtered']['filter']['bool']['must'].append(
            {
                "terms": {
                    "influencer.id": influencer_ids
                }
            }
        )

    # adding KEYWORD search clause
    # This concatenator defines logic INSIDE groups of keywords. Can be OR ('or') or AND ('and').
    concatenator = parameters.get('concatenator', 'or')  # concatenator defining AND or OR logic when searching

    # This concatenator defines logic BETWEEN groups of keywords of POSTS filters.
    # Can be OR ('or'), AND_SAME ('and_same'), AND_ACROSS ('and_across).
    # 'and_same' means that AT LEAST ONE of the keywords from each group should appear IN THE SAME post.
    # 'and_across' means that AT LEAST ONE of the keywords from each group should appear in AT LEAST SOME post.
    group_concatenator = parameters.get('group_concatenator', 'or')

    keywords = parameters.get('keyword')
    keyword_type = parameters.get('type', 'all')
    keyword_types = parameters.get('keyword_types', [])

    if not keyword_types and keywords:
        keyword_types = [keyword_type] * len(keywords)

    groups = parameters.get('groups', [])

    post_keywords = None

    #if default_posts_only is not True and keywords:
    if keywords:
        field_keyword_types = ['brand', 'hashtag', 'mention', 'name', 'content']
        and_or = all(kt not in field_keyword_types for kt in keyword_types)

        if parameters.get('and_or_filter_on') and and_or:
            # here we create a map of lists of tuples, instead of list of lists of lists
            post_keywords = collections.defaultdict(list)
            for keyword, keyword_type, group in zip(keywords, keyword_types, groups):
                post_keywords[group].append((keyword_type, keyword))
            print '* Post Keywords: ', post_keywords
        else:
            keyword_map = collections.defaultdict(list)
            # Possible keyword types:
            field_keyword_types = ['brand', 'hashtag', 'mention', 'name', 'content']

            for keyword, keyword_type in zip(keywords, keyword_types):
                if keyword_type in field_keyword_types or keyword_type == 'all':
                    keyword_map[keyword_type].append(keyword)

            print('* Concatenator: %s' % concatenator)
            print('* Keyword map : %s' % keyword_map)

            # splitting that 'all' keywords into subfields to get AND concatenation working
            if 'all' in keyword_map:
                for kwt in field_keyword_types:
                    if kwt not in keyword_map:
                        keyword_map[kwt] = []

                for kw in keyword_map['all']:
                    keyword_map['name'].append(kw)
                    keyword_map['brand_all'].append(kw)
                    keyword_map['hashtag'].append(kw)
                    keyword_map['mention'].append(kw)
                    keyword_map['content'].append(kw)

            expression = u''
            ctr = 0
            for key, value in keyword_map.items():
                if key != 'all':
                    if 0 < ctr < len(keyword_map):
                        expression += ' OR '
                    expression += '('
                    expression += (' AND ' if concatenator == 'and' else ' OR ').join(["'%s'" % v for v in value])
                    expression += ' in %s)' % key
                    ctr += 1

            # print u'Give me the influencers who has "{}"'.format(expression)

            keyword_subquery = {
                "bool": {
                    "minimum_should_match": 1,
                    "must": [
                        {
                            "range": {
                                "create_date": {
                                    "lte": "now"
                                }
                            }
                        }
                    ],
                    "should": []
                }
            }

            # setting keyword conditions
            append = False
            for keyword_type, keywords in keyword_map.items():
                append = True
                if keyword_type == 'brand' or keyword_type == 'brand_all':

                    brand_names = []
                    brand_domains = []
                    for keyword in keywords:
                        if keyword_type == 'brand_all':
                            brand_names.append(keyword)
                            if is_correct_domain(keyword):
                                brand_domains.append(keyword)
                        else:
                            brand = brand_from_keyword(keyword)
                            if brand is not None:
                                brand_names.append(brand.name)
                                if keyword_type == 'brand':
                                    brand_domains.append(brand.domain_name)
                            else:
                                brand_names.append(keyword)
                                # if is_correct_domain(brand.domain_name):
                                #     brand_domains.append(keyword)

                    if len(brand_names) > 0:
                        keyword_subquery['bool']['should'].append(
                            {
                                "bool": {
                                    "must" if concatenator == 'and' else 'should': [
                                        term_multimatch(["brands", "product_names", "designer_names"],
                                                        brand_name) for brand_name in brand_names
                                    ]
                                }
                            }
                        )

                    if len(brand_domains) > 0:
                        keyword_subquery['bool']['should'].append(
                            {
                                "bool": {
                                    "must" if concatenator == 'and' else 'should': [
                                        term_multimatch(["brand_domains", "product_urls"],
                                                        brand_domain) for brand_domain in brand_domains
                                    ]
                                }
                            }
                        )

                elif keyword_type == 'hashtag':
                    keyword_subquery['bool']['should'].append(
                        {
                            "bool": {
                                "must" if concatenator == 'and' else 'should': [
                                    term_multimatch(["content_hashtags",
                                                     "title_hashtags"],
                                                    u"#%s" % keyword) for keyword in keywords
                                ]
                            }
                        }
                    )
                elif keyword_type == 'mention':
                    keyword_subquery['bool']['should'].append(
                        {
                            "bool": {
                                "must" if concatenator == 'and' else 'should': [
                                    term_multimatch(["content_mentions",
                                                     "title_mentions"],
                                                    u"@%s" % keyword) for keyword in keywords
                                ]
                            }
                        }
                    )
                # elif keyword_type == 'name':
                #     keyword_subquery['bool']['should'].append(
                #         {
                #             "bool": {
                #                 "must" if concatenator == 'and' else 'should': [
                #                     term_multimatch(["product_names", "designer_names"], keyword) for keyword in keywords
                #                 ]
                #             }
                #         }
                #     )
                elif keyword_type == 'content':
                    keyword_subquery['bool']['should'].append(
                        {
                            "bool": {
                                "must" if concatenator == 'and' else 'should': [
                                    # {"match_phrase": {'content': keyword}} for keyword in keywords
                                    term_multimatch(["title", "content"], keyword) for keyword in keywords
                                ]
                            }
                        }
                    )

            if append is True:
                query['query']['filtered']['query']['bool']['should'].append(keyword_subquery)

    # performing post_keywords filters
    if post_keywords is not None:

        group_nodes = []
        for group in post_keywords.values():

            # nodes, of which does this group of conditions consists
            group_subnodes = []
            for kw_type, kw in group:

                if kw_type == 'post_content' or kw_type == 'all':

                    brand_name = kw
                    brand_domain = kw

                    if kw_type == 'post_content':
                        brand = brand_from_keyword(kw)
                        if brand is not None:
                            brand_name = brand.name
                            brand_domain = brand.domain_name

                    group_subnote = {
                        "bool": {
                            "should": [
                                term_match_phrase("title", kw),
                                term_match_phrase("content", kw),
                                term_multimatch(["content_hashtags", "title_hashtags"], u"#%s" % kw),
                                term_multimatch(["content_mentions", "title_mentions"], u"@%s" % kw),
                                term_multimatch(["brands", "product_names", "designer_names"], brand_name),
                                # term_multimatch(["brand_domains", "product_urls"], brand_domain),
                            ],
                            "minimum_should_match": 1
                        }
                    }

                    if is_correct_domain(brand_domain):
                        group_subnote["bool"]["should"].append(
                            term_multimatch(["brand_domains", "product_urls"], brand_domain)
                        )

                    group_subnodes.append(group_subnote)

                elif kw_type == 'post_title':
                    group_subnodes.append(
                        term_match_phrase("title", kw)
                    )

                elif kw_type == 'post_hashtag':
                    group_subnodes.append(
                        term_multimatch(["content_hashtags", "title_hashtags"], u"#%s" % kw)
                    )

                elif kw_type == 'post_mention':
                    group_subnodes.append(
                        term_multimatch(["content_mentions", "title_mentions"], u"@%s" % kw)
                    )

            if len(group_subnodes) > 0:

                group_node = {
                    "bool": {
                        "must" if concatenator == 'and' else 'should': group_subnodes
                    }
                }
                group_nodes.append(group_node)

        print('GROUP NODES: %s' % group_nodes)

        if len(group_nodes) > 0:
            if group_concatenator == 'or' or group_concatenator == 'and_across':
                query['query']['filtered']['query']['bool']['should'].extend(group_nodes)

            elif group_concatenator == 'and_same':
                query['query']['filtered']['query']['bool']['must'].extend(group_nodes)

    # performing 'filters' element in parameters dict
    filters = parameters.get('filters')

    if default_posts_only is not True and filters:

        # adding TAGS search clause
        tags = filters.get('tags')
        if tags:
            inf_ids_in_tags = get_influencers_for_set_of_tags(None, tags)
            query['query']['filtered']['filter']['bool']['must'].append({
                "terms": {
                    "influencer.id": inf_ids_in_tags
                }
            })

        # this is for custom influencer fields
        custom_brand_categories = [w.lower() for w in filters.get('customCategories', [])]
        custom_brand_occupation = [w.lower() for w in filters.get('customOccupation', [])]
        custom_brand_ethnicity = [w.lower() for w in filters.get('customEthnicity', [])]
        custom_brand_tags = [w.lower() for w in filters.get('customTags', [])]
        custom_brand_age = filters.get('customAge', [])

        custom_brand_sex = [w.lower() for w in filters.get('customSex', [])]
        custom_brand_language = [w.lower() for w in filters.get('customLanguage', [])]


        if custom_brand_categories:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.categories" % brand_id, custom_brand_categories))
        if custom_brand_occupation:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.occupation" % brand_id, custom_brand_occupation))
        if custom_brand_ethnicity:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.ethnicity" % brand_id, custom_brand_ethnicity))
        if custom_brand_tags:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.tags" % brand_id, custom_brand_tags))
        if custom_brand_age:
            custom_brand_age_min = custom_brand_age.get('range_min')
            custom_brand_age_max = custom_brand_age.get('range_max')
            query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.custom_brand_data.%s.age' % brand_id, custom_brand_age_min, custom_brand_age_max)
            )

        # @TODO: ATUL, WHAT ABOUT THOSE?
        if custom_brand_sex:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.sex" % brand_id, custom_brand_sex))
        if custom_brand_language:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.custom_brand_data.%s.language" % brand_id, custom_brand_language))

        # adding CATEGORIES search clause
        categories = filters.get('categories')
        if categories:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.categories", categories))

        # adding GENDER search clause
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        # gender consists of list with parameters: ['Female', 'Male'], index needs lowercase first letter
        gender = filters.get('gender')
        if gender and influencer_ids is None:
            query['query']['filtered']['query']['bool']['must'].append(
                term_terms("influencer.gender", [g[:1].lower() for g in gender if len(g) > 1])
            )

        # adding SOCIAL search clause
        social = filters.get('social')
        if social and influencer_ids is None:

            social_value = social.get('value')
            range_min = social.get('range_min')
            range_max = social.get('range_max')
            print ('\n\n*** SOCIAL_VALUE: %r' % social_value)
            if social_value is not None:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.num_followers' % social_value.lower(), range_min, range_max)
                )

        # adding LIKES search clause
        likes = filters.get('likes')
        if likes and influencer_ids is None:
            social_value = likes.get('value')
            range_min = likes.get('range_min')
            range_max = likes.get('range_max')

            if social_value is not None:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.like_count' % social_value.lower(), range_min, range_max)
                )

        # adding SHARES search clause
        shares = filters.get('shares')
        if shares and influencer_ids is None:
            social_value = shares.get('value')
            range_min = shares.get('range_min')
            range_max = shares.get('range_max')

            if social_value is not None:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.share_count' % social_value.lower(), range_min, range_max)
                )

        # adding COMMENTS search clause
        comments = filters.get('comments')
        if comments and influencer_ids is None:
            social_value = comments.get('value')
            range_min = comments.get('range_min')
            range_max = comments.get('range_max')

            if social_value is not None:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.comment_count' % social_value.lower(), range_min, range_max)
                )

        # adding SOURCE search clause
        source = filters.get('source')
        if source:
            for s in source:
                if s is not None and len(s) > 0:
                    query['query']['filtered']['query']['bool']['must'].append(
                        term_wildcard("influencer.social_platforms.source", "*%s*" % s)
                    )

        # adding BRAND_EMAILED search clause
        brand_emailed = filters.get('brand_emailed')
        if brand_emailed:
            query['query']['filtered']['filter']['bool']['must'].append(
                term_terms("influencer.social_platforms.brand_emailed", brand_emailed),
            )

        # Adding ACTIVITY search clause
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        activity = filters.get('activity')
        if activity and influencer_ids is None:

            platform = activity.get('platform')
            if platform.lower() == 'blog':
                platform = ["Blogspot", "Wordpress", "Custom", "Tumblr", "Squarespace"]
            else:
                platform = [platform, ]

            activity_level = activity.get('activity_level')
            if hasattr(ActivityLevel, activity_level):
                activity_level = ActivityLevel._ENUM[activity_level]

            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            term_range("influencer.social_platforms.%s.activity_level" % plat.lower(), 0, activity_level) for plat in platform
                        ]
                    }
                }
            )

        # adding AGE DISTRIBUTION filter
        distr_age = filters.get('avgAge')
        if distr_age:
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter(
                                {
                                    'field': 'influencer.social_platforms.distibutions.dist_age_%s' % group_name,
                                    'min': 25
                                }
                            ) for group_name in distr_age if group_name in ('0_19', '20_24', '25_29',
                                                                            '30_34', '35_39', '40')
                        ]
                    }
                }
            )

        # adding TRAFFIC PER MONTH filter
        traffic_per_month = filters.get('traffic_per_month')
        if traffic_per_month:

            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            term_range("influencer.social_platforms.%s.traffic_per_month" % plat.lower(), 0, traffic_per_month) for plat in platform
                        ]
                    }
                }
            )

        # adding ALEXA RANK filter
        alexa_rank = filters.get('alexa_rank')
        if alexa_rank:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.alexa_rank" % plat.lower(),
                                          'min': alexa_rank}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC SEARCH filter
        traffic_search = filters.get('traffic_search')
        if traffic_search:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_search" % plat.lower(),
                                          'min': traffic_search}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC DIRECT filter
        traffic_direct = filters.get('traffic_direct')
        if traffic_direct:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_direct" % plat.lower(),
                                          'min': traffic_direct}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC SOCIAL filter
        traffic_social = filters.get('traffic_social')
        if traffic_social:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_social" % plat.lower(),
                                          'min': traffic_social}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC REFERRAL filter
        traffic_referral = filters.get('traffic_referral')
        if traffic_referral:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_referral" % plat.lower(),
                                          'min': traffic_referral}) for plat in platform
                        ]
                    }
                }
            )

        # adding MOZ DOMAIN AUTHORITY filter
        moz_domain_authority = filters.get('moz_domain_authority')
        if moz_domain_authority:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            # TODO: Blogspot_moz_domain_authority
                            range_filter({'field': "influencer.social_platforms.%s.Blogspot_moz_domain_authority" % plat.lower(),
                                          'min': moz_domain_authority}) for plat in platform
                        ]
                    }
                }
            )

        # adding MOZ EXTERNAL LINKS filter
        moz_external_links = filters.get('moz_external_links')
        if moz_external_links:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['query']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            # TODO: Blogspot_moz_external_links
                            range_filter({'field': "influencer.social_platforms.%s.Blogspot_moz_external_links" % plat.lower(),
                                          'min': moz_external_links}) for plat in platform
                        ]
                    }
                }
            )

        # ENGAGEMENT
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        engagement = filters.get('engagement')
        if engagement and influencer_ids is None:
            range_min = engagement.get('range_min')
            range_max = engagement.get('range_max')
            if range_min or range_max:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_range('influencer.avg_numcomments_overall', range_min, range_max)
                )

        # adding LOCATION search clause
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        location = filters.get('location')
        if location and len(location) > 0 and influencer_ids is None:
            # locations = expand_locations(location)
            query['query']['filtered']['query']['bool']['must'].append(
                # term_terms('location', [l.lower() for l in locations])
                {
                    "query_string": {
                        "default_field": "influencer.location",
                        "query": " OR ".join(["\"%s\"" % loc for loc in location])
                    }
                }
            )

        # adding PRICERANGES search clause
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        price_ranges = filters.get('priceranges')
        if price_ranges and len(price_ranges) > 0 and influencer_ids is None:
            prices_dict = {
                "Cheap": "cheap",
                "Mid-level": "middle",
                "Expensive": "expensive"
            }
            prices_values = []

            for price in price_ranges:
                prices_values.append(prices_dict.get(price, price))

            if prices_values:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_terms('influencer.price_range', prices_values)
                )

        # adding posts time range search clause
        time_range = filters.get('time_range')

        if time_range:
            print("YES, we have time_range")
            try:
                from_date_str = time_range.get('from', "").split('T')[0]
                if from_date_str:
                    from_date = datetime.strptime(from_date_str, "%Y-%m-%d")\
                        .replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=4)
                    from_date_str = from_date.strftime("%Y-%m-%dT%H:%M:%S.000000")

                to_date_str = time_range.get('to', "").split('T')[0]
                if to_date_str:
                    to_date = datetime.strptime(to_date_str, "%Y-%m-%d")\
                        .replace(hour=23, minute=59, second=59, microsecond=999) + timedelta(hours=4)
                    to_date_str = to_date.strftime("%Y-%m-%dT%H:%M:%S.999999")

                query['query']['filtered']['query']['bool']['must'].append(
                    term_range("create_date", from_date_str, to_date_str)
                )
            except TypeError:
                pass

        # adding POPULARITY search clause
        popularity = filters.get('popularity')
        if isinstance(popularity, list) and 0 < len(popularity) < 3:
            from debra.search_helpers import get_popularity_filter
            from debra.models import Influencer
            ranges = []
            for p in popularity:
                treshold = get_popularity_filter(
                    p,
                    Influencer.objects.filter(show_on_search=True).exclude(blacklisted=True)
                )
                if treshold is not None:
                    ranges.append(term_range('influencer.popularity', treshold.get('min', None), treshold.get('max', None)))

                query['query']['filtered']['query']['bool']['must'].append(
                    {
                        "bool": {
                            "should": ranges
                        }
                    }
                )

    # add PLATFORM filtering
    platform = parameters.get('post_platform')
    if platform:
        query['query']['filtered']['query']['bool']['must'].append({
            "terms": {
                "platform_name": platform

            }
        })

    query["sort"] = [
        {
            "create_date": {
                "order": "desc"
            }
        },
        {
            "_score": {
                "order": "desc"
            }
        }
    ]

    # clean unused nodes
    core_bool_node = query['query']['filtered']['query']['bool']

    if len(core_bool_node['must']) == 0:
        core_bool_node.pop('must')
    if len(core_bool_node['should']) == 0:
        core_bool_node.pop('should')
        core_bool_node.pop('minimum_should_match')
    if len(core_bool_node['must_not']) == 0:
        core_bool_node.pop('must_not')

    if len(query['query']['filtered']['query']['bool']) == 0:
        query['query']['filtered']['query'] = {
            "match_all": {}
        }

    return query





def es_product_query_builder_v3(parameters, page=0, page_size=30, highlighted_first=False):
    """
    Builds a json for products ES query by parameters, page and page_size.

    If we seek posts only for designated influencers, list of their ids should be passed as "direct_influencers_ids"
    list in parameters.

    :param parameters: dict of parameters for search query of ES
    :param page: desired page number of results
    :param page_size: quantity of results per page
    :return: ES query json

    """

    # from debra.models import ActivityLevel

    # no tags are set into query
    has_tags = bool(parameters.get('filters', {}).get('tags', None))

    try:
        page = int(page)
    except TypeError:
        page = 0

    query = {

        "_source": [
            "products.id"
        ],

        "from": page*page_size,
        "size": page_size,

        "query": {
            "filtered": {
                "filter": get_query_filter_v2(
                    settings.DEBUG,
                    # If specific influencer_ids provided, then show them even if they are blacklisted
                    exclude_blacklisted=('influencer_ids' not in parameters),
                    has_tags=has_tags
                ),
                "query": {
                    "bool": {
                        "must": [],
                        "should": [],
                        "must_not": [],
                        "minimum_should_match": 1
                    }
                }
            }
        }
    }


    # We want to show default posts (i.e., without any queries applied). Then, Pavel will implement a new button
    # that will allow the users to click on to see relevant posts.
    default_products_only = parameters.get('default_products', False)
    if default_products_only is not True:
        query["highlight"] = {
            "fields": {
                "products.brand": {"number_of_fragments": 1, "fragment_size": 1},
                "products.brand_url": {"number_of_fragments": 1, "fragment_size": 1},
                "products.prod_url": {"number_of_fragments": 1, "fragment_size": 1}
            }
        }

    print(u'* PARAMETERS: %s' % parameters)
    # adding KEYWORD search clause
    # This concatenator defines logic INSIDE groups of keywords. Can be OR ('or') or AND ('and').
    concatenator = parameters.get('concatenator', 'or')  # concatenator defining AND or OR logic when searching

    # This concatenator defines logic BETWEEN groups of keywords of POSTS filters.
    # Can be OR ('or'), AND_SAME ('and_same'), AND_ACROSS ('and_across).
    # 'and_same' means that AT LEAST ONE of the keywords from each group should appear IN THE SAME post.
    # 'and_across' means that AT LEAST ONE of the keywords from each group should appear in AT LEAST SOME post.
    group_concatenator = parameters.get('group_concatenator', 'or')

    # adding direct influencers if any
    influencer_ids = parameters.get('influencer_ids', None)

    # adding direct influencers if any

    if influencer_ids:
        query['query']['filtered']['query']['bool']['must'].append(
            term_terms("influencer.id", influencer_ids)
        )

        # if we have influencer_ids, then we can dump away filtering for influencers/posts
        query["query"]["filtered"]["filter"] = {
            "match_all": {}
        }
    else:
        query["query"]["filtered"]["query"]["bool"]["must"].append(
            {
                "range": {
                    "create_date": {
                        "lte": "now"
                    }
                }
            }
        )

    # adding KEYWORD search clause
    keywords = parameters.get('keyword')
    keyword_type = parameters.get('type', 'all')
    keyword_types = parameters.get('keyword_types', [])
    if not keyword_types and keywords:
        keyword_types = [keyword_type] * len(keywords)

    groups = parameters.get('groups', [])

    post_keywords = None

    if default_products_only is not True and keywords:
        if parameters.get('and_or_filter_on'):
            # here we create a map of lists of tuples, instead of list of lists of lists
            post_keywords = collections.defaultdict(list)
            for keyword, keyword_type, group in zip(keywords, keyword_types, groups):
                post_keywords[group].append((keyword_type, keyword))
            print '* Post Keywords: ', post_keywords
        else:

            keyword_subquery = {
                "nested": {
                    "path": "products",
                    "query": {
                        "bool": {
                            "minimum_should_match": 1,
                            "must": [
                                {
                                    "range": {
                                        "create_date": {
                                            "lte": "now"
                                        }
                                    }
                                }
                            ],
                            "should": [],
                        }
                    }
                }
            }
            append = False
            for keyword, keyword_type in zip(keywords, keyword_types):
                append = True
                # PRODUCT fields
                if keyword_type in ['all']:
                    keyword_subquery['nested']['query']['bool']['should'].append(
                        term_multimatch(["products.name", "products.designer_name"], keyword)
                    )

                if keyword_type == 'brand':

                    t = time.time()
                    brand = brand_from_keyword(keyword)
                    print '# brand_from_keyword', time.time() - t

                    if brand is not None:
                        brand_name, brand_domain = brand.name, brand.domain_name
                    else:
                        brand_name, brand_domain = keyword, keyword

                    keyword_subquery['nested']['query']['bool']['should'].append(
                        term_match_phrase("product.brand", brand_name)
                    )

                    if is_correct_domain(brand_domain):
                        keyword_subquery['nested']['query']['bool']['should'].append(
                            term_multimatch(["product.brand_url", "product.prod_url"], brand_domain)
                        )
                else:
                    keyword_subquery['nested']['query']['bool']['should'].append(
                        term_match_phrase("product.brand", keyword)
                    )

                    if is_correct_domain(keyword):
                        keyword_subquery['nested']['query']['bool']['should'].append(
                            term_multimatch(["product.brand_url", "product.prod_url"], keyword)
                        )

                if keyword_type in ['all']:
                    keyword_subquery['nested']['query']['bool']['should'].append(
                        term_match_phrase("product.prod_url", keyword)
                    )

            if append is True:
                query['query']['filtered']['query']['bool']['should'].append(keyword_subquery)

    # performing post_keywords filters
    if default_products_only is not True and post_keywords is not None:

        group_nodes = []
        for group in post_keywords.values():

            # nodes, of which does this group of conditions consists
            group_subnodes = []

            for kw_type, kw in group:

                if kw_type in ['all', 'post_content', 'post_title', 'post_hashtag', 'post_mention']:
                    group_subnodes.append(
                        {
                            "nested": {
                                "path": "products",
                                "query": {
                                    "multi_match": {
                                        "use_dis_max": False,
                                        "query": "brownie",
                                        "type": "phrase",
                                        "fields": [
                                            "products.name",
                                            "products.designer_name",
                                            "products.brand",
                                            "products.brand_url",
                                            "products.prod_url"
                                        ]
                                    }
                                }
                            }
                        }
                    )

            if len(group_subnodes) > 0:

                group_node = {
                    "bool": {
                        "must" if concatenator == 'and' else 'should': group_subnodes
                    }
                }
                group_nodes.append(group_node)

        if len(group_nodes) > 0:
            if group_concatenator == 'or' or group_concatenator == 'and_across':
                query['query']['filtered']['query']['bool']['should'].extend(group_nodes)

            elif group_concatenator == 'and_same':
                query['query']['filtered']['query']['bool']['must'].extend(group_nodes)

    # performing 'filters' element in parameters dict
    filters = parameters.get('filters')
    if default_products_only is not True and filters and influencer_ids is None:

        # TODO: posts from twitter in index have no categories set
        # adding SOCIAL search clause
        social = filters.get('social')
        if social and influencer_ids is None:

            social_value = social.get('value')
            range_min = social.get('range_min')
            range_max = social.get('range_max')

            if social_value is not None:
                query['query']['filtered']['filter']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.num_followers' % social_value, range_min, range_max)
                )

        # adding LIKES search clause
        likes = filters.get('likes')
        if likes and influencer_ids is None:
            social_value = likes.get('value')
            range_min = likes.get('range_min')
            range_max = likes.get('range_max')

            if social_value is not None:
                query['query']['filtered']['filter']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.like_count' % social_value, range_min, range_max)
                )

        # adding SHARES search clause
        shares = filters.get('shares')
        if shares and influencer_ids is None:
            social_value = shares.get('value')
            range_min = shares.get('range_min')
            range_max = shares.get('range_max')

            if social_value is not None:
                query['query']['filtered']['filter']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.share_count' % social_value, range_min, range_max)
                )

        # adding COMMENTS search clause
        comments = filters.get('comments')
        if comments and influencer_ids is None:
            social_value = comments.get('value')
            range_min = comments.get('range_min')
            range_max = comments.get('range_max')

            if social_value is not None:
                query['query']['filtered']['filter']['bool']['must'].append(
                    term_range('influencer.social_platforms.%s.comment_count' % social_value, range_min, range_max)
                )

        # adding SOURCE search clause
        source = filters.get('source')
        if source:
            for s in source:
                if s is not None and len(s) > 0:
                    query['query']['filtered']['query']['bool']['must'].append(
                        term_wildcard("influencer.social_platforms.source", "*%s*" % s)
                    )

        # adding BRAND_EMAILED search clause
        brand_emailed = filters.get('brand_emailed')
        if brand_emailed:
            query['query']['filtered']['filter']['bool']['must'].append(
                term_terms("influencer.social_platforms.brand_emailed", brand_emailed),
            )

        # adding CATEGORIES search clause
        categories = filters.get('categories')
        if categories:
            query['query']['filtered']['query']['bool']['must'].append(term_terms("influencer.categories", categories))

        # adding GENDER search clause
        # gender consists of list with parameters: ['Female', 'Male'], index needs lowercase first letter
        gender = filters.get('gender')
        if gender and influencer_ids is None:
            query['query']['filtered']['query']['bool']['must'].append(
                term_terms("influencer.gender", [g[:1].lower() for g in gender if len(g) > 1])
            )

        # adding AGE DISTRIBUTION filter
        distr_age = filters.get('avgAge')
        if distr_age:
            query['query']['filtered']['filter']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter(
                                {
                                    'field': 'influencer.social_platforms.distibutions.dist_age_%s' % group_name,
                                    'min': 25
                                }
                            ) for group_name in distr_age if group_name in ('0_19', '20_24', '25_29',
                                                                            '30_34', '35_39', '40')
                        ]
                    }
                }
            )

        # adding TRAFFIC PER MONTH filter
        traffic_per_month = filters.get('traffic_per_month')
        if traffic_per_month:

            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['filter']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            term_range("influencer.social_platforms.%s.traffic_per_month" % plat.lower(), 0, traffic_per_month) for plat in platform
                        ]
                    }
                }
            )

        # adding ALEXA RANK filter
        alexa_rank = filters.get('alexa_rank')
        if alexa_rank:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['filter']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.alexa_rank" % plat.lower(),
                                          'min': alexa_rank}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC SEARCH filter
        traffic_search = filters.get('traffic_search')
        if traffic_search:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['filter']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_search" % plat.lower(),
                                          'min': traffic_search}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC DIRECT filter
        traffic_direct = filters.get('traffic_direct')
        if traffic_direct:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['filter']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_direct" % plat.lower(),
                                          'min': traffic_direct}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC SOCIAL filter
        traffic_social = filters.get('traffic_social')
        if traffic_social:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['filter']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_social" % plat.lower(),
                                          'min': traffic_social}) for plat in platform
                        ]
                    }
                }
            )

        # adding TRAFFIC REFERRAL filter
        traffic_referral = filters.get('traffic_referral')
        if traffic_referral:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['filter']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            range_filter({'field': "influencer.social_platforms.%s.traffic_referral" % plat.lower(),
                                          'min': traffic_referral}) for plat in platform
                        ]
                    }
                }
            )

        # adding MOZ DOMAIN AUTHORITY filter
        moz_domain_authority = filters.get('moz_domain_authority')
        if moz_domain_authority:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['filter']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            # TODO: Blogspot_moz_domain_authority
                            range_filter({'field': "influencer.social_platforms.%s.Blogspot_moz_domain_authority" % plat.lower(),
                                          'min': moz_domain_authority}) for plat in platform
                        ]
                    }
                }
            )

        # adding MOZ EXTERNAL LINKS filter
        moz_external_links = filters.get('moz_external_links')
        if moz_external_links:
            platform = ["Blogspot", "Wordpress", "Custom", "Squarespace"]
            query['query']['filtered']['filter']['bool']['must'].append(
                {
                    "bool": {
                        "should": [
                            # TODO: Blogspot_moz_external_links
                            range_filter({'field': "influencer.social_platforms.%s.Blogspot_moz_external_links" % plat.lower(),
                                          'min': moz_external_links}) for plat in platform
                        ]
                    }
                }
            )

        # ENGAGEMENT
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        engagement = filters.get('engagement')
        if engagement and influencer_ids is None:
            range_min = engagement.get('range_min')
            range_max = engagement.get('range_max')
            if range_min or range_max:
                query['query']['filtered']['filter']['bool']['must'].append(
                    term_range('influencer.avg_numcomments_overall', range_min, range_max)
                )

        # adding LOCATION search clause
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        location = filters.get('location')
        if location and len(location) > 0 and influencer_ids is None:
            # locations = expand_locations(location)
            query['query']['filtered']['query']['bool']['must'].append(
                # term_terms('location', [l.lower() for l in locations])
                {
                    "query_string": {
                        "default_field": "influencer.location",
                        "query": " OR ".join(["\"%s\"" % loc for loc in location])
                    }
                }
            )

        # adding PRICERANGES search clause
        # This is a HAS_PARENT query to search against content of the Post's Influencer
        price_ranges = filters.get('priceranges')
        if price_ranges and len(price_ranges) > 0 and influencer_ids is None:
            prices_dict = {
                "Cheap": "cheap",
                "Mid-level": "middle",
                "Expensive": "expensive"
            }
            prices_values = []

            for price in price_ranges:
                prices_values.append(prices_dict.get(price, price))

            if prices_values:
                query['query']['filtered']['query']['bool']['must'].append(
                    term_terms('influencer.price_range', prices_values)
                )

        # adding posts time range search clause
        time_range = filters.get('time_range')
        if time_range:
            try:
                from_date_str = time_range.get('from', "").split('T')[0]
                if from_date_str:
                    from_date = datetime.strptime(from_date_str, "%Y-%m-%d")\
                        .replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(hours=4)
                    from_date_str = from_date.strftime("%Y-%m-%dT%H:%M:%S.000000")

                to_date_str = time_range.get('to', "").split('T')[0]
                if to_date_str:
                    to_date = datetime.strptime(to_date_str, "%Y-%m-%d")\
                        .replace(hour=23, minute=59, second=59, microsecond=999) + timedelta(hours=4)
                    to_date_str = to_date.strftime("%Y-%m-%dT%H:%M:%S.999999")

                query['query']['filtered']['query']['filter']['must'].append(
                    term_range("create_date", from_date_str, to_date_str)
                )
            except TypeError:
                pass

    # add PLATFORM filtering
    platform = parameters.get('post_platform')

    if default_products_only is not True and platform:
        query['query']['filtered']['filter']['bool']['must'].append({
            "terms": {
                "platform_name": platform

            }
        })

    # add sorting
    if default_products_only is not True and highlighted_first:
        query["sort"] = [
            {
                "_score": {
                    "order": "desc"
                }
            },
            {
                "products.insert_date": {
                    "order": "desc"
                }
            }
        ]
    else:
        query["sort"] = [
            {
                "products.insert_date": {
                    "order": "desc"
                }
            },
            {
                "_score": {
                    "order": "desc"
                }
            }
        ]

    # clean product nodes
    core_bool_node = query['query']['filtered']['query']['bool']

    if len(core_bool_node['must']) == 0:
        core_bool_node.pop('must')
    if len(core_bool_node['should']) == 0:
        core_bool_node.pop('should')
        core_bool_node.pop('minimum_should_match')
    if len(core_bool_node['must_not']) == 0:
        core_bool_node.pop('must_not')

    if len(query['query']['filtered']['query']['bool']) == 0:
        query['query']['filtered']['query'] = {
            "match_all": {}
        }

    return query


def es_influencer_query_runner_v2(parameters, page_size, page, source=False, brand=None):
    """
    Builds a query for ES, executes it, performs the result to form Q object, list of ids and total hits.
    :param parameters: raw query from request body, contains data from search form or saved query
    :param page_size: quantity of influencers per page to return
    :param page: number of page to retrieve
    :param source: True if it should return list of influencer's data from ES, otherwise False only for ids
    :param brand: the brand who is running this query
    :return: resulting Q object of influencers' data, list of influencers' ids, total number of results
    """
    order_by = True if parameters.get('order_by') else False

    t1 = time.time()
    score_mapping = {}
    filtered_influencer_ids = []

    index_name = ELASTICSEARCH_INDEX

    endpoint = "/%s/_search" % index_name

    url = ELASTICSEARCH_URL

    print("Got brand %r" % brand)

    t01 = time.time()
    print "Page %r" % page
    query = es_influencer_query_builder_v3(parameters, page_size, page, source=source, brand=brand)
    t02 = time.time()
    print "Query generated for %s sec" % (t02 - t01)

    if settings.DEBUG:
        print "Running ES influencer v3 query on index", index_name
        print('*** QUERY: ')
        print json.dumps(query, indent=4)
        print('*** ES endpoint: %s' % (url + endpoint))

    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    if settings.DEBUG:
        print('REQUEST STATUS CODE: %s' % rq.status_code)
    if rq.status_code == 200:
        resp = rq.json()
        took = resp.get("took", None)
        #print resp
        total = resp.get("aggregations", {}).get("total_unique_influencers", {}).get('value', 0)
        ctr = 0
        blog_url_to_skip = ['http://amoreandvita.com/']
        for hit in resp.get("aggregations", {}).get("influencer_wise", {}).get("buckets", []):
            try:
                if (page+1)*page_size > ctr >= page*page_size:
                    if source is True:
                        # TODO: here we should return all influencer's fields: _id, name, blog_url, location, etc...
                        influencer = hit.get("inf_data", {}).get("hits", {}).get("hits", [])
                        if len(influencer) > 0:
                            influencer = influencer[0].get("_source", {}).get("influencer", None)
                        if influencer is not None:
                            burl = influencer.get('blog_url', None)
                            if burl and burl in blog_url_to_skip:
                                pass
                            else:
                                filtered_influencer_ids.append(influencer)
                            #print influencer
                    else:
                        influencer = int(hit.get("key", 0))
                        if influencer > 0:
                            filtered_influencer_ids.append(influencer)

            except ValueError:
                pass
            ctr += 1
        #print('RESULTS: %s' % filtered_influencer_ids)
        t2 = time.time()
        if settings.DEBUG and source is False:
            print "ES took", t2 - t1, " (inner ES time:", took, "ms), ","results:", len(filtered_influencer_ids), "total:", total
        if not filtered_influencer_ids:
            return Q(id=None), {}, total
        return Q(id__in=filtered_influencer_ids), filtered_influencer_ids, total
    else:
        print rq.json()["error"]
        return Q(id=None), {}, 0


def es_post_query_runner_v2(parameters, page, page_size, highlighted_first=False, brand=None):
    """
    Builds and executes ES query to fetch POSTS by user's input data

    :param parameters: dict of parameters from user's search form + extra added
    :param page: number of page for results
    :param page_size: number of results per page
    :param highlighted_first: flag indicating that highlighted posts by keywords must go first in result
    :return: list of post ids, highlighted posts ids, total number of hits for query in ES
    """
    post_ids = []
    highlighted_ids = []
    total = 0

    # forming ES post url from constants data
    # OLD: post_index_url = "%s/%s/post/_search" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)
    post_index_url = "%s/%s/_search" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)
    print("BRAND : %r" % brand)
    # building ES query by parameters
    es_query = es_post_query_builder_v3(parameters, page, page_size, highlighted_first, brand=brand)

    if settings.DEBUG:
        print "Running ES post query v3, url=", post_index_url
        print json.dumps(es_query, indent=4)

    # get product ids list and total count
    rq = make_es_get_request(
        es_url=post_index_url,
        es_query_string=json.dumps(es_query)
    )

    if rq.status_code == 200:
        resp = rq.json()
        total = resp.get("hits", {}).get("total", 0)
        for hit in resp.get("hits", {}).get("hits", []):
            post_id = int(hit.get("_id", 0))
            if post_id > 0:
                post_ids.append(post_id)
                if "highlight" in hit:
                    highlighted_ids.append(post_id)

        if settings.DEBUG:
            print "ES took %s ms, results: %s, total: %s" % (resp.get('took', 0), len(post_ids), total)

    return post_ids, highlighted_ids, total


def es_product_query_runner_v2(parameters, page, page_size, highlighted_first=False):
    """
    Builds and executes ES query to fetch ITEMS by user's input data

    :param parameters: dict of parameters from user's search form + extra added
    :param page: number of page for results
    :param page_size: number of results per page
    :return: sorted list of product ids, highlighted product ids, total number of hits for query in ES
    """
    product_ids = []
    highlighted_ids = []
    total = 0

    # forming ES product url from constants data
    product_index_url = "%s/%s/_search" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)

    # building ES query by parameters
    es_query = es_product_query_builder_v3(parameters, page, page_size, highlighted_first)

    if settings.DEBUG:
        print "Running ES product query v2, url=", product_index_url
        print json.dumps(es_query, indent=4)

    # get product ids list and total count
    rq = make_es_get_request(
        es_url=product_index_url,
        es_query_string=json.dumps(es_query)
    )

    if rq.status_code == 200:
        resp = rq.json()
        total = resp.get("hits", {}).get("total", 0)
        for hit in resp.get("hits", {}).get("hits", []):
            products = hit.get("_source", {}).get("products", [])
            for p in products:
                product_id = int(p.get("id", 0))
                if product_id > 0:
                    product_ids.append(product_id)
                    if "highlight" in hit:
                        highlighted_ids.append(product_id)
        if settings.DEBUG:
            print "ES took %s ms, results: %s, total: %s" % (resp.get('took', 0), len(product_ids), total)

    return product_ids, highlighted_ids, total


def brand_from_keyword(keyword):
    ''' brand_from_keyword returns brand models if they match the keywords. '''
    from debra.models import Brands
    if type(keyword) == dict:
        keyword = keyword.get("value")

    domain = domain_from_url(keyword)

    try:
        brand = Brands.objects.get(
            blacklisted=False, domain_name=domain)
        print('BRAND: %s' % brand)
    except Exception as e:
        brand = None

    return brand


# TODO: Some old queries were used for Ralph Lauren
def influencers_by_posts_with_keywords(keywords_list, page=1, size=20, concatenator='and'):
    """
    Function returns list of influencers' ids coupled with number of posts
    containing at least one of these keywords.
    For now it looks for ALL fields in post, currently:
        title
        content
        brands *
        brand_domains *
        title_hashtags
        content_hashtags
        title_mentions
        content_mentions
    and in dependent product's fields:
        name
        designer_name
        brand *
        brand_url *
        prod_url *

    :param keywords_list: - list of keywords to seek in posts of influencers
    :param page: page of results
    :param size: number of influencers to retrieve
    :param concatenator: concatenator of keywords, 'and' or 'or'
    :return: list of influencers paired with their count of posts, total number of influencers
    """
    result = []

    if type(keywords_list) == str:
        keywords_list = [keywords_list, ]

    # this is a post subquery which has search clauses against keywords
    hashtags_list = ['#%s' % kw for kw in keywords_list]
    mentions_list = ['@%s' % kw for kw in keywords_list]

    brand_names = []
    brand_domains = []

    for kw in keywords_list:
        brand = brand_from_keyword(kw)
        if brand is not None:
            brand_names.append(brand.name)
            brand_domains.append(brand.domain_name)
        else:
            brand_names.append(kw)
            brand_domains.append(kw)

    post_should_query = [

        # term_multimatch(["content_hashtags", "title_hashtags"], hashtags_list),
        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    term_multimatch(["content_hashtags", "title_hashtags"],
                                    hashtag) for hashtag in hashtags_list
                ]
            }
        },

        # term_multimatch(["content_mentions", "title_mentions"], mentions_list),
        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    term_multimatch(["content_mentions", "title_mentions"],
                                    mention) for mention in mentions_list
                ]
            }
        },

        # term_multimatch(["brands", "product_names"], brand_names),
        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    term_multimatch(["brands", "product_names", "designer_names"],
                                    brand_name) for brand_name in brand_names
                ]
            }
        },

        # term_multimatch(["brand_domains", "product_urls"], brand_domains),
        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    term_multimatch(["brand_domains", "product_urls"],
                                    brand_domain) for brand_domain in brand_domains
                ]
            }
        },

        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    {"match_phrase": {'content': kw}} for kw in keywords_list
                ]
            }
        },

        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    {"match_phrase": {'title': kw}} for kw in keywords_list
                ]
            }
        }


    ]

    json_query = {
        "fields": ["_id"],
        "from": page-1,
        "size": size,
        "query": {
            "filtered": {
                "query": {
                    "bool": {
                        "minimum_should_match": 1,
                        "must": [
                            {
                                "has_child": {
                                    "child_type": "post",
                                    "query": {

                                        "constant_score": {
                                            "query": {
                                                "bool": {
                                                    "minimum_should_match": 1,
                                                    "should": post_should_query
                                                }
                                            },
                                            "boost": 1.0
                                        }
                                    },
                                    "score_mode": "sum"
                                }
                            }
                        ]
                    }
                },
                "filter": get_query_filter(settings.DEBUG)
            }
        },
        "sort": {
            "_score": {
                "order": "desc"
            }
        }
    }

    # print json.dumps(json_query, indent=4)

    index_name = ELASTICSEARCH_INDEX

    endpoint = "/%s/influencer/_search" % index_name
    url = ELASTICSEARCH_URL

    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(json_query)
    )

    if rq.status_code == 200:
        resp = rq.json()
        total = resp.get("hits", {}).get("total", 0)
        for hit in resp.get("hits", {}).get("hits", []):
            inf_id = hit.get('_id', None)
            score = hit.get('_score', None)
            if inf_id and score:
                result.append((inf_id, score))
        return result, total
    else:
        return result, None


# TODO: Some old queries were used for Ralph Lauren
def post_ids_by_keywords(keywords_list, page=1, size=20, concatenator='and'):
    """
    Function returns list of posts' ids
    containing at least one of these keywords.
    For now it looks for fields in post, currently:
        content_hashtags
        title_hashtags
        content_mentions
        title_mentions
        brands
        product_names
        brand_domains
        product_urls
        content *
        title *

    :param keywords_list: - list of keywords to seek in posts of influencers
    :param page: page of results
    :param size: number of influencers to retrieve
    :param concatenator: concatenator of keywords, 'and' or 'or'
    :return: list of influencers paired with their count of posts, total number of influencers
    """
    result = []

    if type(keywords_list) == str:
        keywords_list = [keywords_list, ]

    # this is a post subquery which has search clauses against keywords
    hashtags_list = ['#%s' % kw for kw in keywords_list]
    mentions_list = ['@%s' % kw for kw in keywords_list]

    brand_names = []
    brand_domains = []

    for kw in keywords_list:
        brand = brand_from_keyword(kw)
        if brand is not None:
            brand_names.append(brand.name)
            brand_domains.append(brand.domain_name)
        else:
            brand_names.append(kw)
            brand_domains.append(kw)

    post_should_query = [

        # term_multimatch(["content_hashtags", "title_hashtags"], hashtags_list),
        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    term_multimatch(["content_hashtags", "title_hashtags"],
                                    hashtag) for hashtag in hashtags_list
                ]
            }
        },

        # term_multimatch(["content_mentions", "title_mentions"], mentions_list),
        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    term_multimatch(["content_mentions", "title_mentions"],
                                    mention) for mention in mentions_list
                ]
            }
        },

        # term_multimatch(["brands", "product_names"], brand_names),
        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    term_multimatch(["brands", "product_names", "designer_names"],
                                    brand_name) for brand_name in brand_names
                ]
            }
        },

        # term_multimatch(["brand_domains", "product_urls"], brand_domains),
        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    term_multimatch(["brand_domains", "product_urls"],
                                    brand_domain) for brand_domain in brand_domains
                ]
            }
        },

        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    {"match_phrase": {'content': kw}} for kw in keywords_list
                ]
            }
        },

        {
            "bool": {
                "must" if concatenator == 'and' else 'should': [
                    {"match_phrase": {'title': kw}} for kw in keywords_list
                ]
            }
        }

    ]

    # for kw in keywords_list:
    #     post_should_query.append({"match_phrase": {'content': kw}})
    #     post_should_query.append({"match_phrase": {'title': kw}})

    json_query = {
        "fields": ["create_date"],

        "from": (page-1) * size,
        "size": size,

        "query": {
            "filtered": {

                "query": {
                    "bool": {
                        "must": [
                            # This could seem weird, but some posts in Posts model have datetime of distant future
                            # to be shown on top places of recent posts. So we deal with that nuisance it this way.
                            {
                                "range": {
                                    "create_date": {
                                        "lte": "now"
                                    }
                                }
                            },
                        ],

                        "should": [
                            {
                                # this should clause will render results with hits on fields by keywords,
                                # and they will be highlighted and placed in front of others because of hightened score
                                "constant_score": {
                                    "query": {
                                        "bool": {
                                            "minimum_should_match": 1,
                                            "should": post_should_query
                                        }
                                    },
                                    "boost": 10.0
                                }
                            },
                        ],
                        "must_not": [],
                        "minimum_should_match": 1
                    }
                },
                "filter": {
                    "has_parent": {
                        "type": "influencer",
                        "filter": get_query_filter(settings.DEBUG)
                    }
                }
            }
        },

        "sort": {
            "_score": {
                "order": "desc"
            }
        }
    }

    # print json.dumps(json_query, indent=4)

    post_index_url = "%s/%s/post/_search" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)

    rq = make_es_get_request(
        es_url=post_index_url,
        es_query_string=json.dumps(json_query)
    )

    if rq.status_code == 200:
        resp = rq.json()
        total = resp.get("hits", {}).get("total", 0)
        for hit in resp.get("hits", {}).get("hits", []):
            inf_id = hit.get('_id', None)
            if inf_id:
                result.append(inf_id)
        return result, total
    else:
        return result, None


# TODO: remove this when moved to new flattened mapping
def get_query_filter(debug=True, exclude_blacklisted=True, has_tags=False):
    """
    Returns a dict for ES filter query depending on DEBUG setting
    :param debug: - debug setting
    :param has_tags - if query has tags filter (then we use show_on_search)
    :return: dict of filter
    """
    # TODO: for old index to work
    #if '23.251.156.9' not in ELASTICSEARCH_URL:
    if 'http://198.199.71.215:9200' not in ELASTICSEARCH_URL:
        return {
            "and": [
                {
                    "match_all": {}
                }
            ]
        }

    # If we search by tags, we do not apply any of the conditions [blacklisted, show_on_search]
    if has_tags:
        return {
            "and": [
                {
                    "match_all": {}
                }
            ]
        }

    field_name = "show_on_search" if debug or has_tags else "old_show_on_search"
    result = {
        "and": [
            {
                "term": {
                    field_name: True
                }
            }
        ]
    }
    if exclude_blacklisted and not has_tags:
        result['and'].append({
            "term": {
                "blacklisted": False
            }
        })
    return result


def get_query_filter_v2(debug=True, exclude_blacklisted=True, has_tags=False):
    """
    Returns a dict for ES filter query depending on DEBUG setting
    :param debug: - debug setting
    :param has_tags - if query has tags filter (then we use show_on_search)
    :return: dict of filter
    """
    # If we search by tags, we do not apply any of the conditions [blacklisted, show_on_search]
    # if has_tags:
    #     return {
    #         "and": [
    #             {
    #                 "match_all": {}
    #             }
    #         ],
    #         "bool": {
    #             "must": []
    #         }
    #     }

    field_name = "influencer.show_on_search" if debug or has_tags else "influencer.old_show_on_search"
    result = {
        "bool": {
            "must": [
                {
                    "term": {
                        field_name: True
                    }
                },
                {
                    "exists": {
                        "field": "influencer.popularity"
                    }
                }
            ],
            "must_not": []
        }
    }

    if exclude_blacklisted and not has_tags:
        result['bool']['must'].append({
            "term": {
                "influencer.blacklisted": False
            }
        })

    return result


def get_influencers_for_set_of_tags(es_conn=None, tag_list=None):
    """
    Function for finding inflencers ids for a given list of tags
    :param es_conn: es connection endpoint
    :param tag_list: a list of tag ids
    :return: a list of unique influencer ids
    """
    query = {"ids": tag_list}
    inf_ids = []

    if not es_conn:
        from elasticsearch import Elasticsearch
        es_conn = Elasticsearch(ELASTICSEARCH_URL,
                                http_auth=(settings.ELASTICSEARCH_SHIELD_USERNAME,
                                           settings.ELASTICSEARCH_SHIELD_PASSWORD,)
        )
    exists_resp = es_conn.mget(index=ELASTICSEARCH_TAGS_INDEX,
                               doc_type=ELASTICSEARCH_TAGS_TYPE,
                               body=query,
                               request_timeout=200)
    for tag in exists_resp['docs']:
        if not tag['found']:
            print "the document for %r not found" % tag['_id']
        else:
            resp = {
                'tag_id': tag['_id'],
                'influencer_list': tag['_source']['tags']
            }
            vals = resp['influencer_list']
            inf_ids.extend(vals)

    return list(set(inf_ids))



def update_document_append_mode(es_conn, index_name, doc_type, field_name, append_value, doc_id):
    """
    A helper function from elasticsearch essentials book ;) for partially updating  document in append mode
    :param index_name: Name of the index
    :param doc_type: Name of document type
    :param field_name: Name of the array field to be updated
    :param append_value: Value which need to be appended in the array
    :param doc_id: Document id to be updated
    :return:
    """
    script = {"script": "ctx._source."+field_name+" +="+"parameter",
             "params": {
                 "parameter": append_value
             }
    }

    es_conn.update(index=index_name, doc_type=doc_type, body=script, id=doc_id)


def influencer_add_tag(influencer_id, tag_id):
    """
    This function updates Influencer record in ES index by adding tag_id to the tags list.
    :param influencer_id: id of the influencer to update
    :param tag_id: id of the tag to add
    :return:
    """
    # TODO: need to re-make it for adding tag for all corresponding indexed documents of this influencer or think about another mechanism
    from elasticsearch import Elasticsearch

    es_conn = Elasticsearch(ELASTICSEARCH_URL,
                            http_auth=(settings.ELASTICSEARCH_SHIELD_USERNAME,
                                       settings.ELASTICSEARCH_SHIELD_PASSWORD,)
    )

    #check if the tags exist
    if not es_conn.exists(index=ELASTICSEARCH_TAGS_INDEX, doc_type=ELASTICSEARCH_TAGS_TYPE, id=tag_id):
        #if tag does not exist, you need to create it and then you can start adding influencers into it, otherwise it give 404 error
        print 'tag %r not found' % tag_id
        es_conn.index(index=ELASTICSEARCH_TAGS_INDEX, doc_type=ELASTICSEARCH_TAGS_TYPE, id=tag_id, body={'tags':[]})

    update_document_append_mode(es_conn, ELASTICSEARCH_TAGS_INDEX, ELASTICSEARCH_TAGS_TYPE, 'tags', influencer_id, tag_id)
    return True


def influencer_remove_tag(influencer_id, tag_id):
    """
    This function updates Influencer record in ES index by removing tag_id from the tags list.
    :param influencer_id: id of the influencer to update
    :param tag_id: id of the tag to delete
    :return:
    """
    # TODO: need to re-make it for removing tag for all corresponding indexed documents of this influencer or think about another mechanism

    from elasticsearch import Elasticsearch

    es_conn = Elasticsearch(ELASTICSEARCH_URL,
                            http_auth=(settings.ELASTICSEARCH_SHIELD_USERNAME,
                                       settings.ELASTICSEARCH_SHIELD_PASSWORD,)
    )

    if es_conn.exists(index=ELASTICSEARCH_TAGS_INDEX, doc_type=ELASTICSEARCH_TAGS_TYPE, id=tag_id):
        json_query = {
            "script": "ctx._source.tags.removeAll(existing_tag)",
            "params": {
                "existing_tag": influencer_id
            }
        }

        es_conn.update(index=ELASTICSEARCH_TAGS_INDEX, doc_type=ELASTICSEARCH_TAGS_TYPE, id=tag_id, body=json_query)
    else:
        return False



def influencer_set_blacklisted(influencer_id, blacklisted):
    """
    This function updates Influencer record in ES index by setting corresponding value to blacklisted attribute.
    :param influencer_id: id of the influencer to update
    :param blacklisted: boolean value of blacklisted attribute to set.
    :return:
    """
    # TODO: need to re-make it for setting blacklisted=True for all corresponding indexed documents of this influencer or think about another mechanism

    endpoint = "/%s/influencer/%s/_update" % (ELASTICSEARCH_INDEX, influencer_id)
    url = ELASTICSEARCH_URL

    json_query = {
        "doc": {
            "blacklisted": blacklisted
        }
    }

    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(json_query)
    )

    # print('Result: %s : %s' % (rq.status_code, rq.content))
    return rq.status_code == 200


# TODO: Some old queries were used for Ralph Lauren
def helper_search_influencers_by_post_fields(entity='influencer',
                                             condition=[],
                                             group_concatenator='or',
                                             concatenator='or',
                                             page_size=60,
                                             page=0):
    """
    This helper invokes search by Influencers, Posts, Products according to the given parameters and returns
    a list of ids of required entities and their total count.

    :param entity: determines what model do we search against. Can be any of ['influencer', 'post', 'product']
    :param condition: this is a list of groups (list) that contain lists of pair field/keyword values, for example:
            [[['post_content', 'ralphlauren'],['post_content', 'ralph lauren']],
             [['post_content', 'running'],['post_content', 'j.crew']]]
    :param group_concatenator: determines logic between groups, can be any of ['or', 'and_same', 'and_across']
    :param concatenator: determines logic inside groups, can be any of ['or', 'and']
    :param page_size: quantity of results to return per page
    :param page: number of result page to return
    :return:
    """
    # Converting input data...
    parameters = {
        'concatenator': concatenator,
        'group_concatenator': group_concatenator,
        # 'post_keywords': condition
    }

    groups = []
    keywords = []
    keywords_types = []
    grp_ctr = 0
    for grp in condition:
        for key_value in grp:
            keywords_type = key_value[0]
            keyword = key_value[1]
            groups.append(grp_ctr)
            keywords.append(keyword)
            keywords_types.append(keywords_type)
        grp_ctr += 1

    parameters['keyword'] = keywords
    parameters['keyword_types'] = keywords_types
    parameters['groups'] = groups
    parameters['and_or_filter_on'] = True
    parameters['type'] = 'all'

    if entity == 'influencer':
        _, ids, total = es_influencer_query_runner_v2(parameters, page_size, page)
    elif entity == 'post':
        ids, _, total = es_post_query_runner_v2(parameters, page_size=page_size, page=page)
    elif entity == 'product':
        ids, _, total = es_product_query_runner_v2(parameters, page_size=page_size, page=page)
    else:
        return None, None

    return ids, total


# TODO: Some old queries were used for Ralph Lauren
def helper_influencer_stats(condition=[],
                            group_concatenator='or',
                            concatenator='or',
                            min_satisfying_posts=1):
    """

    :param condition: this is a list of groups (list) that contain lists of pair field/keyword values, for example:
            [[['post_content', 'ralphlauren'],['post_content', 'ralph lauren']],
             [['post_content', 'running'],['post_content', 'j.crew']]]
    :param group_concatenator: determines logic between groups, can be any of ['or', 'and_same', 'and_across']
    :param concatenator: determines logic inside groups, can be any of ['or', 'and']
    :param min_satisfying_posts: determines what minimum number of matching post influencer should have to be
            taken into account
    :return:
    """

    # Converting input data...
    parameters = {
        'concatenator': concatenator,
        'group_concatenator': group_concatenator,
        # 'post_keywords': condition
    }

    groups = []
    keywords = []
    keywords_types = []
    grp_ctr = 0
    for grp in condition:
        for key_value in grp:
            keywords_type = key_value[0]
            keyword = key_value[1]
            groups.append(grp_ctr)
            keywords.append(keyword)
            keywords_types.append(keywords_type)
        grp_ctr += 1

    parameters['keyword'] = keywords
    parameters['keyword_types'] = keywords_types
    parameters['groups'] = groups
    parameters['and_or_filter_on'] = True
    parameters['type'] = 'all'

    # preparing ES parameters
    index_name = ELASTICSEARCH_INDEX
    endpoint = "/%s/influencer/_search" % index_name
    url = ELASTICSEARCH_URL

    # building base query for influencer
    # TODO: need to be adapted for new flattened schema
    query = es_influencer_query_builder_v2(parameters, 1, page=0)

    # Distribution of influencers: by quality (less than <1K followers,
    # less than 2K, less than 4K, 6K, 8K, 10K, 15K, 20K, 30K, 50K, 75K, 100K, 1MM, 10 MM, 100MM)
    distr_by_quality = {}

    query['aggs'] = {

        "followers_ranges": {
            "range": {
                "script": "sum = 0; for(sp in _source.social_platforms.num_followers) { if (sp != null) { sum += sp; }; }; return sum;",
                "ranges": [
                    {"to": 1000},
                    {"from": 1000, "to": 2000},
                    {"from": 2000, "to": 3000},
                    {"from": 3000, "to": 5000},
                    {"from": 5000, "to": 10000},
                    {"from": 10000, "to": 20000},
                    {"from": 20000, "to": 50000},
                    {"from": 50000, "to": 75000},
                    {"from": 75000, "to": 100000},
                    {"from": 100000, "to": 1000000},
                    {"from": 1000000, "to": 10000000},
                    {"from": 10000000, "to": 100000000},
                    {"from": 100000000},
                ]
            }
        }
    }
    query['query']['filtered']['query']['bool']['should'][0]['has_child']['min_children'] = min_satisfying_posts

    # print json.dumps(query, indent=4)

    # getting number of influencers in total
    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    # if rq.status_code == 200:
    resp = rq.json()
    # print json.dumps(resp, indent=4)
    total = resp.get("hits", {}).get("total", 0)

    # getting results from aggregations
    for bucket in resp.get('aggregations', {}).get('followers_ranges', {}).get('buckets', []):
        key = ' - '.join([str(bucket.get('from', '')), str(bucket.get('to', ''))])
        distr_by_quality[key] = bucket.get('doc_count', 0)

    return total, distr_by_quality


# TODO: Some old queries were used for Ralph Lauren
def helper_post_platform_stats(condition=[],
                               group_concatenator='or',
                               concatenator='or'):
    """
    Counts quantity of posts by platforms

    :param condition: this is a list of groups (list) that contain lists of pair field/keyword values, for example:
            [[['post_content', 'ralphlauren'],['post_content', 'ralph lauren']],
             [['post_content', 'running'],['post_content', 'j.crew']]]
    :param group_concatenator: determines logic between groups, can be any of ['or', 'and_same', 'and_across']
    :param concatenator: determines logic inside groups, can be any of ['or', 'and']
    :return:
    """
    # Converting input data...
    parameters = {
        'concatenator': concatenator,
        'group_concatenator': group_concatenator,
        # 'post_keywords': condition
    }

    groups = []
    keywords = []
    keywords_types = []
    grp_ctr = 0
    for grp in condition:
        for key_value in grp:
            keywords_type = key_value[0]
            keyword = key_value[1]
            groups.append(grp_ctr)
            keywords.append(keyword)
            keywords_types.append(keywords_type)
        grp_ctr += 1

    parameters['keyword'] = keywords
    parameters['keyword_types'] = keywords_types
    parameters['groups'] = groups
    parameters['and_or_filter_on'] = True
    parameters['type'] = 'all'

    # preparing ES parameters
    index_name = ELASTICSEARCH_INDEX
    endpoint = "/%s/post/_search" % index_name
    url = ELASTICSEARCH_URL

    # # building base query for influencer
    # TODO: need to be adapted for new flattened schema
    query = es_post_query_builder_v2(parameters, page=0, page_size=1)

    query['aggs'] = {
        "platform_counts": {
            "terms": {
                "field": "platform_name",
                "size": 20
            }
        }
    }

    # getting number of influencers in total
    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    # if rq.status_code == 200:
    resp = rq.json()
    total = resp.get("hits", {}).get("total", 0)
    # print json.dumps(resp, indent=4)

    platform_counts = {}

    # getting results from aggregations
    for bucket in resp.get('aggregations', {}).get('platform_counts', {}).get('buckets', []):
        platform_counts[bucket['key']] = bucket['doc_count']

    return total, platform_counts

# TODO: Some old queries were used for Ralph Lauren
def helper_productshelfmap_info(condition=[],
                                group_concatenator='or',
                                concatenator='or',
                                min_satisfying_posts=1,
                                limit=None):
    """
    Counts distributions of influencers by conditions across brand domains, affilliate links, categories (cat1 only).

    :param condition: this is a list of groups (list) that contain lists of pair field/keyword values, for example:
            [[['post_content', 'ralphlauren'],['post_content', 'ralph lauren']],
             [['post_content', 'running'],['post_content', 'j.crew']]]
    :param group_concatenator: determines logic between groups, can be any of ['or', 'and_same', 'and_across']
    :param concatenator: determines logic inside groups, can be any of ['or', 'and']
    :return:
    """
    # Converting input data...
    parameters = {
        'concatenator': concatenator,
        'group_concatenator': group_concatenator,
        # 'post_keywords': condition
    }

    groups = []
    keywords = []
    keywords_types = []
    grp_ctr = 0
    for grp in condition:
        for key_value in grp:
            keywords_type = key_value[0]
            keyword = key_value[1]
            groups.append(grp_ctr)
            keywords.append(keyword)
            keywords_types.append(keywords_type)
        grp_ctr += 1

    parameters['keyword'] = keywords
    parameters['keyword_types'] = keywords_types
    parameters['groups'] = groups
    parameters['and_or_filter_on'] = True
    parameters['type'] = 'all'

    # Part 1. Getting ids of influencers for our conditions. Doing that in pages by 500 ids.
    # preparing ES parameters
    index_name = ELASTICSEARCH_INDEX
    endpoint = "/%s/influencer/_search" % index_name
    url = ELASTICSEARCH_URL

    # building base query for influencer
    # TODO: need to be adapted for new flattened schema
    query = es_influencer_query_builder_v2(parameters, 1, page=0)

    query['query']['filtered']['query']['bool']['should'][0]['has_child']['min_children'] = min_satisfying_posts
    # getting number of influencers in total
    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    resp = rq.json()
    total = resp.get("hits", {}).get("total", 0)
    if total == 0:
        return 0

    print ('Fetching ids of %s influencers...' % total)

    influencer_ids = []
    for p in range(0, total/500+1):
        print('Fetching page %d' % p)
        query = es_influencer_query_builder_v2(parameters, 500, p)
        rq = make_es_get_request(
            es_url=url + endpoint,
            es_query_string=json.dumps(query)
        )

        resp = rq.json()
        for i in resp.get("hits", {}).get("hits", []):
            inf_id = i.get("_id")
            if inf_id:
                influencer_ids.append(inf_id)

    # print('Fetched %s influencers id, total was %s.' % (len(influencer_ids), total))

    # Part 2.
    # Show distribution of these productmodelshelfmaps based off of their brand
    # domain names. ProductModelShelfMap->ProductModel->Brand
    # Show how many had an affiliate link. ProductModelShelfMap->affiliate_prod_link.
    # Distribution of affiliate links: rstyle.me: 45% of products, shopstyle.com: 30% or products.
    # Distribution of product categories: ProductModelShelfMap->ProductModel->{cat1, cat2, cat3}.
    # So, output should be: 'shirts': 30% of products, 'pants': 20% of products.

    total_products, total_with_affiliates, sorted_brand_domains, affiliate_links, categories = find_product_relevant_info(influencer_ids, limit=limit)

    return total, total_products, total_with_affiliates, sorted_brand_domains, affiliate_links, categories


# TODO: Some old queries were used for Ralph Lauren
def helper_brand_info(condition=[],
                      group_concatenator='or',
                      concatenator='or',
                      min_satisfying_posts=5):
    """


    :param condition: this is a list of groups (list) that contain lists of pair field/keyword values, for example:
            [[['post_content', 'ralphlauren'],['post_content', 'ralph lauren']],
             [['post_content', 'running'],['post_content', 'j.crew']]]
    :param group_concatenator: determines logic between groups, can be any of ['or', 'and_same', 'and_across']
    :param concatenator: determines logic inside groups, can be any of ['or', 'and']
    :param min_satisfying_posts: determines what minimum number of matching post influencer should have to be
            taken into account
    :return: total - number of total documents of matched influencers, brands_distribution - list of brands/counts
    """

    # Converting input data...
    parameters = {
        'concatenator': concatenator,
        'group_concatenator': group_concatenator,
        # 'post_keywords': condition
    }

    groups = []
    keywords = []
    keywords_types = []
    grp_ctr = 0
    for grp in condition:
        for key_value in grp:
            keywords_type = key_value[0]
            keyword = key_value[1]
            groups.append(grp_ctr)
            keywords.append(keyword)
            keywords_types.append(keywords_type)
        grp_ctr += 1

    parameters['keyword'] = keywords
    parameters['keyword_types'] = keywords_types
    parameters['groups'] = groups
    parameters['and_or_filter_on'] = True
    parameters['type'] = 'all'

    # Part 1. Getting ids of influencers for our conditions. Doing that in pages by 500 ids.
    # preparing ES parameters
    index_name = ELASTICSEARCH_INDEX
    endpoint = "/%s/post/_search" % index_name
    url = ELASTICSEARCH_URL

    # building base query for post
    # TODO: need to be adapted for new flattened schema
    query = es_post_query_builder_v2(parameters, page_size=1, page=0)

    # modifying it
    bool_part = deepcopy(query['query']['filtered']['query']['bool'])

    query['query']['filtered']['query']['bool'] = {
        "must": [
            {
                "range": {
                    "create_date": {
                        "lte": "now"
                    }
                }
            },
            {
                "has_parent": {
                    "parent_type": "influencer",
                    "score_mode": "score",
                    "query": {
                        "has_child": {
                            "child_type": "post",
                            "score_mode": "none",
                            "min_children": min_satisfying_posts,
                            "query": {
                                "bool": bool_part
                            }
                        }
                    }
                }
            }
        ]
    }

    query.pop('highlight')

    query['aggs'] = {
        "brand_domains_counts": {
            "terms": {
                "field": "brand_domains",
                "size": 100
            }
        }
    }

    # print json.dumps(query, indent=4)
    # getting number of posts in total
    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    resp = rq.json()
    total = resp.get("hits", {}).get("total", 0)

    # print json.dumps(resp, indent=4)

    brands_distribution = []
    # getting results from aggregations
    for bucket in resp.get('aggregations', {}).get('brand_domains_counts', {}).get('buckets', []):
        brands_distribution.append( (bucket['key'], bucket['doc_count']) )

    return total, brands_distribution


# TODO: Some old queries were used for Ralph Lauren
def find_product_relevant_info(influencer_ids, pmsms=None, limit=None):

    from debra.models import ProductModelShelfMap
    from xpathscraper import utils
    print(' * Fetching data of ProductModelShelfMaps from %d influencers' % len(influencer_ids))

    # quantity of encountered brand domains
    brand_domains_qty = {}

    # quantity of encountered affiliate links
    affiliate_links = {}

    # quantity of encountered categories in cat1
    categories = {}

    # total count of influencers with affiliates
    total_with_affiliates = 0
    total_products = 0
    if limit:
        influencer_ids = influencer_ids[:limit]

    for inf_id in influencer_ids:
        #print(' * Ok, fetching pmsms for %s' % inf_id)
        if pmsms:
            productmodelshelfmaps = pmsms.filter(influencer__id=inf_id)
        else:
            productmodelshelfmaps = ProductModelShelfMap.objects.filter(influencer__id=inf_id)

        productmodelshelfmaps = productmodelshelfmaps.prefetch_related('product_model__brand')
        productmodelshelfmaps = productmodelshelfmaps.filter(shelf__name__iexact='Products from my blog')
        # print(' * Starting performing data of ProductModelShelfMaps...')
        for pmsm in productmodelshelfmaps:
            total_products += 1
            # print(' * performing map...')
            brand_domain = pmsm.product_model.brand.domain_name
            if brand_domain in brand_domains_qty:
                brand_domains_qty[brand_domain] += 1
            else:
                brand_domains_qty[brand_domain] = 1

            affiliate_link = pmsm.affiliate_prod_link
            if affiliate_link is not None:
                total_with_affiliates += 1
                affiliate_link_network = utils.domain_from_url(affiliate_link)
                if affiliate_link_network in affiliate_links:
                    affiliate_links[affiliate_link_network] += 1
                else:
                    affiliate_links[affiliate_link_network] = 1

            category = pmsm.product_model.cat1
            if category is not None:
                if category in categories:
                    categories[category] += 1
                else:
                    categories[category] = 1

    sorted_brand_domains_qty = sorted(brand_domains_qty.items(), key=operator.itemgetter(1), reverse=True)
    sorted_brand_domains = []
    # converting values to percents
    for item in sorted_brand_domains_qty:
        sorted_brand_domains.append((item[0], item[1] ))#(item[1]*100/len(sorted_brand_domains_qty))))
    sorted_brand_domains_qty = None

    affiliate_links_sorted = sorted(affiliate_links.items(), key=operator.itemgetter(1), reverse=True)
    affiliate_links = []
    # converting values to percents
    for item in affiliate_links_sorted:
        affiliate_links.append((item[0], item[1])) #(item[1]*100/len(affiliate_links_sorted))))
    affiliate_links_sorted = None

    categories_sorted = sorted(categories.items(), key=operator.itemgetter(1), reverse=True)
    categories = []
    # converting values to percents
    for item in categories_sorted:
        categories.append((item[0], item[1])) #(item[1]*100/len(categories_sorted))))
    categories_sorted = None

    return total_products, total_with_affiliates, sorted_brand_domains, affiliate_links, categories


# TODO: Some old queries were used for Ralph Lauren
def find_product_info_for_brand(brand_name=None, product_name=None, designer_name=None, domain_name=None, start_date=None):
    """
    brand_name is the name of the brand: e.g., 'ralph lauren'
    product_name is a substring for name of the product:
    designer name is a substring for product.designer_name
    domain_name is the domain of the brand we want to search: 'ralphlauren'
    """
    from debra.models import ProductModelShelfMap
    pmsm = ProductModelShelfMap.objects.none()

    if brand_name:
        pmsm_brand_name = ProductModelShelfMap.objects.filter(product_model__brand__name__icontains=brand_name)
        pmsm |= pmsm_brand_name
    if product_name:
        pmsm_product_name = ProductModelShelfMap.objects.filter(product_model__name__icontains=product_name)
        pmsm |= pmsm_product_name
    if designer_name:
        pmsm_designer_name = ProductModelShelfMap.objects.filter(product_model__designer_name__icontains=designer_name)
        pmsm |= pmsm_designer_name
    if domain_name:
        pmsm_brand_domain = ProductModelShelfMap.objects.filter(product_model__prod_url__icontains=domain_name)
        pmsm |= pmsm_brand_domain

    if start_date:
        pmsm = pmsm.filter(added_datetime__gte=start_date)

    inf_ids = set(list(pmsm.values_list('influencer__id', flat=True)))

    print("* Got %d PMSM's and %d Influencers" % (pmsm.count(), len(inf_ids)))

    return find_product_relevant_info(inf_ids, pmsm)


def find_product_mentions_time_series(product_url, start_date):
    """
    This finds the mention counts for the given product_url from the start_date
    """
    from debra.models import ProductModelShelfMap
    import datetime
    pmsm = ProductModelShelfMap.objects.all()

    pmsm = pmsm.filter(product_model__prod_url__icontains=product_url)

    pmsm = pmsm.filter(added_datetime__gte=start_date)

    pmsm = pmsm.prefetch_related('product_model__brand')
    pmsm = pmsm.filter(shelf__name__iexact='Products from my blog')
    print("* Starting for %s since %s" % (product_url, start_date))
    month = timedelta(days=30)
    tod = datetime.date.today()
    start = start_date
    while start <= tod:

        next = start + month
        pmsm_range = pmsm.filter(added_datetime__gte=start).filter(added_datetime__lte=next)
        print("[%s]\t[%s]\t%d\t%d\t%d" % (start, next, pmsm_range.count(), pmsm_range.distinct('post').count(), pmsm_range.distinct('post__influencer').count()))
        start = next


from collections import defaultdict
from bisect import bisect_left

# TODO: Some old queries were used for Ralph Lauren
def detect_influencers_by_keywords(keywords=None, intervals_total=None, intervals_unique=None):
    """
    This function does the following:
    a) for all "theshelf.com/artificial" influencers, check their posts and the description to see
        how many times these keywords appear
    b) check how many different keywords appear in their content? (so for example; this metric gives us a result
       like: 5 different keywords appear in a given Influencer's content).
       So this might more confidence because these are pretty unique hashtags.

    :param keywords: list of keywords to determine appropriate posts/influencers
    :param intervals_total: list of integers, depicting intervals.
        For example, if intervals are like [10,20,30] and the result_total is like
        {'inf': ['id1', 'id2'], 20: ['id3', 'id4'], 10: ['id5', 'id6'], 30: ['id7', 'id8']}
        that means that id1, id2 have total counts in range [30, inf]
        id7, id8 have total counts in range [20, 29]
        id3, id4 have total counts in range [10, 19]
        id5, id6 have total counts in range [0, 9]

    :param intervals_unique: list of integers, depicting unique intervals.
    :return:
    """

    # Need a list of keywords
    if type(keywords) is not list:
        return None

    result_total = defaultdict(list)
    result_unique = defaultdict(list)

    # no intervals to list
    if type(intervals_total) is list:

        intervals_total.sort()

        index_name = ELASTICSEARCH_INDEX
        endpoint = "/%s/influencer/_search" % index_name
        url = ELASTICSEARCH_URL

        should_block = [term_multimatch(["title", "content"], kw) for kw in keywords]

        influencer_query_json = {
            "query": {
                "filtered": {
                    "filter": {
                        "script": {
                            "script": "_source.blog_url.contains(\"theshelf.com\") && _source.blog_url.contains(\"artificial\")"
                        }
                    },
                    "query": {
                        "has_child": {
                            "score_mode": "sum",
                            "query": {
                                "function_score": {
                                    "query": {
                                        "bool": {
                                            "should": should_block
                                        }
                                    },
                                    "functions": [
                                        {
                                            "script_score": {
                                                "script": "sum = 0; for(sp in [%s]) { if (_source.content != null && _source.content.contains(sp)) { sum += 1; }; if (_source.title != null && _source.title.contains(sp)) { sum += 1; }; }; return sum;" % ','.join(["\"%s\"" % kw for kw in keywords])
                                            }
                                        }
                                    ],
                                    "boost_mode": "replace"
                                }
                            },
                            "child_type": "post"
                        }
                    }
                }
            },
            "_source": {
                "exclude": [],
                "include": [
                    "_id", "_score"
                ]
            },
            "from": 0,
            "size": 10000
        }

        # print json.dumps(influencer_query_json, indent=4)
        rq = make_es_get_request(
            es_url=url + endpoint,
            es_query_string=json.dumps(influencer_query_json)
        )

        resp = rq.json()
        total = resp.get("hits", {}).get("total", 0)
        for hit in resp.get("hits", {}).get("hits", []):
            _id = hit.get("_id", None)
            score = hit.get("_score", None)
            if score is None or score == 0:
                break

            pos = bisect_left(intervals_total, int(score))
            if pos == len(intervals_total):
                result_total['inf'].append(_id)
            else:
                result_total[intervals_total[pos]].append(_id)

    if type(intervals_unique) is list:

        intervals_unique.sort()

        index_name = ELASTICSEARCH_INDEX
        endpoint = "/%s/influencer/_search" % index_name
        url = ELASTICSEARCH_URL

        should_block = [
            {
                "function_score": {
                    "query": {
                        "has_child": {
                            "score_mode": "none",
                            "query": {
                                "bool": {
                                    "should": [
                                        {
                                            "multi_match": {
                                                "fields": [
                                                    "title",
                                                    "content"
                                                ],
                                                "type": "cross_fields",
                                                "query": kw
                                            }
                                        }
                                    ]
                                }
                            },
                            "child_type": "post"
                        }
                    },
                    "functions": [
                        {
                            "script_score": {
                                "script": "1"
                            }
                        }
                    ],
                    "boost_mode": "replace"
                }
            } for kw in keywords]

        influencer_query_json = {
            "query": {
                "filtered": {
                    "filter": {
                        "script": {
                            "script": "_source.blog_url.contains(\"theshelf.com\") && _source.blog_url.contains(\"artificial\")"
                        }
                    },
                    "query": {
                        "bool": {
                            "should": should_block,
                            "disable_coord": True
                        }
                    }
                }
            },
            "_source": {
                "exclude": [],
                "include": [
                    "_id", "_score"
                ]
            },
            "from": 0,
            "size": 10000
        }

        # print json.dumps(influencer_query_json, indent=4)
        rq = make_es_get_request(
            es_url=url + endpoint,
            es_query_string=json.dumps(influencer_query_json)
        )

        resp = rq.json()
        total = resp.get("hits", {}).get("total", 0)
        for hit in resp.get("hits", {}).get("hits", []):
            _id = hit.get("_id", None)
            score = hit.get("_score", None)
            if score is None or score == 0:
                break

            pos = bisect_left(intervals_unique, int(score))
            if pos == len(intervals_unique):
                result_unique['inf'].append(_id)
            else:
                result_unique[intervals_unique[pos]].append(_id)

    return result_total, result_unique


def test_detect_influencers():
    """
    Just a tester for a function above
    :return:
    """
    keywords = ['singaporeblogger', 'igsg', 'exploresg', 'instasg', 'vscosg', 'sgfood', 'sgtravel',
                'sgvideo', 'sgbeauty', 'sgblogger', 'lookbooksg', 'sglookbook', 'sgootd', 'wiwtsg', 'ootdindo',
                'ootdindia', 'ulzzanggirl', 'kfashion', 'asianfashion', 'ulzzangmakeup', 'tokyostyle',
                'koreanstyle', 'koreanfashion', 'japanesestyle', 'blogshopsg', 'ootdsg', 'sgfashion', 'fashionsg',
                'sgfoodblogger', 'sgfoodblog']

    intervals_unique = [ 1, 2, 3, 4, 5, 10, 15]  # [0 to 5], (5, 10], (10, 30], (30, +inf]
    intervals_total = [10, 20, 30]  # [0 to 10], (10, 20], (20, 30], (30, +inf]

    result_total, result_unique = detect_influencers_by_keywords(keywords, intervals_total, intervals_unique)
    print('Result total: %s' % result_total)
    print('Result unique: %s' % result_unique)


# helper method, was used for some urgent need
def update_influencer_old_show_on_search(inf_id, new_old_show_on_search=False):
    """
    Helper function to update Influencer's old_show_on_search field and applying that changes in ES index.
    :param inf:
    :param new_old_show_on_search:
    :return:
    """

    from debra.models import Influencer

    try:
        inf = Influencer.objects.get(id=inf_id)

        inf.old_show_on_search = new_old_show_on_search
        inf.save()

        # updating it in ES immediately
        endpoint = "/%s/influencer/%s/_update" % (ELASTICSEARCH_INDEX, inf.id)
        url = ELASTICSEARCH_URL

        json_query = {
            "doc": {
                "old_show_on_search": inf.old_show_on_search
            }
        }
        rq = make_es_get_request(
            es_url=url + endpoint,
            es_query_string=json.dumps(json_query)
        )

        # print('Result: %s : %s' % (rq.status_code, rq.content))
        return rq.status_code == 200
    except Influencer.DoesNotExist:
        return None

# urgent data remover, can be usable
def remove_data_from_index():
    """
    Removing Influencers and their correesponding data from ES index who have
    validated_on__isnull=False and show_on_search!=True
    :return:
    """

    from debra.models import Influencer
    to_remove = Influencer.objects.filter(
        validated_on__isnull=False,
    ).exclude(
        show_on_search=True
    ).values_list(
        'id', flat=True
    ).order_by(
        'id'
    )

    influencer_index_url = "%s/%s/influencer/_query" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)
    post_index_url = "%s/%s/post/_query" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)
    product_index_url = "%s/%s/product/_query" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)
    is_index_url = "%s/%s/influencer_score/_query" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)

    chunk_length = 1000

    ctr = 0

    for chunk_num in range(0, (len(to_remove) / chunk_length + (0 if len(to_remove) % chunk_length == 0 else 1) )):
        t = time.time()
        inf_ids = to_remove[chunk_num*chunk_length:(chunk_num+1)*chunk_length]

        # deleting postinteractions
        is_query = {
            "query": {
                "filtered": {
                    "filter": {
                        "terms": {
                            "_parent": inf_ids
                        }
                    },
                    "query": {
                        "match_all": {}
                    }
                }
            }
        }
        rq1 = make_es_delete_request(
            es_url=is_index_url,
            es_query_string=json.dumps(is_query)
        )

        # deleting products

        products_query = {
            "query": {
                "filtered": {
                    "filter": {
                        "terms": {
                            "influencer_id": inf_ids
                        }
                    },
                    "query": {
                        "match_all": {}
                    }
                }
            }
        }

        rq2 = make_es_delete_request(
            es_url=product_index_url,
            es_query_string=json.dumps(products_query)
        )

        # deleting posts
        posts_query = {
            "query": {
                "filtered": {
                    "filter": {
                        "terms": {
                            "_parent": inf_ids
                        }
                    },
                    "query": {
                        "match_all": {}
                    }
                }
            }
        }

        rq3 = make_es_delete_request(
            es_url=post_index_url,
            es_query_string=json.dumps(posts_query)
        )

        # deleting influencers
        influencers_query = {
            "query": {
                "filtered": {
                    "filter": {
                        "terms": {
                            "_id": inf_ids
                        }
                    },
                    "query": {
                        "match_all": {}
                    }
                }
            }
        }

        rq4 = make_es_delete_request(
            es_url=influencer_index_url,
            es_query_string=json.dumps(influencers_query)
        )

        ctr += len(inf_ids)
        print('Removed %s influencers, chunk (%s...%s) statuses: (%s %s %s %s), took %s seconds' % (
            ctr,
            inf_ids[0],
            inf_ids[-1],
            rq1.status_code,
            rq2.status_code,
            rq3.status_code,
            rq4.status_code,
            (time.time() - t))
        )

    print('Done, removed %s influencers total.' % ctr)


def summarize_brands_data(brands_list=[], site_domain=None):
    """
    This script prints summary for keywords/brands

    1.Number of influencers talking about <"Too Faced" or "TooFaced" or "TooFaced.com">
    2.Number of posts
    3.Number of total products (search these keywords in
        the product.url, product.brand.domain_name, product.brand.name, product.name, product.designer_name)
    4.Total number of Two Faced products that were linked to via an affiliate link.
        productmodelshelfmap has an affiliate_prod_url field
    5.Total number of Too Faced products that were linked to without an affiliate.
    6.What percentage of Two Faced Products were from the two Faced site... (how many.
    7.What percentage of Two Faced products were from retailers sites.Break down of which affiliate networks are
        being used on Two Faced products.Which brands are being mentioned most in conjunction with Two Faced products.

    :param brands_list:
    :return:
    """

    if not isinstance(brands_list, list) or len(brands_list) == 0:
        return

    from debra.models import ProductModel, ProductModelShelfMap
    from collections import defaultdict, OrderedDict
    from urlparse import urlparse

    # 0.
    product_ids = []
    product_inf_ids = []
    product_data = []
    brands_mentioned = []

    parameters = {
        u'keyword_types': [u'all', u'all', u'all'],
        u'and_or_filter_on': True,
        u'order_by': {u'field': u'_score', u'order': u'desc'},
        u'filters': {u'priceranges': [],
                     u'popularity': [],
                     u'comments': None,
                     u'tags': [],
                     u'gender': [],
                     u'brand': [],
                     u'engagement': None,
                     u'shares': None,
                     u'source': [],
                     u'location': [],
                     u'social': None,
                     u'activity': None,
                     u'categories': [],
                     u'likes': None},
        u'keyword': brands_list,
        u'group_concatenator': u'and_same',
        u'sub_tab': u'main_search',
        'no_artificial_blogs': True,
        u'groups': [0 for _ in brands_list],
        u'type': u'all',
        u'page': 1}

    # Part 1. Number of influencers
    index_name = ELASTICSEARCH_INDEX
    endpoint = "/%s/influencer/_search" % index_name
    url = ELASTICSEARCH_URL

    # building base query for influencer
    # TODO: need to be adapted for new flattened schema
    query = es_influencer_query_builder_v2(parameters, page_size=1, page=0)
    query['query']['filtered']['filter'] = get_query_filter(False, True, False)

    # getting number of influencers in total
    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    resp = rq.json()
    infs_total = resp.get("hits", {}).get("total", 0)

    # Part 2. Number of posts
    index_name = ELASTICSEARCH_INDEX
    endpoint = "/%s/post/_search" % index_name
    url = ELASTICSEARCH_URL

    # building base query for influencer
    # TODO: need to be adapted for new flattened schema
    query = es_post_query_builder_v2(parameters, page=0, page_size=1)
    query['query']['filtered']['filter']['has_parent']['filter'] = get_query_filter(False, True, False)

    query['aggs'] = {
        "brand_domains_counts": {
            "terms": {
                "field": "brand_domains",
                "size": 100
            }
        }
    }

    # getting number of influencers in total
    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    resp = rq.json()
    posts_total = resp.get("hits", {}).get("total", 0)

    brands_distribution = []
    # getting results from aggregations
    for bucket in resp.get('aggregations', {}).get('brand_domains_counts', {}).get('buckets', []):
        brands_distribution.append( (bucket['key'], bucket['doc_count']) )

    # Part 3. Number of products
    index_name = ELASTICSEARCH_INDEX
    endpoint = "/%s/product/_search" % index_name
    url = ELASTICSEARCH_URL

    # building base query for influencer
    # TODO: need to be adapted for new flattened schema
    query = es_product_query_builder_v2(parameters, page=0, page_size=1)
    query['query']['filtered']['filter']['has_parent']['filter']['has_parent']['filter'] = get_query_filter(False, True, False)

    # getting number of influencers in total
    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    resp = rq.json()
    products_total = resp.get("hits", {}).get("total", 0)

    # 4, 5
    # building base query for influencer
    # TODO: need to be adapted for new flattened schema
    query = es_product_query_builder_v2(parameters, page=0, page_size=products_total)
    query['query']['filtered']['filter']['has_parent']['filter']['has_parent']['filter'] = get_query_filter(False, True, False)

    query['fields'] = ["create_date", "influencer_id"]

    rq = make_es_get_request(
        es_url=url + endpoint,
        es_query_string=json.dumps(query)
    )

    resp = rq.json()
    # print(resp)
    for h in resp.get("hits", {}).get("hits", []):
        product_ids.append(h['_id'])
        product_inf_ids.append(h['fields']['influencer_id'][0])
        product_data.append((h['_id'], h['fields']['influencer_id'][0]))

    total_affiliate = 0
    total_not_affiliate = 0

    # 6, 7
    # checking site
    retailers = defaultdict(int)

    if site_domain:
        site_domain = site_domain.lower()

    for pd in product_data:
        prod = ProductModel.objects.get(id=pd[0])
        pmsm = prod.productmodelshelfmap_set.filter(influencer_id=pd[1]).order_by('-added_datetime')
        if pmsm.count() > 0:
            pmsm = pmsm[0]
            if pmsm.affiliate_prod_link is None:
                total_not_affiliate += 1
            else:
                total_affiliate += 1

        if site_domain:
            if site_domain in prod.prod_url.lower():
                retailers[site_domain] += 1
            else:
                retailers[urlparse(prod.prod_url).netloc] += 1

    print('%s Influencers found for %s' % (infs_total, brands_list))
    print('%s Posts found for %s' % (posts_total, brands_list))
    print('%s Products found for %s' % (products_total, brands_list))
    # print('Products ids: %s' % product_ids)

    print('%s Products from affiliates' % total_affiliate)
    print('%s Products not from affiliates' % total_not_affiliate)

    if site_domain:
        retailers_self_ctr = retailers.get(site_domain, 0)
        retailers_other_ctr = sum([v for k, v in retailers.items() if k != site_domain])
        print(' RETAILERS:')
        for k, v in sorted(retailers.items(), reverse=True):
            print("    %s : %s ( %s percent)" % (k, v, (v * 100 / (retailers_self_ctr + retailers_other_ctr))))

    print("Brands mentioned in conjunction:")
    for bd in brands_distribution:
        print("    %s : %s mentions" % (bd[0], bd[1]))


def get_posts_total_by_keywords(influencer_id=None, keywords_list=None):
    """
    fetches total number of posts for influencer.

    :param influencer_id:
    :param keywords_list:
    :return:
    """
    if influencer_id is None or keywords_list is None or len(keywords_list) == 0:
        return None

    parameters = {}
    parameters['keyword_types'] = ['all' for k in keywords_list]
    parameters['keyword'] = [k for k in keywords_list]
    parameters['influencer_ids'] = [str(influencer_id)]
    parameters['order_by'] = {u'field': u'_score', u'order': u'desc'}

    print parameters
    _, _, total_posts = es_post_query_runner_v2(parameters,1,60)

    print "Got a total of %d posts" % total_posts
    return total_posts



def explain_detailed_age_dist_for_inf(influencers=None):
    """
    Explains detailed age distribution for influencer

    :param influencer_id:
    :return:
    """
    if influencers is None:
        return None

    from debra.classification_data import influencer_age_groups_dict

    for inf in influencers:

        print(u'INFLUENCER: Id: %s Name: %r Blog name: %r' % (inf.id, inf.name, inf.blogname))

        for group_name, group_keywords in influencer_age_groups_dict.items():

            print(u'AGE GROUP: %s' % group_name)
            keywords_stats = {}

            for keyword in group_keywords:

                total = get_posts_total_by_keywords(inf.id, [keyword,])
                if total is None:
                    total = 0

                if total > 0:
                    keywords_stats[keyword] = total

            print(u'TOTAL POSTS: %s' % get_posts_total_by_keywords(inf.id, group_keywords))
            print(u'TOTAL WORDS: %s' % len(keywords_stats))
            print(u'PERCENT: %s percents' % getattr(inf, "dist_age_%s" % group_name))
            # print(u'WORDS: %s' % u', '.join(keywords_stats.keys()))
            print(u'WORDS: %s' % keywords_stats)
            print(u'')

    return


def brandjobpost_posts_to_collections(campaign_ids, print_comments=False):
    """
    find all BrandJobPost objects in the DB
    find all mentions_required and hashtags_required fields in those objects (they could be comma separated and have # or @ in front of them, we will need to strip them)
    then for each such job postobject, find influencers (job.candidates.filter(campaign_stage=6).values_list('mailbox__influencer'))
    this will give you influencers, find their ids, the ES search should be limited to all posts from only these influencers
    and posts date should be between job.start_date and job.end_date

    Asana: https://app.asana.com/0/42664940909123/102912414897017

    :return:
    """
    from debra.models import BrandJobPost, InfluencerJobMapping, Contract, Posts, Platform, Influencer
    from social_discovery.blog_discovery import queryset_iterator
    from urlparse import urlparse
    from debra.brand_helpers import connect_url_to_post

    from hanna import import_from_blog_post
    from masuka import image_manipulator

    # brand_job_posts = BrandJobPost.objects.all()

    if type(campaign_ids) == int:
        campaign_ids = [campaign_ids]

    brand_job_posts = BrandJobPost.objects.filter(id__in=campaign_ids)

    index_name = ELASTICSEARCH_INDEX
    endpoint = "/%s/post/_search" % index_name
    url = ELASTICSEARCH_URL

    # all_post_ids = []

    # this list will have list of dicts like
    # {"id": 12345, "cause": "ES match: %s"}
    # all_found_post_list = []
    all_found_posts_dict = {}

    for bjp in queryset_iterator(brand_job_posts):

        if print_comments:
            print('Performing BrandJobPost with id: %s' % bjp.id)

        # Initial data
        inf_ids = list(bjp.candidates.filter(campaign_stage__gte=3).values_list('mailbox__influencer__id', flat=True))
        inf_ids = [iid for iid in inf_ids if iid is not None]  # stripping possible Nones

        # We assume that the list of hashtags and mentions are space separated
        # So, if they are comma separated, we first replace ',' by space
        hl = bjp.hashtags_required.replace(',', ' ') if bjp.hashtags_required else ''
        ml = bjp.mentions_required.replace(',', ' ') if bjp.mentions_required else ''

        hashtags_lst = [ht.lower().replace(u'#', u'').strip() for ht in hl.split()] + [ht.lower().strip() for ht in hl.split()]
        mentions_lst = [mr.lower().replace(u'@', u'').strip() for mr in ml.split()] + [mr.lower().strip() for mr in ml.split()]

        # ERROR HANDLING: if a customer enters these hashtags 'ad' or 'sponsored' by mistake, we strip them out here
        if 'ad' in hashtags_lst:
            hashtags_lst.remove('ad')
        if '#ad' in hashtags_lst:
            hashtags_lst.remove('#ad')
        if 'sponsored' in hashtags_lst:
            hashtags_lst.remove('sponsored')
        if '#sponsored' in hashtags_lst:
            hashtags_lst.remove('#sponsored')

        # we should only search for hashtags or mentions and not the client name or client urls
        words = hashtags_lst + mentions_lst #+ [bjp.client_url.strip(), bjp.client_name.strip()]

        # try:
        #     url_short_domain = urlparse(bjp.client_url).netloc
        #     if url_short_domain.startswith('www.'):
        #         url_short_domain = url_short_domain[4:]
        #     words = words + [url_short_domain.strip(), ]
        # except:
        #     pass

        clickmeter_handler = clickmeter.ClickMeterCampaignLinksHandler(
            clickmeter_api, bjp,
            # TODO: if we don't want to check for tracking pixels,
            # then there's no reason to fetch their data from API
            include_pixels=False)

        # words to search from contract
        trackings = {}
        contracts = Contract.objects.filter(
            influencerjobmapping__mailbox__influencer__in=inf_ids,
            influencerjobmapping__job=bjp
        )

        for contract in contracts:
            try:
                entry = filter(None, map(
                    clickmeter_handler.datapoint_tracking_codes.get,
                    map(int, filter(None, itertools.chain(
                        clickmeter_handler.get_contract_product_links(contract),
                        [contract.tracking_brand_link],
                    )))
                ))
                if print_comments:
                    print('Entry: %s' % entry)

                if len(entry) > 0:
                    # entry = u" ".join(entry)
                    trackings[contract.influencerjobmapping.mailbox.influencer_id] = entry
                    if print_comments:
                        print('Inf: %s' % contract.influencerjobmapping.mailbox.influencer_id)
            except Exception as e:
                logging.error(e)

        date_start = bjp.date_start #- timedelta(days=7)
        date_end = bjp.date_end #+ timedelta(days=14)

        short_client_domain = None
        try:
            client_domain = urlparse(bjp.client_url).netloc
            if client_domain is not None and client_domain.startswith('www.') and len(client_domain) > 4:
                short_client_domain = client_domain[4:]
            elif client_domain is not None and not client_domain.startswith('www.'):
                short_client_domain = 'www.%s' % client_domain
        except:
            client_domain = None

        if print_comments:
            print('Influencers: %s' % inf_ids)
            print('Hashtags: %s' % hashtags_lst)
            print('Mentions: %s' % mentions_lst)
            print('Client url: %s' % bjp.client_url)
            print('Client domain: %s' % client_domain)
            print('Client name: %s' % bjp.client_name)
            print('Words: %s' % words)
            print('Date start: %s' % date_start)
            print('Date end: %s' % date_end)

        if len(inf_ids) > 0 and len(words) > 0:

            total = None
            page = 0
            page_size = 1000

            # post_ids = []
            found_post_list = []
            found_posts_dict = {}

            # Remaking for new mapping
            while total is None or len(found_posts_dict.keys()) < total:

                if print_comments:
                    print('Len: %s' % len(found_posts_dict.keys()))

                # ES query: find all posts of these influencers within this datetime
                es_query = {
                    "fields": ["_id"],

                    "sort": [
                        {
                            "create_date": {
                                "order": "desc"
                            }
                        },
                        {
                            "_score": {
                                "order": "desc"
                            }
                        }
                    ],

                    "query": {
                        "filtered": {
                            "filter": {
                                "bool": {
                                    "must": [
                                        {
                                            "terms": {
                                                "influencer.id": inf_ids
                                            }
                                        }
                                    ]
                                }
                            },
                            "query": {
                                "bool": {
                                    "must": term_range(
                                        "create_date",
                                        date_start.strftime("%Y-%m-%dT%H:%M:%S.000000"),
                                        date_end.strftime("%Y-%m-%dT%H:%M:%S.999999")
                                    ),
                                    "should": [
                                    ],
                                    "minimum_should_match": 1
                                }
                            }
                        }
                    },
                    "highlight": {
                        "fields": {
                            "content": {"number_of_fragments": 1, "fragment_size": 1},
                            "title": {"number_of_fragments": 1, "fragment_size": 1},
                            "brands": {"number_of_fragments": 1, "fragment_size": 1},
                            "brand_domains": {"number_of_fragments": 1, "fragment_size": 1},
                            "content_hashtags": {"number_of_fragments": 1, "fragment_size": 1},
                            "title_hashtags": {"number_of_fragments": 1, "fragment_size": 1},
                            "content_mentions": {"number_of_fragments": 1, "fragment_size": 1},
                            "title_mentions": {"number_of_fragments": 1, "fragment_size": 1}
                        }
                    }

                }

                for inf_id in trackings.keys():

                    inf_qry = {
                        "bool": {
                            "must": [
                                {
                                    "term": {
                                        "influencer.id": inf_id
                                    }
                                }
                            ],
                            "should": [],
                            "minimum_should_match": 1
                        }
                    }

                    content_query = [
                        term_multimatch(["title", "content"], keyword) for keyword in trackings[inf_id]
                    ]

                    if print_comments:
                        print(type(inf_qry['bool']['should']))
                        print(type(content_query))

                    if len(trackings[inf_id]) > 0:
                        inf_qry["bool"]["should"].append(content_query)

                    # es_query['query']['filtered']['query']['bool']['should'] = \
                    #     es_query['query']['filtered']['query']['bool']['should'] + inf_qry
                    es_query['query']['filtered']['query']['bool']['should'].append(inf_qry)

                hashtags_query = [
                    term_multimatch(["content_hashtags",
                                     "title_hashtags"],
                                    u"#%s" % keyword.strip()) for keyword in words
                ]

                mentions_query = [
                    term_multimatch(["content_mentions",
                                     "title_mentions"],
                                    u"@%s" % keyword.strip()) for keyword in words
                ]

                # we shouldn't search for hashtags and keywords without the # or @ in front of them
                # may lead to false positives
                # content_query = [
                #     term_multimatch(["title", "content"], keyword) for keyword in words
                # ]

                # brands_query = [term_match("product_urls", urlparse(bjp.client_url).netloc)]
                # product_urls_query = []
                # if client_domain:
                #     product_urls_query = [term_match("product_urls", client_domain)]



                inf_qry = {
                    "bool": {
                        "should": [],
                        "minimum_should_match": 1
                    }
                }

                if len(words) > 0:
                    inf_qry["bool"]["should"].append(hashtags_query)
                    inf_qry["bool"]["should"].append(mentions_query)
                    #inf_qry["bool"]["should"].append(content_query)

                # if client_domain is not None:
                #
                #     inf_qry["bool"]["should"].append(product_urls_query)
                #
                #     brands_query = [term_match("brands", client_domain)]
                #     brand_domains_query = [term_match("brand_domains", client_domain)]
                #
                #     inf_qry["bool"]["should"].append(brands_query)
                #     inf_qry["bool"]["should"].append(brand_domains_query)
                #
                # if short_client_domain is not None:
                #     inf_qry["bool"]["should"].append([term_match("product_urls", short_client_domain)])
                #     inf_qry["bool"]["should"].append([term_match("brands", short_client_domain)])
                #     inf_qry["bool"]["should"].append([term_match("brand_domains", short_client_domain)])

                es_query['query']['filtered']['query']['bool']['should'].append(inf_qry)

                es_query_str = json.dumps(es_query)
                pg_query_str = json.dumps({
                    "from": page * page_size,
                    "size": page_size,
                })

                es_query_str = pg_query_str[:-1] + ', ' + es_query_str[1:]
                if print_comments:
                    print(es_query_str)

                rq = make_es_get_request(
                    es_url=url + endpoint,
                    es_query_string=es_query_str
                )

                page += 1

                if rq.status_code == 200:
                    resp = rq.json()

                    # print(resp)

                    if total is None:
                        total = resp.get('hits', {}).get('total', -1)
                        if print_comments:
                            print('Total detected: %s' % total)

                    for hit in resp.get('hits', {}).get('hits', []):
                        if hit.get('_id') is not None:
                            pid = hit.get('_id')
                            pid = int(pid) if pid.isdigit() else pid

                            hit_field = None
                            hit_value = None

                            if hit.get('highlight') is not None and len(hit.get('highlight')) > 0:
                                highlight_dict = hit.get('highlight')
                                hit_field = highlight_dict.keys()[0]
                                hit_value = highlight_dict.get(hit_field)[0]

                            found_posts_dict[pid] = {
                                "id": pid,
                                "field": hit_field,
                                "value": hit_value,
                            }

                else:
                    if print_comments:
                        print('Status code: %s' % rq.status_code)
                    break

            # return found_posts_dict

            # II. NOW, we will fetch ALL blog posts from DB of these influencers for given time interval
            # except those found, and fetch their content with requests, to check if those posts are valid for this.

            for inf_id in inf_ids:
                if print_comments:
                    print('Fetching possible posts for influencer: %s' % inf_id)
                try:
                    tracking_codes = None

                    contract = InfluencerJobMapping.objects.get(
                        job=bjp, mailbox__influencer_id=inf_id).contract

                    if contract is not None:
                        tracking_codes = filter(None, map(
                            clickmeter_handler.datapoint_tracking_codes.get,
                            map(int, filter(None, itertools.chain(
                                clickmeter_handler.get_contract_product_links(
                                    contract),
                                [contract.tracking_brand_link,
                                    # TODO: Atul: looks like we should check only the tracking link and not the tracking pixel.. because she may have put the pixel on the home page and every post has it
                                    # contract.tracking_pixel
                                 ],
                            )))
                        ))
                        if print_comments:
                            print 'Tracking codes: {}'.format(tracking_codes)
                    if not tracking_codes:
                        print 'No Tracking codes sent to this influencer, so continuing to the next influencer'
                        continue

                    # possible posts of this influencer
                    possible_posts = Influencer.objects.get(id=inf_id).posts_set.filter(
                        create_date__gte=date_start,
                        create_date__lte=date_end,
                        platform__platform_name__in=Platform.BLOG_PLATFORMS
                    ).exclude(
                        id__in=found_posts_dict.keys()
                    ).values_list('id', 'url')

                    # if print_comments:
                    #     print('Extra possible posts: %s' % possible_posts.count())

                    for p in possible_posts:

                        # (1) First, checking
                        # post = Posts.objects.prefetch_related(
                        #     'brandinpost_set__brand',
                        #     'hashtaginpost_set',
                        #     'mentioninpost_set',
                        #     'productmodelshelfmap_set',
                        # ).select_related('influencer').get(
                        #     id=p[0]
                        # )

                        # fetching products from post if they were not fetched before
                        # if not post.products_import_completed:
                        #     if print_comments:
                        #         print('Products were not fetched from post, fetching...')
                        #     import_from_blog_post.fetch_products_from_post(
                        #         post.id, post.influencer.shelf_user.id if post.influencer.shelf_user else None
                        #     )
                        #
                        # # Now checking brand urls - if any matches given brand url
                        # if client_domain:
                        #     # if we have this brand in post - adding it.
                        #     qry_chunks = []
                        #     if client_domain:
                        #         qry_chunks.append(Q(brand__domain_name=client_domain))
                        #     if short_client_domain:
                        #         qry_chunks.append(Q(brand__domain_name=short_client_domain))
                        #
                        #     qry = None
                        #     if len(qry_chunks) > 0:
                        #         qry = qry_chunks.pop()
                        #         for item in qry_chunks:
                        #             qry |= item
                        #
                        #     if qry is not None and post.brandinpost_set.filter(qry).count() > 0 and p[0] not in found_posts_dict.keys():
                        #         if print_comments:
                        #             print('Found client domain in brands of the post %s, adding it.' % p[0])
                        #         # post_ids.append(p[0])
                        #         found_posts_dict[p[0]] = {
                        #             "id": p[0],
                        #             "field": 'post.brandinpost_set.brand.domain_name',
                        #             "value": client_domain,
                        #         }
                        #
                        #         continue
                        #
                        # # Checking hashtags
                        # if post.hashtaginpost_set.filter(hashtag__in=hashtags_lst).count() > 0 and p[0] not in found_posts_dict.keys():
                        #     if print_comments:
                        #         print('Found hashtag in hashtags of the post %s, adding it.' % p[0])
                        #     # post_ids.append(p[0])
                        #     found_posts_dict[p[0]] = {
                        #         "id": p[0],
                        #         "field": 'post.hashtaginpost_set.hashtag',
                        #         "value": hashtags_lst,
                        #     }
                        #     continue
                        #
                        # # Checking mentions
                        # if post.mentioninpost_set.filter(mention__in=mentions_lst).count() > 0 and p[0] not in found_posts_dict.keys():
                        #     if print_comments:
                        #         print('Found mention in mentions of the post %s, adding it.' % p[0])
                        #
                        #     found_posts_dict[p[0]] = {
                        #         "id": p[0],
                        #         "field": 'post.mentioninpost_set.hashtag',
                        #         "value": mentions_lst,
                        #     }
                        #
                        #     continue
                        #
                        # # Checking products
                        # # fetching all productshelfmaps with needed stuff
                        # qry_chunks = [Q(product_model__name__contains=bjp.client_name),
                        #               Q(product_model__designer_name=bjp.client_name),
                        #               Q(product_model__brand__name=bjp.client_name),
                        #               ]
                        # if client_domain:
                        #     qry_chunks.append(Q(product_model__brand__domain_name=client_domain))
                        # if short_client_domain:
                        #     qry_chunks.append(Q(product_model__brand__domain_name=short_client_domain))
                        #
                        # qry = qry_chunks.pop()
                        # for item in qry_chunks:
                        #     qry |= item
                        #
                        # pmsms = post.productmodelshelfmap_set.filter(qry)
                        # if pmsms.count() > 0 and p[0] not in found_posts_dict.keys():
                        #     if print_comments:
                        #         print('Found product model of the post %s, adding it.' % p[0])
                        #     # post_ids.append(p[0])
                        #     found_posts_dict[p[0]] = {
                        #         "id": p[0],
                        #         "field": 'post.productmodelshelfmap_set.product_model',
                        #         "value": [bjp.client_name, client_domain] if client_domain else bjp.client_name,
                        #     }
                        #
                        #     continue

                        # (2) Second, if nothing before helped, trying to fetch tracking links
                        if tracking_codes is not None:
                            r = requests.get(
                                p[1],
                                timeout=20,
                                headers={
                                    'User-Agent':
                                    "Mozilla/5.0 (Windows NT 6.1; Win64; x64; rv:46.0) Gecko/20100101 Firefox/46.0"},
                                verify=False
                            )
                            # r.raise_for_status()
                            if any(tc in r.text for tc in tracking_codes) and p[0] not in found_posts_dict.keys():
                                if print_comments:
                                    print('Found tracking stuff in post %s, adding it.' % p[0])
                                # post_ids.append(p[0])
                                found_posts_dict[p[0]] = {
                                    "id": p[0],
                                    "field": 'tracking',
                                    "value": tracking_codes,
                                }

                except Exception as e:
                    logging.error(e)

            # all_post_ids = all_post_ids + post_ids
            # all_found_post_list = all_found_post_list + found_post_list
            all_found_posts_dict.update(found_posts_dict)

            # print('Posts ids:')
            # print(len(post_ids))
            # print(post_ids[:50])

            from debra.models import Posts, PostAnalytics
            # existing_post_ids = bjp.post_collection.postanalytics_set.values_list(
            #     'post', flat=True)

            # More precise way to get participating posts
            existing_post_ids = bjp.participating_post_ids
            posts = Posts.objects.filter(
                id__in=list(set(map(int, found_posts_dict.keys())) - set(existing_post_ids)))
            print("all posts found: %r" % posts)

            # Adding posts to collection
            for post in queryset_iterator(posts):
                try:
                    if not post.post_image:
                        image_manipulator.upload_post_image(post)
                except:
                    print("Problem in extracting image from post: %r" % post)
                    pass
                post_analytics = PostAnalytics.objects.from_source(post_url=post.url, refresh=True)
                post_analytics.post = post
                post_analytics.collection = bjp.post_collection
                if post.id in found_posts_dict.keys():
                    post_analytics.info = json.dumps({
                        'hit_field': found_posts_dict.get('field'),
                        'hit_value': found_posts_dict.get('value')
                    })
                post_analytics.save()
                bjp.post_collection.add(post_analytics)
                connect_url_to_post(post_analytics.post_url, post_analytics.id)

            # plats = {}
            # total_campaign_posts = Posts.objects.filter(id__in=post_ids)
            # for p in total_campaign_posts:
            #     plats[p.platform.platform_name] = plats.get(p.platform.platform_name, 0) + 1
            #
            #     # if p.platform_name == 'Pinterest':
            #     #     print(p)
            #
            # if print_comments:
            #     print('len(plats)=%s' % len(plats))
            #     for k, v in plats.items():
            #         print('%s   %s' % (k, v))

    return all_found_posts_dict


# used to test age distributions
def get_ageless_influencers():
    """
    using ES query
    :return:
    """

    import io
    # import datetime
    from debra.models import Influencer
    from social_discovery.blog_discovery import queryset_iterator

    inf_ids = []

    es_query = {
        "sort": [
            {
                "popularity": {
                    "order": "desc"
                }
            }
        ],
        "query": {
            "filtered": {
                "filter": {
                    "match_all": {}
                },
                "query": {
                    "bool": {
                        "must_not": [
                            # {
                            #     "query_string": {
                            #         "query": "*theshelf.com\\/artificial*",
                            #         "default_operator": "AND",
                            #         "default_field": "blog_url",
                            #         "analyze_wildcard": True
                            #     }
                            # },
                            {
                                "term": {
                                    "blacklisted": True
                                }
                            },
                            {
                                "nested": {
                                    "query": {
                                        "bool": {
                                            "must": [
                                                # {
                                                #     "term": {
                                                #         "social_platforms.name": "source"
                                                #     }
                                                # },
                                                # {
                                                #     "wildcard": {
                                                #         "social_platforms.activity_level": '*brand*'
                                                #     }
                                                # }
                                            ]
                                        }
                                    },
                                    "path": "social_platforms"
                                }
                            },
                            {
                                "nested": {
                                    "query": {
                                        "bool": {
                                            "must": [
                                                {
                                                    "term": {
                                                        "social_platforms.name": "dist_age"
                                                    }
                                                },
                                                {
                                                    "range": {
                                                        "social_platforms.activity_enum": {
                                                            "gte": 0
                                                        }
                                                    }
                                                }
                                            ]
                                        }
                                    },
                                    "path": "social_platforms"
                                }
                            }
                        ],
                        "must": [
                            {
                                "term": {
                                    "old_show_on_search": True
                                }
                            }
                        ]
                    }
                }
            }
        },
        "_source": {
            "exclude": [],
            "include": [
                "_id"
            ]
        }
    }

    index_name = ELASTICSEARCH_INDEX
    endpoint = "/%s/influencer/_search" % index_name
    url = ELASTICSEARCH_URL

    for i in range(0, 8):

        es_query_str = json.dumps(es_query)
        pg_query_str = json.dumps({
            "from": i * 1000,
            "size": 1000,
        })

        es_query_str = pg_query_str[:-1] + ', ' + es_query_str[1:]

        rq = make_es_get_request(
            es_url=url + endpoint,
            es_query_string=es_query_str
        )

        if rq.status_code == 200:
            resp = rq.json()

            for hit in resp.get('hits', {}).get('hits', []):
                h = hit.get('_id')
                if h is not None and h not in inf_ids:
                    inf_ids.append(h)
        else:
            print('Status code: %s' % rq.status_code)
            break

        print('fetched %s...' % (i*1000))

    print('Fetched: %s' % len(inf_ids))

    influencers = Influencer.objects.filter(id__in=inf_ids)

    csvfile = io.open('ageless_influencers__%s.csv' % datetime.strftime(datetime.now(), '%Y-%m-%d_%H%M%S'), 'w+', encoding='utf-8')

    csvfile.write(u'Inf id\tname\tblog name\tblog url\n')

    ctr = 0
    for inf in queryset_iterator(influencers):
        csvfile.write(u'%s\t%s\t%s\t%s\n' % (
            inf.id,
            inf.name.replace('\n', '').replace('\t', '') if inf.name is not None else inf.name,
            inf.blogname.replace('\n', '').replace('\t', '') if inf.blogname is not None else inf.blogname,
            inf.blog_url.replace('\n', '').replace('\t', '') if inf.blog_url is not None else inf.blog_url)
        )

        ctr += 1
        if ctr % 100 == 0:
            print('Performed: %s' % ctr)

    csvfile.close()


def inf_indexed_posts_checker(inf_id=None):
    """
    Checks if all influencer's posts are indexed.
    Found unindexed posts are scheduled for indexing.

    :param inf_id:
    :return:

    """

    from debra.models import Influencer

    if inf_id is None:
        print('No influencer_id given')
        return None, None

    try:
        inf = Influencer.objects.get(id=inf_id)
        # print('Considering influencer: id: %s name: %r blog name: %r' % (inf.id, inf.name, inf.blogname))

        # if inf.blacklisted is True:
        #     print ('Influencer is BLACKLISTED')
        #
        # if inf.old_show_on_search is not True:
        #     print ('Influencer is NOT PRODUCTION')

        posts_db_ids = list(inf.posts_set.exclude(platform__url_not_found=True).values_list('id', flat=True))

        # print('Influencer should have %s posts indexed' % len(posts_db_ids))

        post_url = "%s/%s/post/_search?scroll=1m" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)
        scroll_url = "%s/_search/scroll?scroll=1m" % ELASTICSEARCH_URL

        indexed_posts_ids = []  # posts found indexed in ES
        not_indexed_posts_ids = []  # posts NOT found indexed in ES

        es_rq = {
            "filter": {
                "ids": {
                    "type": "post",
                    "values": posts_db_ids
                }
            },
            "size": 500,
            "from": 0,
            "_source": {
                "exclude": [],
                "include": [
                    "_id"
                ]
            }
        }

        # Populating lists
        should_request = True
        scroll_token = None
        while should_request:
            if scroll_token is None:
                rq = make_es_get_request(
                    es_url=post_url,
                    es_query_string=json.dumps(es_rq)
                )
            else:
                rq = make_es_get_request(
                    es_url=scroll_url,
                    es_query_string=scroll_token
                )

            resp = rq.json()
            scroll_token = resp.get("_scroll_id", None)
            hits = resp.get('hits', {}).get('hits', [])

            if len(hits) == 0:
                should_request = False
            else:
                for hit in hits:
                    try:
                        inf_id = int(hit.get('_id', None))
                        indexed_posts_ids.append(inf_id)
                    except:
                        pass

        # sorting
        for db_id in posts_db_ids:
            if db_id not in indexed_posts_ids:
                not_indexed_posts_ids.append(db_id)

        # print('Indexed: %s posts' % len(indexed_posts_ids))
        # print('Not indexed: %s posts' % len(not_indexed_posts_ids))

        return indexed_posts_ids, not_indexed_posts_ids

    except Influencer.DoesNotExist:
        return None, None



def fix_picless_influencers():
    """
    Receives a list of ids of all picless influencers and schedules them for reindexing.

    :param inf_id:
    :return:

    """

    # print('Influencer should have %s posts indexed' % len(posts_db_ids))

    post_url = "%s/%s/influencer/_search?scroll=1m" % (ELASTICSEARCH_URL, ELASTICSEARCH_INDEX)
    scroll_url = "%s/_search/scroll?scroll=1m" % ELASTICSEARCH_URL

    indexed_posts_ids = []  # posts found indexed in ES

    es_rq = {
        "fields": [
            "create_date"
        ],
        "query": {
            "filtered": {
                "filter": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "show_on_search": True
                                }
                            }
                        ],
                        "must_not": [
                            {
                                "nested": {
                                    "path": "social_platforms",
                                    "filter": {
                                        "bool": {
                                            "must": [
                                                {
                                                    "term": {
                                                        "social_platforms.name": "profile_pic"
                                                    }
                                                }
                                            ]
                                        }
                                    }

                                }
                            }
                        ]
                    }
                },
                "query": {
                    "match_all": {}
                }
            }
        },
        "from": 0,
        "size": 500
    }

    # Populating lists
    should_request = True
    scroll_token = None
    while should_request:
        if scroll_token is None:
            rq = make_es_get_request(
                es_url=post_url,
                es_query_string=json.dumps(es_rq)
            )
        else:
            rq = make_es_get_request(
                es_url=scroll_url,
                es_query_string=scroll_token
            )

        resp = rq.json()
        scroll_token = resp.get("_scroll_id", None)
        hits = resp.get('hits', {}).get('hits', [])

        if len(hits) == 0:
            should_request = False
        else:
            for hit in hits:
                try:
                    inf_id = int(hit.get('_id', None))
                    indexed_posts_ids.append(inf_id)
                except:
                    pass

    return indexed_posts_ids
