#!/bin/bash

cd /home/ubuntu/Projects_daily-submitter

virtualenv venv
source venv/bin/activate

export PYTHONPATH=/home/ubuntu/Projects_daily-submitter/miami_metro
pip install -r requirements.txt
pip install --upgrade --force-reinstall python-intercom

export DJANGO_SETTINGS_MODULE=settings

# Tasks submission code

python -m platformdatafetcher.postprocessing submit_daily_postprocessing_tasks > /home/ubuntu/submit.log 2>&1

# Send logs

LOG_DEST=104.130.7.28:log

chmod 400 miami.pem
scp -i ./miami.pem deployments/daily-submitter/deploy.log $LOG_DEST/daily-submitter-deploy-$(date +%s).log
scp -i ./miami.pem /home/ubuntu/submit.log $LOG_DEST/submit-$(date +%s).log

# Terminating instance

sudo shutdown -h now

