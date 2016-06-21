#!/bin/bash

cd /home/ubuntu/Projects_platform-extractor

virtualenv venv
source venv/bin/activate

export PYTHONPATH=/home/ubuntu/Projects_platform-extractor/miami_metro
pip install -r requirements.txt
pip install --upgrade --force-reinstall python-intercom

sudo /usr/local/bin/supervisord -c /home/ubuntu/Projects_platform-extractor/deployments/platform-extractor/files/supervisord.conf

