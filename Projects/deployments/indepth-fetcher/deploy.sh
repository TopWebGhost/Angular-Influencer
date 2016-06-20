#!/bin/bash

ROLE="indepth-fetcher"
PROJECT_PATH="/home/ubuntu/Projects_$ROLE"
cd $PROJECT_PATH

virtualenv venv
source venv/bin/activate

export PYTHONPATH=$PROJECT_PATH/miami_metro
pip install -r requirements.txt
pip install --upgrade --force-reinstall python-intercom

#sudo $PROJECT_PATH/deployments/common/install-xvfb.sh
sudo /usr/local/bin/supervisord -c "$PROJECT_PATH/deployments/$ROLE/files/supervisord.conf"
