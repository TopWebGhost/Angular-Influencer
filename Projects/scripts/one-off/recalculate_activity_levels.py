from __future__ import absolute_import, division, print_function, unicode_literals
from debra import db_util
from platformdatafetcher import fetchertasks


def get_all_platforms():
    connection = db_util.connection_for_reading()
    cursor = connection.cursor()
    cursor.execute("select p.id from debra_platform as p")
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


def submit_tmp_calculate_platform_activity_levels(batch):
    # HACK: use the Youtube queue since it's likely empty
    fetchertasks.tmp_calculate_platform_activity_levels.apply_async(args=[batch],
                         queue='every_day.fetching.Youtube',
                         routing_key='every_day.fetching.Youtube')
