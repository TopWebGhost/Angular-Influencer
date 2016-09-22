from settings import *  #flake8:noqa

# GCE RabbitMQ cluster
BROKER_HOST = "130.211.172.204"

# This is the stats node IP address. Not all cluster nodes run the management
# web API.
RABBITMQ_MANAGEMENT_API_ENDPOINT = 'http://130.211.131.175:15672'
RABBITMQ_NODE_MEMORY_ALERT = 8 * 1024 * 1024 * 1024 # 8 GB
