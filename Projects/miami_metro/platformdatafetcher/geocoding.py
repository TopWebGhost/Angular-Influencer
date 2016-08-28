"""Normalizing location entered by QA/got from a fetcher, using a geocoding API.
"""

import logging

import baker
from celery.decorators import task
from geopy import geocoders

from xpathscraper import utils
from debra import models
from platformdatafetcher import platformutils
from debra.constants import GOOGLE_API_KEY

from retrying import retry

log = logging.getLogger('platformdatafetcher.geocoding')

# delay geocoder initialization
geocoder = None
def get_geocoder():
    global geocoder
    if geocoder is None:
        geocoder = geocoders.GoogleV3(api_key=GOOGLE_API_KEY)
    return geocoder


def extract_address_component(ctype, components, multiple=False):
    res = []
    for component in components:
        if 'types' in component and ctype in component['types']:
            res.append(component)
    if not res:
        res = None
    elif multiple:
        return res
    else:
        try:
            res = res[0]['long_name']
        except:
            print "Nothing to extract!"
    return res


@retry(stop_max_attempt_number=3, stop_max_delay=10000, wait_fixed=3000)
def get_location_data(value):
    return get_geocoder().geocode(value, timeout=20)


def handle_influencer_demographics(inf, diff_only=False):
    with platformutils.OpRecorder('normalize_location', influencer=inf) as opr:
        if not inf.demographics_location:
            log.warn('No location to process')
            return
        loc = get_location_data(inf.demographics_location)

        log.info(u'Got location from {}: {}'.format(inf.demographics_location, loc))
        if loc is None or not loc.address:
            log.warn(u'Location not geocoded: {}'.format(inf.demographics_location))
            return

        address_components = loc.raw['address_components']

        changed = False
        if loc.raw is not None:
            country = extract_address_component('country', address_components)
            state = extract_address_component('administrative_area_level_1', address_components)
            city = extract_address_component('locality', address_components)
            try:            
                locality, created = models.DemographicsLocality.objects.get_or_create(
                    country=country, state=state, city=city)
            except models.DemographicsLocality.MultipleObjectsReturned:
                locality = models.DemographicsLocality.objects.filter(
                    country=country, state=state, city=city)[0]
                created = False
            changed = inf.demographics_locality != locality
            inf.demographics_locality = locality

        # changed = changed or inf.demographics_location_normalized != loc.address
        inf.demographics_location_normalized = loc.address

        if loc.latitude is not None:
            changed = changed or inf.demographics_location_lat != loc.latitude
            inf.demographics_location_lat = loc.latitude
        if loc.longitude is not None:
            changed = changed or inf.demographics_location_lon != loc.longitude
            inf.demographics_location_lon = loc.longitude
        if (diff_only and changed) or not diff_only:
            inf.save()
        return changed

def fix_demographic_location(frange=None, srange=None):
    q = models.Influencer.objects.exclude(demographics_location__isnull=True).exclude(demographics_location='').exclude(demographics_location_normalized='').exclude(demographics_location_normalized__isnull=True).order_by('id')
    if frange:
        if srange:
            q = q[frange:srange]
        else:
            q = q[:frange]
    total = q.count()

    print 'Handling influencers edit history, total number of edited objects: {}'.format(total)

    import timeit
    current = 1
    for a in q:
        for attempt in range(1, 4):
            try:
                handle_influencer_demographics(a)
                break
            except Exception, e:
                print str(e)
                print 'retrying...'
        else:
            print 'Some error occured, we cannot fill location values for this influencer.'
            with open('/home/walrus/location.log', 'a') as f:
                f.write(str(a.id) + '\n')

        print u'processed id={}, "{}", {}/{} ({}%)  ===> {}'.format(a.id, a.demographics_location_normalized, current, total, current * 100.0 / total, a.demographics_locality)
        current += 1



@task(name='platformdatafetcher.geocoding.normalize_location', ignore_result=True)
@baker.command
def normalize_location(inf_id, diff_only=False):
    inf = models.Influencer.objects.get(id=inf_id)
    handle_influencer_demographics(inf, diff_only=diff_only)


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
