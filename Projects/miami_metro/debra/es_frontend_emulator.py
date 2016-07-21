from .search_helpers import search_influencers, search_influencer_products, search_influencer_posts
from .search_helpers import get_searchable_influencers
from random import randrange
from .models import Influencer

''' Frontend Emulator provides an API for making the ES
queries that would be made by the frontend javascript
application.

Filters and FrontendQuery can be used independently, but
are not designed to be. The Queries object should be used
instead.

Queries builds and manages multiple queries and exposes
helper functions that reflect those found in search_helpers.py.

Examples, assuming queries = Queries():

The query that runs on initial page load:

queries.initial_page_load.search_influencers()

Find posts that belong to influnecer 12, with no other options:

queries.id_12.influencer = 12
queries.id_12.search_influencer_posts()

Create a brand filter for prada, and search influencers:

queries.prada_only.filters.brand = "prada.com"

queries.prada_only.search_influencers()

Of the found influencer, search a random influencer's products:

queries.prada_only.search_influencer_prodcts()

More examples:

queries.female_fashion.filters.categories = "fashion"
queries.female_fashion.filters.gender = "female"
queries.search_influencers()
queries.search_influencer_products()
queryes.search_influencer_fashion()


queries.influencer_99.influencer = 99
queries.influencer_99.keywords = ["running", "casual"]
queries.influencer_99.search_posts()

The following query will automatigically limit to only searchable influencers:
queries.loading_page.search_influencer_posts()
'''

class Filters(object):
    ''' Filters are the available filtering options on the front end. '''
    def __init__(self):
        self._brands = []
        self._gender = []
        self._prices = []
        self._popularity = []
        self._activity = None
        self._followers = []
        self._categories = []
        self._locations = []
        self._comments = None

    @property
    def brand(self):
        return self._brands

    @brand.setter
    def brand(self, brands):
        if type(brands) != list:
            brands = [brands]

        for brand in brands:
            self._brands.append({'value': brand})

    @property
    def gender(self):
        return self._gender

    @gender.setter
    def gender(self, genders):    
        if type(genders) != list:
            genders = [genders]

        self._genders.extend(genders)

    @property
    def price(self):
        return self._prices

    @price.setter
    def price(self, prices):
        if type(prices) != list:
            prices = [prices]

        prices = [price if price.lower() != 'medium' else 'Mid-Level' for price in prices]
        self._prices.extend(prices)

    @property
    def popularity(self):
        return self._popularity
        
    @popularity.setter
    def popularity(self, pops):
        if type(pops) != list:
            pops = [pops]

        self._popularity.extend(pops)

    @property
    def activity(self):
        return self._activity

    @activity.setter
    def activity(self, activity):
        if type(activity) != list:
            activity = [activity]

        if self._activity is None:
            self._activity = []
            
        for act in activity:
            self._activity.append({'platform': act[0], 'activity_level': act[1]})

    @property
    def followers(self):
        return self._followers

    @followers.setter
    def followers(self, followers):
        if type(followers) != list:
            followers = [followers]

        for follower in followers:
            f = {'platform': follower[0]}

            self._followers.append({'platform': follower[0],
                                    'range_min': follower[1],
                                    'range_max': follower[2]})    

    @property
    def category(self):
        return self._categories

    @category.setter
    def category(self, categories):
        if type(categories) != list:
            categories = [categories]

        self._categories.extend(categories)

    @property
    def location(self):
        return self._locations

    @location.setter
    def location(self, locations):
        if type(locations) != list:
            locations = [locations]

            self._locations.extend(locations)

    @property
    def comments(self):
        return self._comments

    @comments.setter
    def comments(self, comments):
        if type(comments) != list:
            comments = [comments]

        if self._comments is None:
            self._comments = []

        for comment in comments:
            self._comments.append({'rangee_min': comment[0], 'range_max': comment[1]})
            
    @property
    def query(self):
        return {
            'brand': self.brand,
            'engagement': self.comments[0] if self.comments else None,
            'gender': self.gender,
            'categoies': self.category,
            'location': self.location,
            'popularity': self.popularity,
            'priceranges': self.price,
            'social': self.activity[0] if self.activity else None
        }
        
class FrontendQuery(object):
    ''' FrontendQuery is an entire frontend query, as it would be received and deserialized from JSON. '''        
    def __init__(self, filters=None):
        self._keywords = None
        self._filters = Filters() if filters is None else filters
        self._order_by = {}
        self._page = 1
        self._type = None
        self._display = 'all'

        self._influencer_pool = []
        self._influencer_ids = []

    @property
    def keyword(self):
        return self._keywords

    @keyword.setter
    def keyword(self, keywords):
        if type(keywords) != list:
            keywords = [keywords]

        if self._keywords is None:
            self._keywords = keywords
        else:
            self._keywords.extend(keywords)

    @property
    def filters(self):
        return self._filters

    @property
    def page(self):
        return self._page

    @page.setter
    def page(self, page):
        self._page = page

    @property
    def type(self):
        return self._type

    @type.setter
    def type(self, _type):
        self._type = _type
        
    @property
    def display(self):
        return self._display

    @display.setter
    def display(self, display):
        self._display = display.lower()

    @property
    def query(self):
        return {
            'type': self.type,
            'page': self.page,
            'keyword': self.keyword,
            'filters': self.filters.query,
            'display': self.display
        }

    def search_influencers(self, items_per_page=60):
        return search_influencers(self.query, items_per_page)

    @property
    def influencer_pool(self):
        if not self._influencer_pool:
            if not self._influencer_ids:
                self._influencer_pool = get_searchable_influencers()
            else:
                self._influencer_pool = list(Influencer.objects.filter(
                    id__in=self._influencer_ids
                ))

        return self._influencer_pool

    @influencer_pool.setter
    def influencer_pool(self, pool):
        if type(pool) != list:
            pool = [pool]

        for p in pool:
            try:
                p = int(p)
                self._influencer_ids.append(p)
            except:
                self._influencer_pool.append(p)

    @property
    def influencer(self):
        return self.influencer_pool[randrange(0, len(self.influencer_pool))]

    @influencer.setter
    def influencer(self, influencer):
        if type(influencer) == Influencer:
            self.influencer_pool = influencer
        else:
            self.influencer_id = influencer

    @property
    def influencer_id(self):
        return self.influencer.id

    @influencer_id.setter
    def influencer_id(self, id):
        self.influencer = Influencer.objects.get(pk=id)

    def search_influencer_products(self, influencer=None, items_per_page=25):
        return search_influencer_products(
            influencer if influencer else self.influencer,
            self.query,
            items_per_page
        )

    def search_influencer_posts(self, influencer=None, items_per_page=12):
        return search_influencer_posts(
            influencer if influencer else self.influencer,
            self.query,
            items_per_page
        )
        
class Queries(object):
    def __init__(self):
        self.__name = None

    def __getattr__(self, attr):
        if not hasattr(self, attr):
            setattr(self, attr, FrontendQuery())
        return getattr(self, attr)

    @property
    def all(self):
        return [(q, getattr(self, q)) for q in dir(self) if \
                not q.startswith('_') and q not in ('all') and \
                type(getattr(self, q)) == FrontendQuery]


    def include(self, queries, name='included'):
        for key, query in queries.all:
            setattr(self, name + '_' + key, query)

    name = property(lambda self: self.__name,
            lambda self, value: setattr(self, '_Queries__name',
                value if type(value) == FrontendQuery else FrontendQuery(value)))
    
