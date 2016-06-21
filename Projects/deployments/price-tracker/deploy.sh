#!/bin/bash

cd /home/ubuntu/Projects_price-tracker

virtualenv venv
source venv/bin/activate

export PYTHONPATH=/home/ubuntu/Projects_price-tracker/miami_metro
pip install -r requirements.txt
pip install --upgrade --force-reinstall python-intercom

sudo /usr/local/bin/supervisord -c /home/ubuntu/Projects_price-tracker/deployments/price-tracker/files/supervisord.conf

