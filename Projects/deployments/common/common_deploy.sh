#!/bin/bash
# script doing deploy actions common to all deployments
PROJECT_PATH="/home/$USER/Projects_$ROLE"
cd $PROJECT_PATH

# install system and setup virtualenv
./bootstrap all

# Run role-specific deploy if any
if [ -x $PROJECT_PATH/deployments/$ROLE/role_deploy.sh ]; then
    $PROJECT_PATH/deployments/$ROLE/role_deploy.sh "$PROJECT_PATH"
fi

source venv/bin/activate

export PYTHONPATH=$PROJECT_PATH/miami_metro
pip install --upgrade --force-reinstall python-intercom

# Supervisor log dir
mkdir -p /home/$USER/log

sudo apt-get install -y supervisor
sudo service supervisor start
sudo $PROJECT_PATH/deployments/common/fix-sshd-x-forwarding.sh
sudo USER=$USER GROUP=$GROUP $PROJECT_PATH/deployments/common/install-xvfb.sh
sudo cp $PROJECT_PATH/deployments/common/sysfiles/etc/cron.d/clean_* /etc/cron.d
sudo killall -HUP cron || true

# install_pgbouncer.py calls sudo
$PROJECT_PATH/deployments/common/install_pgbouncer.py -p 10

# Spawn a user supervisord instance with our workers
sudo supervisord -c "$PROJECT_PATH/deployments/$ROLE/files/supervisord.conf"
