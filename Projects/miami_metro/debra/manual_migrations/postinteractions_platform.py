'''
A helper script that calculates the platform_id values for the largest table in the database.

The entry point is the run_update() function, which you can run in a Django shell.

It is using two worker processes, which can be configured via the Pool constructor.
'''
from __future__ import absolute_import, division, print_function, unicode_literals
from debra import db_util
from multiprocessing import Pool
import traceback


INTERACTIONS_TABLE = 'debra_postinteractions'


def get_batch(batch_size=10000):
    connection = db_util.connection_for_reading()
    cursor = connection.cursor()
    cursor.execute('SELECT post_id FROM {interactions} WHERE platform_id IS NULL LIMIT %s'.format(interactions=INTERACTIONS_TABLE),
                   [batch_size])
    post_ids = [row[0] for row in cursor.fetchall()]
    return list(set(post_ids))


def update_batch(post_ids):
    try:
        connection = db_util.connection_for_reading()
        cursor = connection.cursor()
        post_comma_string = str(tuple(post_ids))
        # PG-specific UPDATE FROM command
        cursor.execute('''
    UPDATE {interactions}
    SET platform_id = ps.platform_id
    FROM (SELECT id, platform_id FROM debra_posts WHERE id IN {post_ids}) AS ps
    WHERE post_id IN {post_ids} AND ps.id = post_id
                    '''.format(interactions=INTERACTIONS_TABLE, post_ids=post_comma_string))
    except:
        traceback.print_exc()


def run_update(batch_size=20000):
    #pool = Pool(2)
    while True:
        ids = get_batch(batch_size=batch_size)
        if not ids:
            print("Done.")
            return

        half1 = ids[:len(ids) // 2]
        half2 = ids[len(ids) // 2:]

        print('Updating interactions for {} posts.'.format(len(ids)))
        #pool.map(update_batch, [half1, half2])
        update_batch(ids)
