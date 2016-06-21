#!/bin/bash

PROJECTS_DIR=/home/ubuntu/Projects_price-tracker

# OS settings
sysctl -w net.ipv4.tcp_fin_timeout=15
sysctl -w net.ipv4.ip_local_port_range="25000 65000"
sudo apt-get update
sudo apt-get install -y libcurl4-openssl-dev

# Preparation of git code deployment
rm -fr /home/ubuntu/Projects_price-tracker
su ubuntu -c 'ssh-agent sh -c "cd /tmp; ssh-add /home/ubuntu/sshkeys/githubkey; git clone git@github.com:atuls/Projects.git /home/ubuntu/Projects_price-tracker"'
cd /home/ubuntu/Projects_price-tracker
cd deployments/price-tracker

# Copy system config files from repo
cp sysfiles/etc/cron.d/* /etc/cron.d
killall -HUP cron

$PROJECTS_DIR/deployments/common/common_setup.sh $PROJECTS_DIR

# The rest is done by a script run from ubuntu user
./run_deploy_as_root.sh
