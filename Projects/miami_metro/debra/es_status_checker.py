from servers import es_nodes
from celery.decorators import task
import requests
from django.conf import settings
import logging
from mailsnake import MailSnake
from debra.models import Influencer

from elasticsearch import Elasticsearch
from elasticsearch.helpers import scan

from social_discovery.blog_discovery import queryset_iterator


log = logging.getLogger('debra.celery_status_checker')

mailsnake_client = MailSnake(settings.MANDRILL_API_KEY, api='mandrill')

REPORT_TO_EMAILS = [{'email': email_entry[1], 'type': 'to'} for email_entry in settings.ADMINS]


@task(name="debra.es_status_checker.check_es_cluster_status", ignore_result=True)
def check_es_cluster_status():
    """
    Checks status of our ElasticSearch cluster and sends email if some node is downed.
    :return:
    """

    not_200_status = []
    downed_machines = []

    # getting downed machines
    for machine_name, host_ip in es_nodes.items():

        try:
            resp = requests.get(
                'http://%s:9200/' % host_ip,
                timeout=10
            )

            if resp.status_code == 200 and resp.json().get('status', None) == 200:
                log.info('Looks like ES node is running good...')
                pass
            else:
                log.info('Looks like the ES node %s returned some bad response... ' % machine_name)
                not_200_status.append((machine_name, host_ip, resp.status_code))
        except:
            log.info('Looks like the ES node %s is downed and unreachable... ' % machine_name)
            downed_machines.append((machine_name, host_ip))

    log.info('Not 200 status machines: %s' % not_200_status)
    log.info('Downed machines: %s' % downed_machines)

    # sending an email
    if len(downed_machines) > 0 or len(not_200_status) > 0:

        html = ""

        if len(not_200_status) > 0:
            html += "<p>WARNING: ES nodes did not return 200 status:</p>"
            for machine_name, host, status in not_200_status:
                html += "<p>%s (%s) : status %s</p>" % (machine_name, host, status)

        if len(downed_machines) > 0:
            html += "<p>WARNING: ES nodes might be downed:</p>"
            for machine_name, host in downed_machines:
                html += "<p>%s (%s)</p>" % (machine_name, host)

        mailsnake_client.messages.send(message={
            'html': html,
            'subject': 'WARNING: ES nodes might be currently downed',
            'from_email': 'atul@theshelf.com',
            'from_name': 'ES Cluster Activity Monitor',
            'to': REPORT_TO_EMAILS}
        )


@task(name="debra.es_status_checker.check_old_show_on_search_influencers", ignore_result=True)
def check_old_show_on_search_influencers():
    """
    Checks which Influencers with old_show_on_search=True are not currently indexed in ES.
    :return:
    """

    # DB influencer ids
    inf_ids = Influencer.objects.filter(
        old_show_on_search=True,
        source__isnull=False,
        blog_url__isnull=False
    ).exclude(
        blacklisted=True
    ).values_list(
        'id', flat=True
    )
    db_inf_ids = set(inf_ids)

    log.info('DB influencer ids: %s' % len(db_inf_ids))

    # ES influencer ids
    es_inf_ids = set()

    # overriding filter -- adding exclusion of old_show_on_search=True and getting show_on_search=True on production
    qry = {
        "fields": [
            "_id"
        ],
        "query": {
            "filtered": {
                "filter": {
                    "bool": {
                        "must": [
                            {
                                "term": {
                                    "old_show_on_search": True
                                }
                            }
                        ],
                        "must_not": [
                            {
                                "term": {
                                    "blacklisted": True
                                }
                            }
                        ]
                    }
                }
            }
        }
    }

    es = Elasticsearch(['198.199.71.215', ])

    es_data = scan(
        es,
        query=qry,
        size=500,
        doc_type="influencer"
    )

    for hit in es_data:
        # print(hit)
        try:
            es_id = hit.get('_id')
            if es_id is not None:
                es_inf_ids.add(int(es_id))
        except Exception as e:
            log.error(e)

    log.info('ES influencer ids: %s' % len(es_inf_ids))

    # finding out who is not indexed
    unindexed_ids = db_inf_ids - es_inf_ids

    log.info('Unindexed: %s' % len(unindexed_ids))

    if len(unindexed_ids) > 0:
        subject = "Unindexed production Influencers found: %s" % len(unindexed_ids)
        html = "<p>UNINDEXED Influencers with old_show_on_search=True: %s</p>" % len(unindexed_ids)

        for inf in Influencer.objects.filter(id__in=list(unindexed_ids)).values_list('id', 'name', 'blogname', 'old_show_on_search'):
            html += "<p>%s : %s , Blog name: %s (old_show_on_search=%s)</p>" % (inf[0],
                                                                                inf[1],
                                                                                inf[2],
                                                                                inf[3])

    else:
        subject = "No unindexed production Influencers found."
        html = "<p>No unindexed Influencers found.</p>"

    log.info(subject)
    log.info(html)

    mailsnake_client.messages.send(message={
        'html': html,
        'subject': subject,
        'from_email': 'atul@theshelf.com',
        'from_name': 'ES Cluster Activity Monitor',
        'to': REPORT_TO_EMAILS}
    )
