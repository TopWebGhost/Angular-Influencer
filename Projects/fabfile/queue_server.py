from __future__ import absolute_import, division, print_function, unicode_literals
from fabric.api import task, run


@task
def nonempty_queues():
    run("/opt/rabbitmq/sbin/rabbitmqctl list_queues -p /theshelf | "
        "sed '/^Listing queues/d' | "
        "awk '$2 > 0 {print $0}' | "
        "sort -n -k 2")
