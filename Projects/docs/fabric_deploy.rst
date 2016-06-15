Fabric Deployments
=========================

Fabric is an SSH-based server automation tool that offers a concise Python API to execute commands on multiple machines. Details on http://www.fabfile.org.

Hosts are organized in various roles. With the role and host configuration occurring in ``fabfile/__init__.py``. There is a separate SSH connection configuration: ``fabfile/ssh_config`` that lists host IP's and SSH key configs.

Listing Available Tasks
------------------------------
::

    fab --list

Role List
------------------------------
daily-fetcher
platform-data-postprocessing
celery-default
newinfluencer-fetcher
rs-daily-fetcher
rs-platform-data-postprocessing

all - all of the above. No tasks bound to it -- useful for one off diagnostic commands.
all_workers - just worker instances. Useful for broad diagnostic commands.

Passing Parameters to Tasks
------------------------------

Just use a colon after the task name:
::

    fab -H <IP or hostname> common.supervisorctl:command="stop all"

If the task has only one parameter, you can omit the parameter name:
::

    fab -H <IP or hostname> common.supervisorctl:"stop all"

Deploying New Worker Code
------------------------------

This command will push new ``master`` code to all queue worker servers:
::

    fab -P worker_deploy

You can override the git branch being deployed by passing the ``branch`` parameter.

Running a System Command on a Single Host
-----------------------------------------
::

    fab -H <IP or hostname> -- free -m

Running a System Command on All Machines of a Certain Role
----------------------------------------------------------
::

    fab -R daily-fetcher -- free -m
    fab -R all -- sudo ~/ps_mem.py

Running a Command on Machines in Parallel
-----------------------------------------

Don't want to wait for machine N before executing on machine N + 1? Use the -P switch:
::

    fab -P -R daily-fetcher -- free -m


Deploying New Code to a Single Role or Instance
-----------------------------------------------

The magic happens in ``fabfile/common.py``. To run a full deploy, you need to specify a role or host name.
::

    fab -R daily-fetcher common.deploy

The above will deploy the latest ``master`` branch to all daily-fetcher instances. To deploy to a single instance, run:
::

    fab -H <IP address or hostname> common.deploy

The scripts will resolve the role by searching all roledefs' ``hosts`` lists. See ``common.current_role`` for details.

Other useful tasks in the ``common`` module are: ``update_code``, ``restart_workers``, ``force_restart``, ``supervisorctl``, ``start_supervisord``, ``status``, ``update_virtualenv``, ``update_system_packages``


Installing a New Worker Instance
--------------------------------

1. Start the virtual machine and determine its hostname, say "postprocessing-7".
2. Prepare the machine (updating packages, setting hostnames, DNS settings, etc) by running:

::

    fab -H <IP address or hostname> pre_install:hostname='postprocessing-7'

Note: The last step of the pre_install process will reboot the instance.

3. Add the instance address to the list of hosts in the correct roledef (``miami_metro/servers.py``), so that role resolution works at install time.
4. After the rebooted instance has come back online, run the full role install:

::

   fab -H <IP address or hostname> common.install


.. _fabric-ssh-helper:

Easy Interactive SSH Sessions
------------------------------

To connect to the second instance of the ``daily-fetcher`` role, use this fab command:
::

    fab -R daily-fetcher ssh:2

Machine indexes are 1-based, so the first instance is ``ssh:1``. Of course, you can change the role name to connect to other workers too.
