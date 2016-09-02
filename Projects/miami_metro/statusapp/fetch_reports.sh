#!/bin/bash

source /home/ubuntu/venv-statusapp/bin/activate
cd /home/ubuntu/Projects/miami_metro/statusapp/
export DJANGO_SETTINGS_MODULE=statusapp.settings
export PYTHONPATH=".:.."
python -m statustasks.fetch_reports /var/www/reports
exit 0
