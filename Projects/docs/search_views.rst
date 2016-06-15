Search views
============

Influencers feed view
+++++++++++++++++++++

Searching for influencers involves few steps that might be extracted into separate helper function in future but currently there is only one view that returns influencers feed, here are steps needed to get influencers feed json:

- prepare influencers (do prefetches, select related and some general filtering, we assume that influencers who show up on search page has to have show_on_search flag set to true, existing profile pic, existing score_popularity_overall and they can not be blacklisted, it might be different for other pages)
- filter influencers - use *debra.search_helpers.filter_blogger_results* function with request and prefetched influencers as arguments (plan_name is deprecated)
- do pagination
- grab influencers page from database
- for every filtered influencer that is on current page use *derba.serializers.InfluencerSerializer* to get json-serializable dictionary
- serialize it into json string and return

Those points doesn't include any optimizations and caching nor any privilege checks which have to be performed separately.

Actual implementation includes caching (per influencer - so there is no need to load influencer from db every time, if we have its *id* then cache will return proper json-serializable dictionary). Additionaly current implementation uses mix of elastic search and database filtering so we have to combine results ourselves (which will hopefully change in near future) - so whole view is divided into 2 phases - *preflight* where we get only influencers *id*-s, do filtering and pagination and *serialization* where we look up influencers by *id* from cache or load their data from database if they are not in cache.

Query used to filter out should look like this:

.. code-block:: json

    {
        "page": 1,                          # page number
        "filters": {
            "category": ["hats"],           # category filter - show only hats
            "popularity": ["Medium"],       # popularity - only medium popularity
            "engagement": {
                "value": "",                # it will always be empty string
                "range_min": 1,             # minimal number of comments per post
                "range_max": 100            # max number of comments per post
            },
            "brand": [{                     # influencer has to have something to do with jcrew
                "text": "J.Crew",
                "value": "jcrew.com"
            }],
            "priceranges": ["Cheap"],       # influencer has to write about cheap items...
            "gender": ["Female"],           # ...and be female..
            "location": ["USA"],            # ...from USA
            "social": {
               "value": "Facebook",         # it also has to have 0-200 followers on facebook
                "range_min": 0,
                "range_max": 200
            }
        },
        "keyword":"ann",                    # its blog name has to contain "ann"
        "type":"blogname"
    }

Other feeds
+++++++++++

Other feed types are much simpler since we only have to use one of functions from debra.feeds_helpers. For example if we want to have twitter feed we would use following code:

.. code-block:: py

    def simple_twitter_feed_json(request):
        try:
            search_query = json.loads(request.body)
        except:
            search_query = {}

        data = feeds_helpers.twitter_feed_json(request)

        json_data = json.dumps(data, cls=DjangoJSONEncoder)
        return HttpResponse(json_data, content_type="application/json")

frontend sends filter type in search_query['filter'] so we can use if-s to select appropriate function. Also search_query can be modified dynamicaly in view to constraint searching (eg. results only from given brand or date range). This is example search query send by frontend:

.. code-block:: json

    {
        "filter": "blog",                   # feed type - can be on of constants from feeds_helpers with _FEED_FILTER_KEY suffix
        "pageBlog": 1,                      # each feed type will have its own pagination - feed_helpers constants with _FEED_PAGE_NO_KEY suffix
        "keyword": "ann",                   # keyword query for influencer's blogname
        "stype": "blogname",
        "filters": {                        # filters are built same as for influencers feed
            "category": ["outerwear"],
            "popularity": ["Small"],
            "engagement": {
                "value": "",
                "range_min": 1,
                "range_max": 100
            },
            "brand": [{
                "text": "Amazon",
                "value": "amazon.com"
            }],
            "priceranges": ["Mid-level"],
            "location": ["UK"],
            "gender": ["Male"],
            "social": {
                "value": "Facebook",
                "range_min": 0,
                "range_max": 1000
            }
        }
    }


Internally feed helpers use elastic search to filter data and do serialization (separate for different feed type). There is also cache for non-filtered content.

Also please note that same query can be used to obtain influencers.

Influencer details
++++++++++++++++++

There is one view which loads inflencers details - *debra.search_views.blogger_info_json*. It uses *debra.search_helpers.get_influencer_json* internally to load basic json and then if there is additional filtering needed - customizes that json.

get_influencer_json
-------------------

This function in simplest form takes influencer intance as its argument. Whole logic is divided into few steps:

- get data

First, there are database queries prepared which load influencer, its platforms, brand mentions, items and posts.

- build json

Then json with data such as number of followers for each platform, description etc. is made.

- extend json

After that more details are fetched from database to build categories chart, number of posts related to fashion chart and popularity charts.

blogger_info_json
-----------------

When influencer profile is viewed from search page where query related to brand is made, we want to filter out posts and items to be related with that brand. To do this *blogger_info_json* uses *get_influencer_json* to get basic json-serializable dictionary of influencer's details and decorates it with customized values. Basicaly it means that there is query made to elastic search to get posts and items related to brand given in query. Then original items and posts are replaced with new one - or simply mixed if influencer has not enough items or posts from given brand. Then everything is cached (per query - so if somebody in future will query influencer with details about some brand - we will have it in cache), serialized and returned to frontend.
