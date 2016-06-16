#!/bin/bash

# script doing setup common to all deployments

PROJECTS_DIR="$1"

cd /home/ubuntu

### Setup /home/ubuntu/Projects_DEFAULT
if [ -f Projects_DEFAULT ]; then
    echo "Projects_DEFAULT already exists"
else
    ln -sf "$PROJECTS_DIR" Projects_DEFAULT
fi


### Setup cron.d
cp /home/ubuntu/Projects_DEFAULT/deployments/common/sysfiles/etc/cron.d/* /etc/cron.d
killall -HUP cron

# Run role-specific setup if any
if [ -x $PROJECTS_DIR/deployments/$ROLE/role_setup.sh ]; then
    $PROJECTS_DIR/deployments/$ROLE/role_setup.sh "$PROJECTS_DIR"
fi
