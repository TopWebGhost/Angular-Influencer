[unix_http_server]
file=/tmp/supervisor-daily-fetcher.sock   ; (the path to the socket file)

[supervisord]
logfile=/tmp/supervisord-daily-fetcher.log ; (main log file;default $CWD/supervisord.log)
logfile_maxbytes=10MB        ; (max main logfile bytes b4 rotation;default 50MB)
logfile_backups=10           ; (num of main logfile rotation backups;default 10)
loglevel=info                ; (log level;default info; others: debug,warn,trace)
pidfile=/tmp/supervisord-daily-fetcher.pid ; (supervisord pidfile;default supervisord.pid)
nodaemon=false               ; (start in foreground if true;default false)
minfds=1024                  ; (min. avail startup file descriptors;default 1024)
minprocs=200                 ; (min. avail process descriptors;default 200)

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix:///tmp/supervisor-daily-fetcher.sock ; use a unix:// URL  for a unix socket
;serverurl=http://127.0.0.1:9001 ; use an http:// url to specify an inet socket
;username=chris              ; should be same as http_username if set
;password=123                ; should be same as http_password if set
;prompt=mysupervisor         ; cmd line prompt (default "supervisor")
;history_file=~/.sc_history  ; use readline history if available

;[include]
;files = relative/directory/*.ini

{% for platform in platforms %}
[program:celeryd-fetcher-{{ platform }}]
command=/home/ubuntu/Projects_daily-fetcher/venv/bin/python manage.py celeryd --loglevel=INFO -c 1 -Q daily_fetching.{{ platform }}
directory=/home/ubuntu/Projects_daily-fetcher/miami_metro
redirect_stderr=true
stdout_logfile=/home/ubuntu/log/celeryd-fetcher-{{ platform }}.out
stderr_logfile=/home/ubuntu/log/celeryd-fetcher-{{ platform }}.err
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=10
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
environment=PYTHONPATH="/home/ubuntu/Projects_daily-fetcher",DJANGO_SETTINGS_MODULE="settings",MIAMI_SENTRY_DSN="http://4ec48378879f46898694a4eef298629c:b2d04c2f39554e8eab942989d1064561@ec2-54-225-19-99.compute-1.amazonaws.com:9000/5"
user=ubuntu
{% endfor %}

[program:celeryd-daily-sponsorship_fetching]
command=/home/ubuntu/Projects_daily-fetcher/venv/bin/python manage.py celeryd --loglevel=INFO -c 1 -Q sponsorship_fetching
redirect_stderr = true
stdout_logfile=/home/ubuntu/log/celeryd-daily-sponsorship_fetching.out
stderr_logfile=/home/ubuntu/log/celeryd-daily-sponsorship_fetching.err
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=10
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
environment=PYTHONPATH="/home/ubuntu/Projects_daily-fetcher",DJANGO_SETTINGS_MODULE="settings",MIAMI_SENTRY_DSN="http://4ec48378879f46898694a4eef298629c:b2d04c2f39554e8eab942989d1064561@ec2-54-225-19-99.compute-1.amazonaws.com:9000/5"

[program:hcheck-disk]
command=/home/ubuntu/Projects_daily-fetcher/venv/bin/python -m servermonitoring.healthchecks check_disk_space
directory=/home/ubuntu/Projects_daily-fetcher
redirect_stderr = true
stdout_logfile=/home/ubuntu/log/hcheck-disk.out
stderr_logfile=/home/ubuntu/log/hcheck-disk.err
autostart=true
autorestart=true
environment=DJANGO_SETTINGS_MODULE="settings",PYTHONPATH="/home/ubuntu/Projects_daily-fetcher/miami_metro"
user=ubuntu

