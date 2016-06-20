[unix_http_server]
file=/tmp/supervisor-indepth-fetcher.sock   ; (the path to the socket file)

[supervisord]
logfile=/tmp/supervisord-indepth-fetcher.log ; (main log file;default $CWD/supervisord.log)
logfile_maxbytes=10MB        ; (max main logfile bytes b4 rotation;default 50MB)
logfile_backups=10           ; (num of main logfile rotation backups;default 10)
loglevel=info                ; (log level;default info; others: debug,warn,trace)
pidfile=/tmp/supervisord-indepth-fetcher.pid ; (supervisord pidfile;default supervisord.pid)
nodaemon=false               ; (start in foreground if true;default false)
minfds=1024                  ; (min. avail startup file descriptors;default 1024)
minprocs=200                 ; (min. avail process descriptors;default 200)

[rpcinterface:supervisor]
supervisor.rpcinterface_factory = supervisor.rpcinterface:make_main_rpcinterface

[supervisorctl]
serverurl=unix:///tmp/supervisor-indepth-fetcher.sock ; use a unix:// URL  for a unix socket
;serverurl=http://127.0.0.1:9001 ; use an http:// url to specify an inet socket
;username=chris              ; should be same as http_username if set
;password=123                ; should be same as http_password if set
;prompt=mysupervisor         ; cmd line prompt (default "supervisor")
;history_file=~/.sc_history  ; use readline history if available

;[include]
;files = relative/directory/*.ini

{% for platform in platforms %}
[program:celeryd-indepth-fetcher-{{ platform }}]
command=/home/ubuntu/Projects_indepth-fetcher/venv/bin/python manage.py celeryd --loglevel=INFO -c 1 -Q indepth_fetching.{{ platform }}
directory=/home/ubuntu/Projects_indepth-fetcher/miami_metro
redirect_stderr = true
stdout_logfile=/home/ubuntu/log/celeryd-indepth-fetcher-{{ platform }}.out
stderr_logfile=/home/ubuntu/log/celeryd-indepth-fetcher-{{ platform }}.err
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=10
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=600
environment=PYTHONPATH="/home/ubuntu/Projects_indepth-fetcher",DJANGO_SETTINGS_MODULE="settings"
user=ubuntu
{% endfor %}

[program:hcheck-disk]
command=/home/ubuntu/Projects_indepth-fetcher/venv/bin/python -m servermonitoring.healthchecks check_disk_space
directory=/home/ubuntu/Projects_indepth-fetcher
redirect_stderr = true
stdout_logfile=/home/ubuntu/log/hcheck-disk.out
stderr_logfile=/home/ubuntu/log/hcheck-disk.err
autostart=true
autorestart=true
environment=DJANGO_SETTINGS_MODULE="settings",PYTHONPATH="/home/ubuntu/Projects_indepth-fetcher/miami_metro"
user=ubuntu

