# -*- coding: utf-8 -*-
import json
import logging
import datetime
import os
import base64
import time
import traceback
from io import BytesIO
from collections import Counter

import magic
from email import message
from mailsnake import MailSnake
from celery.decorators import task

from django.conf import settings
from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt
from django.core.mail import mail_admins
from django.core.cache import get_cache

from debra.mongo_utils import notify_brand

log = logging.getLogger('debra.mail_proxy')
mailsnake_client = MailSnake(settings.MANDRILL_API_KEY, api='mandrill')
mailsnake_admin_client = MailSnake(
    settings.MANDRILL_ADMIN_EMAIL_API_KEY, api='mandrill')
mc_cache = get_cache('memcached')
redis_cache = get_cache('redis')


def upload_message_attachments_to_s3(message, attachments, b64=False):
    from masuka.image_manipulator import get_bucket, BUCKET_PATH_PREFIX
    s3_attachments = []
    bucket = get_bucket('theshelf-email-attachments')
    try:
        for attachment in attachments:
            if type(attachment) == dict:
                filename = "%s_%s" % (
                    message.id if message else datetime.datetime.now(),
                    attachment['name']
                )
                new_key = bucket.new_key(filename)
                if b64:
                    content = base64.b64decode(attachment['content'])
                else:
                    content = attachment['content']
                new_key.set_contents_from_string(
                    content, headers={'Content-Type': attachment['type']})
                new_key.set_acl('public-read')
                s3_attachments.append({
                    'path': os.path.join(
                        BUCKET_PATH_PREFIX,
                        'theshelf-email-attachments', filename),
                    'name': attachment['name'],
                    'mimetype': attachment['type']
                })
    except:
        pass
    return s3_attachments


def collect_attachments(attachments, resend=False, msg=None):
    from debra.account_helpers import send_msg_to_slack
    from masuka.image_manipulator import get_bucket, BUCKET_PATH_PREFIX
    mandrill_attachments = []
    s3_attachments = []
    old_bucket = get_bucket('message-attachments-tmp')
    bucket = get_bucket('theshelf-email-attachments')
    for attachment in attachments:
        try:
            if resend:
                mandrill_attachments.append({
                    'name': attachment['name'],
                    'content': base64.b64encode(
                        bucket.get_key(
                            attachment['path'].split('/')[-1]).read()),
                    'type': attachment['mimetype']
                })
            else:
                old_key = attachment[1]
                new_key = "%s_%s" % (
                    msg.id if msg else datetime.datetime.now(),
                    attachment[0]
                )
                # new_key = 'attachment_{}'.format(attachment.strip('tmp_'))

                buff = BytesIO()
                old_bucket.get_key(old_key).get_contents_to_file(buff)
                content = buff.getvalue()

                bucket.copy_key(new_key, 'message-attachments-tmp', old_key)
                old_bucket.delete_key(old_key)
                bucket.get_key(new_key).set_acl('public-read')

                file_type = magic.from_buffer(content, mime=True)
                mandrill_attachments.append({
                    'name': attachment[0],
                    'content': base64.b64encode(content),
                    'type': file_type
                })
                s3_attachments.append({
                    'name': attachment[0],
                    'path': os.path.join(
                        BUCKET_PATH_PREFIX,
                        'theshelf-email-attachments', new_key),
                    'mimetype': file_type,
                })
                # s3_attachments.append({
                #     'name': attachment[0],
                #     'content': content,
                #     'type': filetype
                # })
        except:
            send_msg_to_slack(
                'attachment-crashes',
                "{traceback}\n"
                "{delimiter}"
                "\n".format(
                    delimiter="=" * 120,
                    traceback=traceback.format_exc(),
                )
            )
    return mandrill_attachments, s3_attachments


def mailsnake_admin_send(mandrill_message):
    # if settings.DEBUG:
    #     raise Exception()
    admins = [
        {"email": admin[1], "name": admin[0]}
        for admin in settings.ADMINS[:2]
    ]
    admin_message = mandrill_message.copy()
    admin_message.update({
        "to": admins,
        "subject": "{} ({})".format(
            mandrill_message["subject"],
            ", ".join([
                "{} <{}>".format(u["name"], u["email"])
                for u in mandrill_message["to"]
            ])
        )
    })
    print '* mailsnake send to admins'
    return mailsnake_admin_client.messages.send(message=admin_message)


def mailsnake_send(mandrill_message, admins_only=False, users_only=False):
    admin_resp, user_resp = None, None

    if not users_only:
        try:
            admin_resp = mailsnake_admin_send(mandrill_message)
        except Exception:
            log.info('Failed sending copy to admins')

    if not admins_only:
        print '* mailsnake send to users'
        # print '* {}'.format(mandrill_message)
        user_resp = mailsnake_client.messages.send(message=mandrill_message)

    if admins_only:
        log.info("Not sending to the influencer or the brand")
        return admin_resp

    return user_resp


def complete_message_influencer_2_brand(mandrill_message, thread, send=False,
                                        **kwargs):
    from debra import models

    to_list = []
    if thread.initiator:
        to_list.append({
            'email': thread.initiator.email, 'name': thread.brand_name})
    else:
        to_list = [
            {'email': email, 'name': thread.brand_name} for email in
            models.User.objects.filter(
                userprofile__brand_privilages__brand=thread.brand).values_list(
                    'email', flat=True)
        ]

    mandrill_message.update({
        'from_email': thread.influencer_mail,
        'from_name': thread.influencer_name,
        'to': to_list
    })

    if not send:
        str_ts = datetime.datetime.utcfromtimestamp(
            int(kwargs["ts"])).strftime("%b. %e, %Y - %H:%M")
        msg = {
            "text": "Received email from %s, %s UTC" % (
                thread.influencer.name, str_ts),
            "thread": thread.id
        }
        notify_brand(thread.brand.id, "mail", msg)


def complete_message_brand_2_influencer(mandrill_message, thread, sender=None,
                                        send=False, **kwargs):
    mandrill_message.update({
        'from_email': thread.brand_mail,
        'from_name': thread.brand_name,
    })
    emails = []
    if thread.influencer.email_for_advertising_or_collaborations:
        emails = thread.influencer \
            .email_for_advertising_or_collaborations.split()
    elif thread.influencer.email_all_other:
        emails = thread.influencer.email_all_other.split()
    elif thread.influencer.shelf_user:
        emails = [thread.influencer.shelf_user.email]
    if not emails:
        src = "unknown"
        if thread.candidate_mapping.exists():
            src = "Campaign title=%s, id=%i" % (
                thread.candidate_mapping.all()[0].job.title,
                thread.candidate_mapping.all()[0].job.id)
        if thread.mapping.exists():
            src = "Collection name=%s, id=%i" % (
                thread.mapping.all()[0].group.name,
                thread.mapping.all()[0].group.id)
        mail_admins(
            "No email for influencer",
            "source: %s, brand: %s, influencer id = %i" % (
                src, thread.brand.domain_name, thread.influencer.id))

    mandrill_message.update({
        'to': [{'email': x, 'name': thread.influencer_name} for x in emails]
    })


def is_invalid(resp):
    try:
        status = resp[0]["status"]
        if status == 'invalid':
            return True
    except Exception:
        log.exception(
            "Some error occurs when trying to get sent"
            "message's type: {}".format(resp))
    return False


def is_status(resp, status):
    try:
        if resp[0]["status"] == status:
            return True
    except Exception:
        pass
    return False


def get_mandrill_id(resp):
    """
    here is the place where we handle situation with messages which are not
    being sent; just send message to admins and Sentry in case of fail
    """
    try:
        mandrill_id = resp[0]["_id"]
    except Exception:
        log.exception('Could not get mandrill id from resp: {}'.format(resp))
        mandrill_id = "."
    return mandrill_id


def parse_email(email, is_sender):
    from debra import models
    parts = email.split('_')
    if (parts[0] == 'i' and is_sender) or (parts[0] == 'b' and not is_sender):
        direction = models.MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND
    elif ((parts[0] == 'b' and is_sender) or
            (parts[0] == 'i' and not is_sender)):
        direction = models.MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER
    else:
        raise ValueError()
    pk = int(parts[1])  # Influencer or Brands id
    mailbox_id = int(parts[3])
    return (parts[0], direction, pk, mailbox_id)


def is_admin_or_contact_email(email):
    from debra.constants import ADMIN_EMAILS
    if email in ['sales@theshelf.com']:
        return True
    return (email in [a.get('admin_email') for a in ADMIN_EMAILS] or
            email in [a.get('contact_email') for a in ADMIN_EMAILS] or
            email in [x for _, x in settings.ADMINS])


def exclude_from_events(msg):
    return (is_admin_or_contact_email(msg.get('msg', {}).get('sender')) or
            is_admin_or_contact_email(msg.get('msg', {}).get('email')))


def is_test_email(email, is_sender):
    test_emails = [
        'atul@theshelf.com',
        'pavel@theshelf.com',
        'our.newsletter.list@gmail.com'
    ]
    test_influencers = [1205504, ]
    test_brands = [148634, ]
    if email in test_emails:
        return True
    try:
        user_type, direction, pk, mailbox_id = parse_email(email, is_sender)
    except Exception:
        return False
    if user_type == 'i':
        return pk in test_influencers
    elif user_type == 'b':
        return pk in test_brands
    return False


@task(name='debra.mail_proxy.handle_events', ignore_result=True)
def handle_events(events_data, to_save=True, events_backup=None):
    from debra.models import (
        MailProxyMessage, InfluencerJobMapping, MandrillEvent)
    from debra import helpers

    log.info("Got %d evnets data units" % len(events_data))

    if len(events_data) == 0:
        log.info("Returning")
        return

    if events_backup is None:
        events_backup = [None] * len(events_data)

    event_2_type = {
        "send": MailProxyMessage.TYPE_SEND,
        "open": MailProxyMessage.TYPE_OPEN,
        "click": MailProxyMessage.TYPE_CLICK,
        "spam": MailProxyMessage.TYPE_SPAM,
        "hard_bounce": MailProxyMessage.TYPE_BOUNCE,
    }

    log.info("Got {} events".format(len(events_data)))

    events_backup = [
        y for x, y in zip(events_data, events_backup)
        if not exclude_from_events(x)
    ]
    events_data = [x for x in events_data if not exclude_from_events(x)]
    log.info("Got {} events after filtering".format(len(events_data)))

    if len(events_data) == 0:
        log.info("Returning as nothing needs to be done")
        return

    mandrill_ids = [x.get('_id') for x in events_data if x.get('_id')]

    log.info("Getting corresponding messages from DB for %r" % mandrill_ids)

    messages_from_db = list(MailProxyMessage.objects.filter(
        mandrill_id__in=mandrill_ids,
        type=MailProxyMessage.TYPE_EMAIL
    ).values_list('mandrill_id', 'thread'))

    mandrill_id_2_thread = dict(messages_from_db)

    log.info("Mandrill_id_2_thread: %r" % mandrill_id_2_thread)
    log.info("Performing checks...")

    # check #1 for thread uniqueness
    thread_counts = Counter(
        [mandrill_id for mandrill_id, _ in messages_from_db])
    if any([x > 1 for x in thread_counts.values()]):
        log.info("[ADMIN NOTIFICATION] Thread uniqueness check")
        helpers.send_admin_email_via_mailsnake(
            "mandrill_id was found in multiple mailboxes",
            "('mandrill_id', 'thread_id') pairs: {},\n counts: {}".format(
                messages_from_db, thread_counts))

    # check #2 for missing messages in DB
    diff = set(mandrill_ids) - set(
        [mandrill_id for mandrill_id, _ in messages_from_db])
    if diff:
        log.info("[ADMIN NOTIFICATION] Missing messages in DB check")
        helpers.send_admin_email_via_mailsnake(
            "Mandrill events fired for missing emails", str(diff))

    events_for_save = []

    for n, (data, backup) in enumerate(zip(events_data, events_backup)):
        mandrill_id = data.get('_id')
        events_for_save.append(MailProxyMessage(
            thread_id=mandrill_id_2_thread.get(mandrill_id),
            msg=json.dumps(data),
            ts=datetime.datetime.utcfromtimestamp(int(data.get('ts'))),
            direction=MailProxyMessage.DIRECTION_NONE,
            type=event_2_type.get(data.get('event')),
            mandrill_id=mandrill_id
        ))
        if backup is None:
            log.info(
                "No backup found for #{} event, creating one...".format(n))
            events_backup[n] = MandrillEvent.objects.create(
                data=data, type=MandrillEvent.TYPE_EVENT)

        log.info(
            "Event found MandrillID: {} ThreadID: {}".format(
                mandrill_id, mandrill_id_2_thread.get(mandrill_id)))
    if not to_save:
        log.info("to_save == False, so not creating events data in DB")
    else:
        # save to DB
        log.info("Saving events data to DB")
        _zipped = zip(events_for_save, events_backup)
        for n, (event, backup) in enumerate(_zipped):
            try:
                event.save()
            except Exception:
                log.info("Failed to save event #{}".format(n))
            log.info("Saved backup.id %s to STATUS_SAVED" % backup.id)
            backup.status = MandrillEvent.STATUS_SAVED
            backup.save()

        # MailProxyMessage.objects.bulk_create(events_for_save)

    # handle 'open' and 'click' events
    opened_and_clicked_emails = [
        x.get('_id')
        for x in events_data
        if x.get('event') in ('open', 'click')
    ]

    log.info("Got {} 'open' and 'click' events".format(
        len(opened_and_clicked_emails)))

    opened_and_clicked_threads = set(
        [mandrill_id_2_thread.get(x) for x in opened_and_clicked_emails])

    # save notification to mongoDB
    # log.info("Saving brand notifications to mongoDB...")
    # for msg in opened_and_clicked_emails_from_db:
    #     if msg.direction == MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER:
    #         notification = {
    #             'text': "%s opened email on %s UTC" % (
    #                 msg.thread.influencer.name,
    #                 msg.ts.strftime("%b. %e, %Y - %H:%M")),
    #             'thread': msg.thread_id
    #         }
    #         notify_brand(msg.thread.brand_id, "mail", notification)

    log.info("Getting associated campaigns...")
    job_mappings = InfluencerJobMapping.objects.filter(
        status=InfluencerJobMapping.STATUS_INVITED,
        mailbox__in=opened_and_clicked_threads,
    )

    log.info("Should change campaigns statuses to RECEIVED: {}".format(
        job_mappings.values_list('id', flat=True)))

    if not to_save:
        log.info("to_save == False, so not changing campaign statuses DB")
    else:
        # save to DB
        log.info("Saving changes data to campaign statuses in DB")
        job_mappings.update(status=InfluencerJobMapping.STATUS_EMAIL_RECEIVED)

    for backup in events_backup:
        log.info("Saved backup.id %s to STATUS_PROCESSED" % backup.id)
        backup.status = MandrillEvent.STATUS_PROCESSED
        backup.save()

    print("Sleeping for 10s")
    time.sleep(10)


@task(name='debra.mail_proxy.handle_inbound', ignore_result=True)
def handle_inbound(inbound_data, admins_only=False, inbound_backup=None):
    from debra import models
    from debra import helpers

    log.info("Got %d inbound data units" % len(inbound_data))

    if len(inbound_data) == 0:
        log.info("Returning")
        return

    if inbound_backup is None:
        log.info("No backup provided")
        inbound_backup = [None] * len(inbound_data)

    for n, (data, backup) in enumerate(zip(inbound_data, inbound_backup)):

        if backup is None:
            log.info("No backup found for #{} message, creating one...".format(
                n))
            backup = models.MandrillEvent.objects.create(
                data=data, type=models.MandrillEvent.TYPE_INBOUND)
            log.info("Backup for #{} message created, id={}".format(
                n, backup.id))

        log.info("Preparing message #{}, backup_id={}".format(n, backup.id))

        ts = data.get('ts')
        msg = data.get('msg')
        raw_msg = msg.get('raw_msg')
        email_to = msg.get('email')
        attachments = msg.get('attachments', [])
        images = msg.get('images', [])

        try:
            r_type = email_to.split('_')[0]
        except Exception:
            # this should never happen if all emails are ok
            log.exception(
                "Wrong email_to, can't split it by underscore",
                "Wrong email: %s" % (email_to,))
            return HttpResponse()

        # mail from brand to influencer
        if r_type == "i":
            direction = models.MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER
            thread = models.MailProxy.objects.get(influencer_mail=email_to)

        # mail from influencer to brand
        if r_type == "b":
            direction = models.MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND
            thread = models.MailProxy.objects.get(brand_mail=email_to)

        log.info("#{} message: Brand={}, Influencer={}".format(
            n, thread.brand_id, thread.influencer_id))

        mandrill_message = {
            'text': msg.get('text'),
            'html': msg.get('html'),
            'subject': msg.get('subject'),
            'attachments': attachments,
            'images': images,
        }
        if direction == models.MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER:
            complete_message_brand_2_influencer(
                mandrill_message, thread, ts=ts)
        if direction == models.MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND:
            complete_message_influencer_2_brand(
                mandrill_message, thread, ts=ts)

        db_params = dict(
            direction=direction,
            thread=thread,
            msg=raw_msg,
            type=models.MailProxyMessage.TYPE_EMAIL
        )

        try:
            log.info(
                '\nSearching for #{} message (thread={}, direction={}) in '
                'database...'.format(n, thread.id, direction))
            msg = models.MailProxyMessage.objects.filter(**db_params)[0]
            log.info("#{} message is found".format(n))
        except IndexError:
            log.info("#{} message is not found".format(n))
            if admins_only:
                continue
            log.info("Sending #{} message to clients".format(n))
            resp = mailsnake_send(mandrill_message)

            log.info("Set status of backup.id=%r to STATUS_SENT" % backup.id)
            backup.status = models.MandrillEvent.STATUS_SENT
            backup.save()

            mandrill_id = get_mandrill_id(resp)
            log.info("Got ID for #{} message: {}".format(n, mandrill_id))

            log.info("Saving #{} message...".format(n))
            msg = models.MailProxyMessage.objects.create(
                ts=datetime.datetime.utcfromtimestamp(int(ts)),
                mandrill_id=mandrill_id,
                **db_params
            )

            thread.candidate_mapping.filter(
                campaign_stage=models.InfluencerJobMapping
                .CAMPAIGN_STAGE_WAITING_ON_RESPONSE
            ).update(
                campaign_stage=models.InfluencerJobMapping
                .CAMPAIGN_STAGE_NEGOTIATION,
                campaign_stage_prev=models.InfluencerJobMapping
                .CAMPAIGN_STAGE_WAITING_ON_RESPONSE)

            log.info("#{} message is saved: id={}".format(n, msg.id))
            log.info("Set status of backup.id=%r to STATUS_SAVED" % backup.id)
            backup.status = models.MandrillEvent.STATUS_SAVED
            backup.save()

            if is_invalid(resp):
                log.info(
                    "[ADMIN NOTIFICATION] Message #{} is invalid".format(n))
                body = 'INVALID mandrill message. Msg_id: {}'.format(msg.id)
                log.error(body)
                helpers.send_admin_email_via_mailsnake(body, body)

            if is_status(resp, 'rejected'):
                log.info("[ADMIN NOTIFICATION] Message #{} rejected".format(n))
                helpers.send_admin_email_via_mailsnake(
                    '''REJECTED mandrill message.
                        models.MailProxyMessage(id={})
                    '''.format(msg.id),
                    'Response: {}'.format(resp)
                )

            if attachments:
                log.info("Saving #{} message's attachments to DB...".format(n))
                msg.attachments = upload_message_attachments_to_s3(
                    msg, attachments.values(), True)
                msg.save()

            log.info(
                "Set status of backup.id=%r to STATUS_PROCESSED" % backup.id)
            backup.status = models.MandrillEvent.STATUS_PROCESSED
            backup.save()
        finally:
            log.info("Sending #{} message copy to admins...".format(n))
            mailsnake_send(mandrill_message, admins_only=True)

    print("Sleeping for 10s")
    time.sleep(10)


@task(name='debra.mail_proxy.handle_webhook', ignore_result=True)
def handle_webhook(batch_id, save_events=True, admins_only=False, celery=True):
    from debra import models

    # use this function to define which messages should be treated as test-data
    def is_test(x):
        # all data is non-test for now
        return False
        f = is_test_email
        return (f(x.get('msg', {}).get('email'), False) and
                f(x.get('msg', {}).get('sender'), True))

    # separates out 'inbound' and other event types
    def split_data(data):
        inbound_data = [x for x in data if x['event'] == 'inbound']
        events_data = [
            x for x in data
            if x['event'] in ('send', 'open', 'click', 'spam', 'hard_bounce')
        ]
        return inbound_data, events_data

    def create_backup(batch, event_type, data):
        return [
            models.MandrillEvent.objects.create(
                data=event_data, batch=batch, type=event_type)
            for event_data in data
        ]

    batch = models.MandrillBatch.objects.get(id=batch_id)
    webhook_data = batch.data

    test_data = [x for x in webhook_data if is_test(x)]
    customer_data = [x for x in webhook_data if not is_test(x)]

    log.info("Test data: {}, Customer data: {}".format(
        len(test_data), len(customer_data)))

    inbound_data, events_data = split_data(customer_data)

    log.info("Inbound: {}, events: {}".format(
        len(inbound_data), len(events_data)))

    log.info("Saving webhook raw data...")
    inbound_backup = create_backup(
        batch, models.MandrillEvent.TYPE_INBOUND, inbound_data)
    events_backup = create_backup(
        batch, models.MandrillEvent.TYPE_EVENT, events_data)

    if celery:
        handle_inbound.apply_async(
            args=[inbound_data, admins_only, inbound_backup],
            queue="celery_mandrill_2")
        handle_events.apply_async(
            args=[events_data, save_events, events_backup],
            queue="celery_mandrill_2")
    else:
        handle_inbound(inbound_data, admins_only, inbound_backup)
        handle_events(events_data, save_events, events_backup)

        all_events = models.MandrillEvent.objects.filter(
            batch__id=batch_id, type=models.MandrillEvent.TYPE_EVENT)
        print("Checking Events now: Total %d Processed %d" % (
            all_events.count(),
            all_events.filter(
                status=models.MandrillEvent.STATUS_PROCESSED).count()))
        all_inbound = models.MandrillEvent.objects.filter(
            batch__id=batch_id, type=models.MandrillEvent.TYPE_INBOUND)
        print("Checking Inbound now: Total %d Processed %d" % (
            all_inbound.count(),
            all_inbound.filter(
                status=models.MandrillEvent.STATUS_PROCESSED).count()))


@csrf_exempt
def mandrill_webhook(request):
    from debra import models
    from debra import helpers

    if request.method != "POST":
        return HttpResponse()

    try:
        webhook_data = json.loads(request.POST.get('mandrill_events', ''))
    except:
        log.exception("Mandrill JSON parse error.")
        return HttpResponse()

    try:
        batch = models.MandrillBatch.objects.create(data=webhook_data)
    except Exception:
        helpers.send_admin_email_via_mailsnake(
            "Failed to save mandrill batch", webhook_data)
        return HttpResponse(status=500)
    else:
        handle_webhook.apply_async(
            [batch.id, True, False, False], queue="celery_mandrill_2")

        return HttpResponse()


def send_test_email(brand, sender, subject, body, attachments=None):
    attachments = attachments or []

    mandrill_message = {
        'html': body,
        'subject': subject,
        # 'from_email': sender.email,
        'from_email': '{}_b_{}_id_{}@reply.theshelf.com'.format(
            sender.email.split('@')[0], brand.id, sender.id),
        'from_name': brand.name,
        'to': [{'email': sender.email, 'name': brand.name}]
    }

    if attachments:
        mandrill_message['attachments'], s3_attachments = collect_attachments(
            attachments)

    resp = mailsnake_send(mandrill_message)

    try:
        del resp[0]["email"]
        del resp[0]["_id"]
        return json.dumps(resp[0])
    except Exception:
        log.exception('Error parsing Mandrill response.')
        return json.dumps({})


def send_email(thread, sender, subject, body, direction, attachments=None,
               resend=None):
    from debra import models

    attachments = attachments or []

    if thread.initiator is None and sender is not None:
        thread.initiator = sender
        thread.save()

    mandrill_message = {
        'html': body,
        'subject': subject,
    }
    if direction == models.MailProxyMessage.DIRECTION_BRAND_2_INFLUENCER:
        complete_message_brand_2_influencer(mandrill_message, thread)
    if direction == models.MailProxyMessage.DIRECTION_INFLUENCER_2_BRAND:
        complete_message_influencer_2_brand(
            mandrill_message, thread, send=True)

    if attachments:
        mandrill_message["attachments"], s3_attachments = collect_attachments(
            attachments, resend=resend)

    resp = mailsnake_send(mandrill_message)
    raw_msg = message.Message()
    raw_msg["subject"] = subject
    raw_msg.set_payload(body)

    mandrill_id = get_mandrill_id(resp)

    if not resend:
        msg = models.MailProxyMessage.objects.create(
            thread=thread,
            msg=raw_msg.as_string(),
            ts=datetime.datetime.utcnow(),
            direction=direction,
            type=models.MailProxyMessage.TYPE_EMAIL,
            mandrill_id=mandrill_id
        )
        redis_cache.set('sb_{}'.format(msg.id), thread.subject, timeout=0)
    else:
        resend.mandrill_id = mandrill_id
        resend.save()
        msg = resend

    if is_invalid(resp):
        body = 'INVALID mandrill message. Msg_id: {}'.format(msg.id)
        log.error(body)
        mail_admins(body, body)

    if is_status(resp, 'rejected'):
        mail_admins(
            'REJECTED mandrill message. models.MailProxyMessage(id={})'.format(
                msg.id),
            'Response: {}'.format(resp)
        )

    if attachments and not resend:
        msg.attachments = s3_attachments
        msg.save()

    try:
        del resp[0]["email"]
        del resp[0]["_id"]
        return json.dumps(resp[0])
    except Exception:
        log.exception('Error parsing Mandrill response.')
        return json.dumps({})
