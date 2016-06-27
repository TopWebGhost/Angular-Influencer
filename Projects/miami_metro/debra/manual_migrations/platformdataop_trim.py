'''
A helper script that trims old records from the debra_platformdataop table.

The entry point is the run_update() function, which you can run in a Django shell.
'''
from __future__ import absolute_import, division, print_function, unicode_literals
from debra import db_util
import time


def delete_batch(batch_size=10000):
    '''
    Delete the earliest <batch_size> ops and return the count of rows actually deleted
    '''
    connection = db_util.connection_for_writing()
    cursor = connection.cursor()
    sql = '''
WITH deleted_ops AS (
    DELETE FROM debra_platformdataop
    WHERE id IN (
        SELECT id from debra_platformdataop
        WHERE started < now() - '6 months'::INTERVAL
        ORDER BY started
        LIMIT %s
    )
    RETURNING *
)
SELECT count(*) FROM deleted_ops;
'''
    cursor.execute(sql, [batch_size])
    return [row[0] for row in cursor.fetchall()][0]


def run_update(batch_size=10000):
    while True:
        deleted = delete_batch(batch_size=batch_size)
        print('Deleted {} ops.'.format(deleted))

        if deleted < batch_size:
            print("Done.")
            break

        # Let the DB take a breather
        time.sleep(10)
