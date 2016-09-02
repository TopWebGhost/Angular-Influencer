#!/bin/bash

source /home/ubuntu/venv-miami/bin/activate
cd /home/ubuntu/Projects
export PYTHONPATH=/home/ubuntu/Projects/miami_metro
export DJANGO_SETTINGS_MODULE=settings
nohup python -m servermonitoring.healthchecks bookmarklet_processing_test > /home/ubuntu/hcheck-bookmarklet.out 2>&1 &
