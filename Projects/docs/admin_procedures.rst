Administration procedures
=========================

For running reports, it's best to use a local Django development server (address
http://localhost:8000/), because page loads will not give timeout errors.

Daily system correctness check
------------------------------

PDO stats report
^^^^^^^^^^^^^^^^

Implementation: :func:`debra.admin.pdo_stats_report`.

Address: http://localhost:8000/admin/upgrade/report/pdo_stats/?days=3

The ``days`` argument can be changed and can be fractional.

This is the most important report showing the "heartbeat" of the system. The report shows numbers of
tasks executed in the last ``days``, divided by successes and failures. A failure is recognized by
looking at :attr:`~debra.models.PlatformDataOp.error_msg` - it's ``None`` for a success, and contains
an exception type and message when there was an error (the assumption is that all tasks use
:class:`debra.platformutils.OpRecorder` which handles storing error data automatically).

Task ``fetch_data`` has separate entries for policies used, and ``fetch_products_from_post`` are
divided by ``platform_name``.

Things to check:

- if all tasks that need to be executed are really executed
- if the number of successes is high enough
- if there aren't sudden drops of tasks being executed between days


PDO error summary
^^^^^^^^^^^^^^^^^

Implementation: :func:`debra.admin.ModifyItemsAdminSite.pdo_error_stats`.

Address: http://localhost:8000/admin/upgrade/report/pdo_error_stats/?days=1

The ``days`` argument can be changed and can be fractional.

This counts most common errors, by task type. Errors that are printed have appeared at least twice in
the specified ``days`` period.

Things to check:

- review all errors, especially with high counts

To review the errors individually and check for which models they happened, you can use the report that
lists all errenous executions: http://localhost:8000/admin/upgrade/report/pdo_all_errors/?days=0.1

Alternatively, you can directly inspect the database, eg.::

 SELECT * FROM debra_platformdataop
 WHERE task_name='task_name'
 AND error_msg IS NOT NULL
 AND started > current_timestamp - '1 day'::interval
 ORDER BY id desc


Postprocessing and daily fetching task submission
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Each function from :mod:`platformdatafetcher.postprocessing` that submits tasks is also separately
recorder in PlatformDataOp (by the main function
:func:`platformdatafetcher.postprocessing.submit_daily_postprocessing_tasks`), as well as
:func:`platformdatafetcher.pbfetcher.submit_daily_fetch_tasks`.

Things to check:

- see if all the submission functions where actually executed (for example, a problem encountered in
  the past was that the submitting process was killed because of memory errors)
- see how long it took to execute them (``started`` and ``finished`` columns). The execution time
  should be more or less the same every day.
- see if there are no errors for each of them (``error_msg`` column)


Query to view recent PDOs::

 SELECT *
 FROM debra_platformdataop
 WHERE operation LIKE 'submit%' OR operation LIKE 'periodic_content%'
 ORDER BY id DESC LIMIT 40;


Check platform and fetchers reports
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Look at reports that investigate number of platforms, posts, latest posts dates, all available on
the status app server: http://107.170.29.25:9000/theshelf-status/.


Rabbitmq dashboard
^^^^^^^^^^^^^^^^^^

See how many messages are in the queues::

 /opt/rabbitmq/sbin/rabbitmqctl list_queues -p /theshelf

The web interface contains this data also, plus it has graphs showing message consumption rates. The
interface is accessible on 15672 port, and the easiest way to use it is to setup an SSH tunnel::

 ssh -i miami.pem -L 15674:localhost:15672 ubuntu@104.130.3.236

After it, you can access http://localhost:15674 address in your browser (check ``settings.py`` for log
in credentials).


DB, Heroku dashboards
^^^^^^^^^^^^^^^^^^^^^

Check AWS console to see database load.

Check Heroku dashboard to see web application load.



Using ansible for running commands
----------------------------------

For investigating things on servers, Ansible can be used instead of SSH to automate running commands on
multiple servers at once: see :ref:`ref-ansible`.

Deploying New Code Using Fabric
----------------------------------

`fabric_deploy`
