PROJECTS_ROOT=$(cd "$(dirname ${BASH_SOURCE:-$_})"/.. && pwd)
export PYTHONPATH=$PROJECTS_ROOT:$PROJECTS_ROOT/miami_metro
export DJANGO_SETTINGS_MODULE=settings
source $PROJECTS_ROOT/venv/bin/activate
