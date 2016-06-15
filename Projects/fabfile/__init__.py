from __future__ import absolute_import, division, print_function, unicode_literals
import os
from fabric.api import env, local, task, roles, sudo, parallel
from . import common, roles_config


FAB_DIR = os.path.dirname(__file__)
env.user = 'ubuntu'
env.pool_size = 20  # Max simultaneous command connections
env.key_filename = os.path.join(os.path.dirname(FAB_DIR), 'miami.pem')
env.forward_agent = True


env.roledefs = roles_config.roledefs


@task
@roles('daily-fetcher', 'platform-data-postprocessing', 'newinfluencer-fetcher',
       'daily-fetcher-blogs', 'daily-fetcher-social', 'daily-fetcher-infrequent',
       'product-importer-from-blogs',
       'celery-default', 'rs-daily-fetcher', 'rs-platform-data-postprocessing')
@parallel(pool_size=20)
def worker_deploy(branch='master', force=True):
    common.deploy(branch=branch, force=force)


@task
@roles('db-second')
def db_second_deploy(branch='master', force=True):
    common.deploy(branch=branch, force=force)


@task
def pre_install(hostname):
    sudo('apt-get -qy update')
    sudo('apt-get -qyy dist-upgrade')
    set_hostname(hostname)
    setup_ntp_time()
    sudo('reboot')


@task
def set_hostname(hostname):
    sudo('echo "{}" > /etc/hostname'.format(hostname))
    sudo('echo "127.0.0.1 {}" >> /etc/hosts'.format(hostname))


@task
def setup_ntp_time():
    sudo('apt-get -qyy install ntpdate')
    sudo('echo "0 1 * * * root /usr/sbin/ntpdate-debian" > /etc/cron.d/ntpdate')
    sudo('ntpdate-debian')


@task
def ps_mem(role=None):
    with common.cd_project(role):
        sudo("./scripts/ps_mem.py")


@task
def ssh(index, user='ubuntu'):
    role = env.roles[0]

    try:
        index = int(index)
    except ValueError:
        print("Pass a numeric 0-based host index.")
        return

    try:
        target_host = env.roledefs[role]['hosts'][index - 1]
    except IndexError:
        print('Host {} not found.'.format(index))
        return

    if target_host not in env.host_string:
        print('Skipping host: {}'.format(env.host_string))
        return

    if '@' not in target_host:
        ssh_command = 'ssh {user}@{host} -A -i {key_file}'.format(user=env.user, host=target_host,
                                                   key_file=env.key_filename)
    else:
        ssh_command = 'ssh {host} -A -i {key_file}'.format(host=target_host,
                                                   key_file=env.key_filename)

    local(ssh_command)
