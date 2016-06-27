from django.core.management.base import BaseCommand
from django.db.models.query_utils import Q
from debra import admin_helpers
from debra.models import Influencer


import gc


class Command(BaseCommand):

    help = 'Cleans up ask.fm profiles'

    @classmethod
    def handle(cls, *args, **options):

        # fetching our new Influencers
        influencers = Influencer.objects.filter(Q(fb_url__icontains='facebook.com/askfmpage')
                                                | Q(tw_url__icontains='twitter.com/ask_fm')
                                                | Q(insta_url__icontains='instagram.com/ask_fm')
                                                | Q(insta_url__icontains='instagram.com/askfm')
                                                | Q(blog_url__startswith='http://ask.fm/')
                                                )
        influencers = influencers.filter(instagram_profile__isnull=False)
        inf_queryset = queryset_iterator(influencers)

        ctr = 0
        print('Started performing ask.fm Influencers (total: %s)...' % influencers.count())
        for inf in inf_queryset:
            blog_url_is_changed = False
            fb_is_changed = False
            tw_is_changed = False
            insta_is_changed = False

            if inf.blog_url is not None and inf.blog_url.startswith('http://ask.fm/'):
                blog_url_is_changed = True
                inf.blog_url = 'http://theshelf.com/artificial' + inf.blog_url
            if inf.fb_url is not None and 'facebook.com/askfmpage' in inf.fb_url:
                inf.fb_url = None
                fb_is_changed = True
            if inf.tw_url is not None and 'twitter.com/ask_fm' in inf.tw_url:
                inf.tw_url = None
                tw_is_changed = True
            if inf.insta_url is not None and ('instagram.com/ask_fm' in inf.insta_url or 'instagram.com/askfm' in inf.insta_url):
                inf.insta_url = None
                if inf.instagram_profile.count() == 1:
                    inf.insta_url = 'http://instagram.com/' + inf.instagram_profile.all()[0].username
                insta_is_changed = True

            if fb_is_changed or tw_is_changed or insta_is_changed or blog_url_is_changed:
                inf.description = None
                inf.save()
                if blog_url_is_changed:
                    admin_helpers.handle_blog_url_change(inf, inf.blog_url)
                if fb_is_changed:
                    admin_helpers.handle_social_handle_updates(inf, 'fb_url', inf.fb_url)
                if tw_is_changed:
                    admin_helpers.handle_social_handle_updates(inf, 'tw_url', inf.tw_url)
                if insta_is_changed:
                    admin_helpers.handle_social_handle_updates(inf, 'insta_url', inf.insta_url)

            # Increasing counter
            ctr += 1
            if ctr % 100 == 0:
                print('%s influencers performed' % ctr)

        print('Total: %s' % ctr)


# https://djangosnippets.org/snippets/1949/
def queryset_iterator(queryset, chunksize=1000):
    """
    Iterate over a Django Queryset ordered by the primary key

    This method loads a maximum of chunksize (default: 1000) rows in it's
    memory at the same time while django normally would load all rows in it's
    memory. Using the iterator() method only causes it to not preload all the
    classes.

    Note that the implementation of the iterator does not support ordered query sets.
    """
    pk = 0
    try:
        last_pk = queryset.order_by('-pk')[0].pk
        queryset = queryset.order_by('pk')
        while pk < last_pk:
            for row in queryset.filter(pk__gt=pk)[:chunksize]:
                pk = row.pk
                yield row
            gc.collect()
    except IndexError:
        gc.collect()