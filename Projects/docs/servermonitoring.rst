Server monitoring and controlling resources usage
=================================================


Killing Firefoxes taking too much memory/hanging
------------------------------------------------

All code that uses Selenium, usually through :class:`xpathscraper.xbrowser.XBrowser`, runs a Firefox
process and as experience shows it is not very stable. The process can hang, which means that when run as
a task, the whole Celery worker is blocked forever. Another issue is memory usage which is unpredictable.
Especially running more complex Javascript algorithms like in price tracker, or platform extractor, can
cause the memory usage to rise unpredictably.

To deal with these problems, a tool was implemented in :mod:`servermonitoring.watchdog`. The tool is run
as a separate process (it should be included in supervisord configs in deployments) as a command ``python
-m servermonitoring.watchdog watch``. It then checks in a loop for processes not fulfilling one of the
conditions (currently only ``firefox`` processes are checked and the duration values can be changed):

- memory usage less than 1.2GB
- a process should be validated after 180 seconds
- a process should be revalidated every 180 seconds

**Validation** is done by calling :func:`servermonitoring.watchdog.validate_process` for the given
``pid``. Currently the :class:`~xpathscraper.xbrowser.XBrowser` class calls this function at startup and
for every page load. It implies that when a ``firefox`` process hangs during startup or between page
loads, this situation will be noticed by the watchdog and the process will be killed (and Celery worker
manager/supervisord will be able to instantiate a new process). Validation is implemented by writing a
file in ``/tmp/watchdog-validated/`` with the name being ``<pid>-<create-time>`` and content --
time of validation.


Checking disk space
-------------------
The command :func:`servermonitoring.healthchecks.check_disk_space` just checks available disk space in
predefined paths (:attr:`servermonitoring.healthchecks.DISK_PATH`) and if it's lower than 90%, it sends a
message to Sentry.

Cleaning Selenium profiles
--------------------------

When Selenium process hangs, it leaves a directory containing a Firefox profile, which is about 20MB in
size. To delete these directories commands run by cron are set up. The setup is done by
``deployments/common/common_setup.sh`` script, called by ``user_data.sh`` present in ``deployment``
directories.


Sentry
------

Sentry captures exceptions and errors and aggregates them, and has a web interface to browse them.
The address is http://ec2-54-225-19-99.compute-1.amazonaws.com:9000/.

There's standard Django-Sentry integration used, which results in all ``log.exception()`` and
``log.error()`` calls to be sent to Sentry. To send a custom message, write::

 from raven.contrib.django.raven_compat.models import client

 client.captureMessage('My message')

To organize exceptions, multiple Sentry projects are used. By setting ``MIAMI_SENTRY_DSN`` flag to a
specific dsn (Sentry identification of a project), the default dsn is overridden. It's done in
Supervisord configs for specific process types.

Statusapp
---------

The Statusapp is a separate Django application that is a "dashboard" containing results of running
monitoring scripts, and includes multiple reports investigating the database contents.

The address is http://107.170.29.25:9000/theshelf-status/. (after logging in, you will be redirected to
a subpage - you need to re-enter the root page url manually)

The code is placed in ``miami_metro/statusapp/`` git subdirectory and the app is running on
107.170.29.25 Digital Ocean server, using ``ubuntu`` user, using a startup script
``miami_metro/statusapp/run_gunicorn.sh`` (it's set up to run on system startup in ``/etc/rc.local``).

The application periodically runs some offline monitoring scripts. The default cron setup::

    */10 * * * *   /home/ubuntu/Projects/miami_metro/statusapp/run_single_task.sh "database access"
    */10 * * * *   /home/ubuntu/Projects/miami_metro/statusapp/run_single_task.sh "website access"
    */10 * * * *   /home/ubuntu/Projects/miami_metro/statusapp/run_single_task.sh "website login"
    */10 * * * *   /home/ubuntu/Projects/miami_metro/statusapp/run_single_task.sh "rabbitmq access"
    */10 * * * *   /home/ubuntu/Projects/miami_metro/statusapp/run_single_task.sh "bookmarklet status"
    8 04 * * *     /home/ubuntu/Projects/miami_metro/statusapp/fetch_reports.sh

The application uses a local SQLite database (the reason is that it should not stop running when the
default database is not running). It means that it can't use Django's models defined in the default
``miami_metro`` application and mostly uses direct sql statements for reports.

To add a task that should run periodically, see :mod:`statusapp.statustasks.tasks` and the ``Task``
base class and example implementation. The run should be performed from cron and ``run_single_task.sh``
script.

To add a report, just modify the main view function :func:`statusapp.statustasks.views.status_table`
and the main template file ``status_table.html``.

.. automodule:: statusapp.statustasks.tasks
    :members:

Database reports
----------------

Some database reports are included in the main Django application, in :mod:`debra.admin` module.
The SQL can be executed using Django's 
