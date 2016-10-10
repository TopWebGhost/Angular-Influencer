#!/bin/sh

if ! [ "$1" ]; then
    echo "Supervisorctl command is needed"
    exit 1
fi

exec ansible -s 'Daily-Fetcher*' -m shell -a "supervisorctl -s unix:///tmp/supervisor-daily-fetcher.sock $@"
