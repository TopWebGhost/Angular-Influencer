#!/bin/bash

rm -f deploy.log
touch deploy.log
chown $USER:$GROUP deploy.log
sudo chown -R $USER:$GROUP /home/$USER
su $USER -c "cd $PWD; ./deploy.sh 2>&1 | tee deploy.log"
