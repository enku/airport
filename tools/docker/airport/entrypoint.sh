#!/bin/sh
set -e

MANAGE="python3 /opt/airport/airport/djangoproject/manage.py"
PATH="/opt/airport/.local/bin:$PATH"
DJANGO_DEBUG=${DJANGO_DEBUG:-0}

if [ "${DJANGO_DEBUG}" -ne 0 ] ; then
    echo "Running in debug mode"
    MANAGE="python3 /usr/src/manage.py"
    PYTHONPATH=/usr/src/airport
else
    PYTHONPATH=/opt/airport/airport/djangoproject
fi

export PYTHONPATH

# migrate the data
sleep 3
$MANAGE migrate auth
$MANAGE migrate
$MANAGE gameserver &

if [ "${DJANGO_DEBUG}" -ne 0 ] ; then
    $MANAGE runserver -v2 0.0.0.0:8000
else
    gunicorn -w 4 --bind 0.0.0.0:8000 djangoproject.wsgi
fi

wait
