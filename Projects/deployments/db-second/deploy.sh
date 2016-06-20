#!/bin/bash
export ROLE="db-second"

PROJECT_PATH="/home/$USER/Projects_$ROLE"
$PROJECT_PATH/deployments/common/common_deploy.sh
