from __future__ import absolute_import, division, print_function, unicode_literals
import os
from contextlib import contextmanager
from fabric.api import task, env, cd, run, sudo, prefix
from fabric.operations import put


def current_role():
    host_string = env.get('host_string')
    if host_string:
        for role_name, role_def in env['roledefs'].items():
            if role_name.startswith('all'):
                continue
            for role_host in role_def['hosts']:
                if role_host in host_string:
                    return role_name

    raise ValueError("Host '{}' not found in role definitions.".format(host_string))


def local_project_dir():
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def project_dir(role):
    return env.roledefs[role]['project_dir']


def venv_dir(role):
    return os.path.join(project_dir(role), 'venv')


@contextmanager
def cd_project(role=None):
    if not role:
        role = current_role()
    with cd(project_dir(role)):
        yield


@task
def project_run(command, role=None):
    '''
    Run a command with the virtualenv activated and the current dir set to the project root.
    '''
    if not role:
        role = current_role()

    with cd_project(role):
        with prefix(". '{}/bin/activate'".format(venv_dir(role))):
            run(command)


@task
def bootstrap(command, role=None):
    return project_run('./bootstrap {}'.format(command))


@task
def start_supervisord(role=None):
    if not role:
        role = current_role()

    supervisor_conf = 'deployments/{}/files/supervisord.conf'.format(role)
    with cd_project(role):
        sudo('supervisord -c "{}"'.format(supervisor_conf))


@task
def supervisorctl(command, role=None, fail_on_error=True):
    if not role:
        role = current_role()

    supervisor_conf = 'deployments/{}/files/supervisord.conf'.format(role)
    with cd_project(role):
        supervisor_command = 'supervisorctl -c "{}" {}'.format(supervisor_conf, command)
        if not fail_on_error:
            supervisor_command += ' || true'
        sudo(supervisor_command)


@task
def status(role=None):
    supervisorctl(command='status', role=role)


@task
def stop(role=None):
    supervisorctl(command='stop all', role=role)


@task
def force_stop(role=None):
    supervisorctl(command='stop all', role=role)
    supervisorctl(command='shutdown', role=role)

    # Clean up, if needed
    sudo('pkill -f celery')
    sudo('pkill -f firefox')
    sudo('pkill -f servermonitoring') # We sometimes get processes escaping supervisord


@task
def start(role=None):
    supervisorctl(command='start all', role=role)


@task
def check_logs(role=None):
    if not role:
        role = current_role()

    config = 'deployments/{}/files/supervisord.conf'.format(role)
    with cd_project(role):
        run("./scripts/check_logs.py -c '{}'".format(config))


@task
def restart_workers(role=None):
    supervisorctl(command='stop all', role=role, fail_on_error=False)
    supervisorctl(command='reread', role=role, fail_on_error=False)
    supervisorctl(command='update', role=role, fail_on_error=False)
    supervisorctl(command='start all', role=role)


@task
def force_restart(role=None):
    supervisorctl(command='stop all', role=role)
    supervisorctl(command='shutdown', role=role)
    run('killall -9 firefox || true')
    start_supervisord(role)


@task
def update_code(branch='master', role=None):
    with cd_project(role):
        # make sure fetch fetches all branches!
        run('git config remote.origin.fetch +refs/heads/*:refs/remotes/origin/*')
        run('git fetch origin')
        run('git checkout -f origin/{}'.format(branch))


@task
def reconfigure_pgbouncer(pool_size=10, branch='master', role=None):
    force_stop(role)
    update_code(branch, role)
    #project_run('./deployments/common/install_pgbouncer.py -p {}'.format(pool_size), role)
    deploy(branch, force=True, role=role)


@task
def update_virtualenv(role=None):
    bootstrap(command='update_virtualenv', role=role)


@task
def update_system_packages(role=None):
    bootstrap(command='update_packages common', role=role)


@task
def deploy(branch='master', force=True, role=None):
    update_code(branch, role)
    update_system_packages(role)
    update_virtualenv(role)
    if force:
        force_restart(role)
    else:
        restart_workers(role)


@task
def pip(command, role=None):
    if not role:
        role = current_role()

    with cd_project(role):
        run('./theshelf pip {}'.format(command))


@task
def install(role=None):
    if role is None:
        role = current_role()

    user_data_script = '{}/deployments/{}/user_data.sh'.format(local_project_dir(), role)
    put(local_path=user_data_script, remote_path='/root', use_sudo=True)
    sudo('chmod a+x /root/user_data.sh')
    sudo('/root/user_data.sh')
