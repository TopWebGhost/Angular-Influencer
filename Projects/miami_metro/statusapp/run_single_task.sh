#!/bin/bash

source /home/ubuntu/venv-statusapp/bin/activate
cd /home/ubuntu/Projects/miami_metro/statusapp/
export DJANGO_SETTINGS_MODULE=statusapp.settings
export PYTHONPATH=".:.."
python -m statustasks.tasks run_single_task "$1" >> /home/ubuntu/task-$(echo "$1" | tr ' ' '_').log 2>&1
exit 0
