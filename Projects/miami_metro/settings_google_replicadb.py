from settings_google import *  #flake8:noqa
from copy import deepcopy

READ_DB = 'read_replica'
WRITE_DB = 'default'

DATABASES['read_replica'] = deepcopy(DATABASES['default'])
DATABASES['read_replica']['HOST'] = DATABASES['default']['REPLICA_HOST']

class ReadReplicaRouter(object):
    def db_for_read(self, model, **hints):
        return READ_DB

    def db_for_write(self, model, **hints):
        return WRITE_DB

    def allow_relation(self, obj1, obj2, **hints):
        """
        Avoid an "Instance is on database 'default', value is on database 'read_replica' error.

        Our DB's are synced, so we should allow relations anyway.
        """
        return True


DATABASE_ROUTERS = ['settings_google_replicadb.ReadReplicaRouter']
