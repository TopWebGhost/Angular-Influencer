Deployment (running code on servers)
====================================

Deployment scripts
------------------
A "deployment" is a directory inside ``deployments/`` directory located in the Git repository.
It contains scripts for preparing an environment for running a specific set of processes
(usually Celery workers processing messages from specified queues). It leverages a
mechanism supported by EC2 instances for setting up a newly started server instance -
automatically running ``user_data.sh`` script after a bootup.

Multiple deployments can be run simultaneously on a single instance.

The important content of most deployments:

- ``user_data.sh`` - the main entry point, can be called manually. Should be executed by
  ``root`` user. It sets some system-level settings and clones Git repository to a
  directory ``/home/ubuntu/Projects-<deployment-name>`` (multiple deployments have
  separate Git clones). It usually calls ``deployments/common/common_setup.sh`` script
  which contains setup common to all deployments.
- ``deploy.sh`` - setting up a specific deployment, run by ``ubuntu`` user. It usually
  creates ``virtualenv`` for a Git clone and starts supervisord specific for the
  deployment (supervisord configuration uses paths specific to a deployment so that running
  multiple instances of supervisord will work).
- ``files/`` - contains files (like ``supervisord.conf``) used by a deployment
- ``sysfiles/`` - these files should be copied to system-level directories for setting
  system-level services (like cron).

.. _ref-ansible:

Ansible
-------
Ansible collects information about all running EC2 and Rackspace instances and enables
running commands on a subset of them. Configuration is stored inside
``deployments/common/sysfiles/`` and is currently deployed on an instance running
RabbitMQ. Test run::
    $ ansible all -m setup
This command should print details of all the dected servers.

Initial versions of Ansible scripts are available in ``playbooks/`` and ``scripts/``
directories.


Fabric
-------

Fabric can script code deployments, command execution and status checks. See :doc:`/fabric_deploy`.
