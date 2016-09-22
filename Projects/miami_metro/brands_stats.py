from debra.models import *
import csv


def dt_to_timestamp(dt):
    import time
    return time.mktime(dt.timetuple())

def num_queries(brand, period_start, period_end, query_type):
    from debra.mongo_utils import get_query_tracking_col

    permissions = (
        UserProfileBrandPrivilages.PRIVILAGE_OWNER,
        UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR,
        UserProfileBrandPrivilages.PRIVILAGE_CONTRIBUTOR_UNCONFIRMED
    )

    period_start = dt_to_timestamp(period_start)
    period_end = dt_to_timestamp(period_end)

    col = get_query_tracking_col()
    total_queries = 0
    for relation in brand.related_user_profiles.all():
        if not relation.permissions in permissions:
            continue
        user_id = relation.user_profile.user.id
        queries = col.find({
            "meta.user_id": user_id,
            "ts": {"$gte": period_start, "$lte": period_end},
            "query_type": query_type
        })
        total_queries += queries.count()
    return total_queries

def mails_count(brand, period_start, period_end):
    """
    here we count how many emails were exchanged between influencers<>brands through our platform
    """
    count = 0
    for proxy in brand.mails.all():
        count += proxy.threads.filter(ts__gte=period_start, ts__lte=period_end, type=1).count()
    return count

def infs_contacted_count(brand, period_start, period_end):
    """
    here we count how many unique influencers were contacted in this time period
    """
    count = 0
    for proxy in brand.mails.all():
        if proxy.threads.filter(ts__gte=period_start, ts__lte=period_end, type=1).exists():
            count += 1
    return count


def run(start_date, search=False, profile_views=False, total_emails=False, influencers_contacted=False):
    import datetime
    from dateutil.relativedelta import relativedelta
    raw_data = ["Brand"]

    ps = start_date

    print "{0:=^31}".format("Number of search queries")

    # find all relevant brands
    brands = Brands.objects.prefetch_related('related_user_profiles__user_profile__user')
    brands = brands.prefetch_related('related_user_profiles__user_profile')
    brands = brands.prefetch_related('related_user_profiles')
    brands = brands.prefetch_related('mails')
    brands = brands.prefetch_related('saved_queries')
    brands = brands.filter(is_subscribed=True, blacklisted=False)
    brands = brands.exclude(domain_name='yahoo.com').exclude(domain_name='rozetka.com.ua')
    brands = brands.order_by('id')
    brands = [b for b in brands if b.mails.count() > 0 or b.saved_queries.count() > 0]

    # for output to a csv file that is saved in the /tmp
    while ps<datetime.datetime.now():
        raw_data.append(ps.strftime("%B %Y"))
        ps = ps + relativedelta(months=1)

    tod = datetime.datetime.today()
    if search:
        filename = '/tmp/search_%s.csv' % tod.strftime('%b:%y')
    if profile_views:
        filename = '/tmp/profileview_%s.csv' % tod.strftime('%b:%y')
    if total_emails:
        filename = '/tmp/total_emails_%s.csv' % tod.strftime('%b:%y')
    if influencers_contacted:
        filename = '/tmp/infs_contacted_%s.csv' % tod.strftime('%b:%y')

    output = open(filename, 'w')
    csvwriter = csv.writer(output, delimiter=',',quotechar='"', quoting=csv.QUOTE_MINIMAL)
    csvwriter.writerow(raw_data)

    if search:
        for brand in brands:
            row = [brand.name]
            ps = start_date
            while ps<datetime.datetime.now():
                #print "{0:=^31}".format(ps.strftime("%B %Y"))
                pe = ps + relativedelta(months=1)
                #for brand in brands:
                print "{0:<20} {1:>10} ".format(brand.name,num_queries(brand, ps, pe, "brand-search-query"))
                row.append(num_queries(brand, ps, pe, "brand-search-query"))
                ps = pe
            csvwriter.writerow(row)

    print "{0:=^31}".format("Number of blogger panels opened")
    if profile_views:
        for brand in brands:
            row = [brand.name]
            ps = start_date
            while ps<datetime.datetime.now():
                #print "{0:=^31}".format(ps.strftime("%B %Y"))
                pe = ps + relativedelta(months=1)
                print "{0:<20} {1:>10}".format(brand.name,num_queries(brand, ps, pe, "brand-clicked-blogger-detail-panel"))
                row.append(num_queries(brand, ps, pe, "brand-clicked-blogger-detail-panel"))
                ps = pe
            csvwriter.writerow(row)


    print "{0:=^31}".format("Number of emails")
    if total_emails:
        for brand in brands:
            row = [brand.name]
            ps = start_date
            while ps<datetime.datetime.now():
                print "{0:=^31}".format(ps.strftime("%B %Y"))
                pe = ps + relativedelta(months=1)
                print "{0:<20} {1:>10}".format(brand.name,mails_count(brand, ps, pe))
                row.append(mails_count(brand, ps, pe))
                ps = pe
            csvwriter.writerow(row)

    if influencers_contacted:
        for brand in brands:
            row = [brand.name]
            ps = start_date
            while ps<datetime.datetime.now():
                print "{0:=^31}".format(ps.strftime("%B %Y"))
                pe = ps + relativedelta(months=1)
                print "{0:<20} {1:>10}".format(brand.name,infs_contacted_count(brand, ps, pe))
                row.append(infs_contacted_count(brand, ps, pe))
                ps = pe
            csvwriter.writerow(row)


def campaigns_created():
    """
    Figure out how many campaigns are created within a given time period

    We can only estimate because campaigns don't go through our system.
    """
    import datetime
    from dateutil.relativedelta import relativedelta
    start = datetime.date(2014, 10 ,1)
    one_month = relativedelta(months=1)

    mp = MailProxy.objects.all()

    # find all that have at least 3 messages
    at_least_3 = set()

    for m in mp:
        mc = MailProxyMessage.objects.filter(thread=m)
        if mc.count() >= 4:
            at_least_3.add(m.id)

    print("got %d threads with at least 3 messages" % len(at_least_3))

    tod = datetime.date.today()
    while start <= tod:
        next = start + one_month
        count = 0
        for m in at_least_3:
            mc = MailProxyMessage.objects.filter(thread__id=m, ts__gte=start, ts__lte=next)
            if mc.count() >= 3:
                count += 1
        print("We have %d campaigns in [%s, %s]" % (count, start, next))
        start = next


if __name__ == "__main__":
    import datetime
    start_date = datetime.datetime(2014, 10, 1)
    run(start_date, search=True, profile_views=False, total_emails=False, influencers_contacted=False)
    run(start_date, search=False, profile_views=True, total_emails=False, influencers_contacted=False)
    run(start_date, search=False, profile_views=False, total_emails=True, influencers_contacted=False)
    run(start_date, search=False, profile_views=False, total_emails=False, influencers_contacted=True)

