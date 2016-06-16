#!/bin/sh

# Start the Xvfb X server. Managed by an Upstart job
if [ -f /etc/supervisor/conf.d/xvfb.conf ] ; then
    echo "Xvfb already configured in system supervisord."
else
cat > /etc/supervisor/conf.d/xvfb.conf <<EOF
[program:xvfb]
command=Xvfb :1 -screen 0 1920x1080x24
redirect_stderr=true
stdout_logfile=/var/log/supervisor/xvfb.out
stderr_logfile=/var/log/supervisor/xvfb.err
stdout_logfile_maxbytes=10MB
stdout_logfile_backups=10
autostart=true
autorestart=true
startsecs=10
stopwaitsecs=60
user=$USER
killasgroup=true
EOF

    supervisorctl 'stop all'
    supervisorctl 'reread'
    supervisorctl 'update'
    supervisorctl 'start all'
fi
