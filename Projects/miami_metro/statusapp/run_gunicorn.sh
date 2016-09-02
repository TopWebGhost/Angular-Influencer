#!/bin/bash

source /home/ubuntu/venv-statusapp/bin/activate
cd /home/ubuntu/Projects/miami_metro/statusapp/
export PYTHONPATH=".:.."
export DJANGO_SETTINGS_MODULE=statusapp.settings
exec gunicorn \
	-b 0.0.0.0:9000 \
	--pid=/home/ubuntu/gunicorn.pid \
	--access-logfile=/home/ubuntu/statusapp-access.log \
	--log-file=/home/ubuntu/statusapp-gunicorn.log \
	-D \
	-w 2 \
	-t 3600 \
	statusapp.wsgi >> /home/ubuntu/gunicorn.out 2>&1
