PROJECTS_ROOT=$(cd "$(dirname ${BASH_SOURCE:-$_})"/.. && pwd)
export PYTHONPATH=$PROJECTS_ROOT/miami_metro:$PROJECTS_ROOT/miami_metro/statusapp
export DJANGO_SETTINGS_MODULE=statusapp.settings

if [ -d $PROJECTS_ROOT/miami_metro/statusapp/venv ]; then
    source $PROJECTS_ROOT/miami_metro/statusapp/venv/bin/activate
else
    source $PROJECTS_ROOT/venv/bin/activate
fi
