'''
A helper script that calculates the show_on_search values for the largest table in the database.

The entry point is the run_update() function, which you can run in a Django shell.

It is using two worker processes, which can be configured via the Pool constructor.
'''
from __future__ import absolute_import, division, print_function, unicode_literals
from debra import db_util
#from multiprocessing import Pool
import traceback
import time


INFLUENCERS_TABLE = 'debra_influencer'
POSTS_TABLE = 'debra_posts'


def get_influencer_batch():
    '''
    previously prepared influencers as:

create table tmp_influencer_show_on_search as select id, show_on_search from debra_influencer where show_on_search is not null;
create index tmp_influencer_show_on_search_influencer_id on tmp_influencer_show_on_search(id);

    HACK: this selects and updates show_on_search = False influencers to avoid joins. To handle all values we need to do the
    same for show_on_search = True ones too.
    '''
    connection = db_util.connection_for_reading()
    cursor = connection.cursor()
    cursor.execute('SELECT id FROM tmp_influencer_show_on_search WHERE show_on_search = false LIMIT 10')
    return [row[0] for row in cursor.fetchall()]


def mark_updated(influencer_ids):
    influencer_comma_string = str(tuple(influencer_ids))
    connection = db_util.connection_for_writing()
    cursor = connection.cursor()
    cursor.execute('''
    DELETE FROM tmp_influencer_show_on_search
    WHERE id IN {influencer_ids}
                '''.format(influencer_ids=influencer_comma_string))


def update_influencers(influencer_ids):
    try:
        influencer_comma_string = str(tuple(influencer_ids))
        connection = db_util.connection_for_writing()
        cursor = connection.cursor()
        cursor.execute('''
    UPDATE {posts}
    SET show_on_search = false
    WHERE influencer_id IN {influencer_ids}
                    '''.format(posts=POSTS_TABLE, influencer_ids=influencer_comma_string))
    except Exception:
        traceback.print_exc()


def run_update():
    while True:
        influencers_to_update = get_influencer_batch()
        if not influencers_to_update:
            print("Done.")
            break

        print('Updating posts for influencers: {}'.format(influencers_to_update))
        update_influencers(influencers_to_update)

        print('Removing updated influencers')
        mark_updated(influencers_to_update)

        # Let the DB take a breather
        time.sleep(10)
