from __future__ import absolute_import, division, print_function, unicode_literals
from debra import db_util
from platformdatafetcher import fetchertasks


def get_blog_platforms():
    connection = db_util.connection_for_reading()
    cursor = connection.cursor()
    cursor.execute("""
                   select distinct p.id from debra_platform p inner join debra_posts ps
                    on ps.platform_id = p.id
                   where p.platform_name in ('Wordpress', 'Blogspot', 'Custom')
                   """)
    rows = cursor.fetchall()
    return [row[0] for row in rows]


def batch_platforms(platform_ids):
    batch_size = 500
    current = platform_ids
    while len(current) > batch_size:
        batch = current[:batch_size]
        current = current[batch_size:]
        yield batch
    yield current


def submit_check_social_comments(batch):
    # HACK: use the Youtube queue since it's likely empty
    fetchertasks.check_social_comments.apply_async(args=[batch],
                         queue='every_day.fetching.Youtube',
                         routing_key='every_day.fetching.Youtube')
