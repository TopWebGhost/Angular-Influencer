from __future__ import absolute_import, division, print_function, unicode_literals
from debra import db_util
from django.db.models import Q
from debra import models
from debra import constants
from platformdatafetcher import postprocessing


def to_recalculate_is_active():
    q = '''
SELECT DISTINCT i.id
FROM debra_influencer i
INNER JOIN
  (SELECT inf.id,
          max(inserted_datetime) AS last_post
   FROM debra_influencer inf
   INNER JOIN debra_platform p ON p.influencer_id = inf.id
   INNER JOIN debra_posts ps ON ps.platform_id = p.id
   WHERE p.platform_name IN ('Wordpress',
                             'Blogspot',
                             'Custom')
   GROUP BY inf.id) ips ON i.id = ips.id
WHERE ips.last_post > now() - '90 days'::interval AND
    i.is_active = 'f'::bool AND
    i.source IS NOT NULL AND
    i.blog_url IS NOT NULL
    '''
    connection = db_util.connection_for_reading()
    c = connection.cursor()
    c.execute(q)
    rows = c.fetchall()
    return [row[0] for row in rows]


def submit_tmp_submit_is_active_denormalize(batch):
    # HACK: use the Youtube queue since it's likely empty
    postprocessing.tmp_submit_is_active_denormalize.apply_async(args=[batch],
                         queue='every_day.fetching.Youtube',
                         routing_key='every_day.fetching.Youtube')


def newinfluencers():
    query = models.Influencer.objects.active_unknown().filter(
        source__isnull=False,
        blog_url__isnull=False,
        blacklisted=False,
        relevant_to_fashion__isnull=True,
    )
    return query


def batch_influencers(influencer_ids):
    batch_size = 500
    current = influencer_ids
    while len(current) > batch_size:
        batch = current[:batch_size]
        current = current[batch_size:]
        yield batch
    yield current


####################################################################


def q_influencer():
    query = models.Influencer.objects.filter(
        source__isnull=False,
        #blog_url__isnull=False,
        #blacklisted=False,
        relevant_to_fashion__isnull=False,
        #relevant_to_fashion=True,
        #is_active=True
    )

    query = query.active().filter(
        relevant_to_fashion__isnull=False,
        blacklisted=False,
        blog_url__isnull=False
    ).distinct()

    query = query.filter(
        Q(profile_pic_url__isnull=False) |
        Q(fb_url__isnull=False) |
        Q(tw_url__isnull=False) |
        Q(pin_url__isnull=False) |
        Q(insta_url__isnull=False)
    )

    query = query.exclude(show_on_search=True)
    query = query.exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_INFORMATIONS)
    query = query.exclude(validated_on__contains=constants.ADMIN_TABLE_INFLUENCER_SELF_MODIFIED)

    query = query.filter(average_num_comments_per_post__gte=2)
    query = query.exclude(blogname__iexact='PROBLEM ID')
    return query


def test_num():
    q = q_influencer()
    return q.count()
