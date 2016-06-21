#!/bin/bash

rm -f deploy.log
touch deploy.log
chown ubuntu:ubuntu deploy.log
sudo chown -R ubuntu:ubuntu /home/ubuntu
su ubuntu -c "cd $PWD; stdbuf -o L -e L ./deploy.sh >> deploy.log 2>&1"
