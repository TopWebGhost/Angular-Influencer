#!/bin/sh
ansible all -m shell -a 'ls -l /tmp/supervisor*.sock 2>/dev/null || true'
