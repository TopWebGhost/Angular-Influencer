import datetime

import baker
from celery.decorators import task
from django.core import mail

import hanna.scripts
from xpathscraper import utils


@task(name="debra.admin_reports.duplicates_report", ignore_result=True)
@baker.command
def duplicates_report():
    start = datetime.datetime.now()
    title = 'Influencer duplicates'

    dups = None
    try:
        dups = hanna.scripts.find_influencer_duplicates()
    except:
        log.exception('')

    end = datetime.datetime.now()
    took_hours = (end - start).total_seconds() / 3600.0

    if dups is None:
        mail.mail_admins(title, 'Error when computing duplicates after %s hours' % took_hours)
    else:
        lines = ['Found %d duplicate influencers' % len(dups), '']
        for i, inf in enumerate(dups):
            lines.append('%d. %r' % (i, inf))
        mail.mail_admins(title, '\n'.join(lines))


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
