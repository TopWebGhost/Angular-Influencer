PgBouncer Configuration
=========================

PgBouncer is a connection pooling proxy for PostgreSQL. We use it to reduce the total number of database connections we create from worker instances.

Why use it
----------
There is a significant overhead for every DB connection both on the client and server side:

- The client has to wait for the connection to be established, then issue commands and close the connection after, just to open it again for the next task.
- The server has to spawn a separate backend process for every connection and having too many of those, could cause DB performance issues.


Installing PgBouncer
--------------------
We use the Ubuntu default pgbouncer package, which is installed via the requirements.system.txt package update mechanism.

PgBouncer doesn't start up by default on installation and requires some tweaks to its configuration. We have a script that takes care of that: `install_pgbouncer.py`. It does the following:

1. Import the DB endpoint config and credentials from settings.py.
2. Generate a valid pgbouncer.ini and copies it to /etc/pgbouncer
3. Set the same DB user and write it in /etc/pgbouncer/userlist.txt
4. Enable and restart the service.

The script takes a single parameter, which is the DB connection pool size. You invoke it like this:

::

    ./deployments/common/install_pgbouncer.py -p 10

and it will call sudo to configure PgBouncer locally.

Making Python Code Use PgBouncer
-----------------------------------
We have a separate settings module that gets the current `DATABASE['default']` setting and changes its `HOST` and `PORT` settings to point it to the local pgbouncer daemon. Since we do it only for GCE workers now, we only have one module named `settings_google_pgbouncer.py`.

To switch a worker to pgbouncer, you need to change its supervisor config environment from `E="google"` to `E="google_pgbouncer"`.

Installing and Updating PgBouncer Remotely
------------------------------------------
Installing PgBouncer for a single server instance involves the following steps:

1. Stopping all workers.
2. Pulling the latest code from the git repository (and getting the latest version of the pgbouncer installer script).
3. Running the script, passing the needed pool size parameter.
4. Run a full deploy (safest), which will update packages and restart workers.

We have a Fabric task, `common.reconfigure_pgbouncer` that does all that:

::
    fab -P -R daily-fetcher common.reconfigure_pgbouncer:10

The above will update the pgbouncer configuration on all daily-fetcher worker instances (running in parallel) and set a pool size of 10.

When Should I Update PgBouncer Configs?
---------------------------------------
Since the DB credentials are stored in `/etc/pgbouncer/pgbouncer.ini`, configs should be updated on every DB connection setting change.
