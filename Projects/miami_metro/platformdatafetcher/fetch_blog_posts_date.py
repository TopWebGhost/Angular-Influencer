from random import randint
import random
from time import sleep
from lxml.html import document_fromstring, fromstring
import requests
from requests.exceptions import Timeout, ConnectionError, TooManyRedirects
from datetime import datetime, timedelta
from requests.packages.urllib3.exceptions import DecodeError
from selenium.common.exceptions import NoSuchElementException
from debra.models import Posts
from debra.elastic_search_helpers import es_influencer_query_runner_v2
import re
import dateutil.parser
import time
from xpathscraper import xbrowser
from django.conf import settings
from xpathscraper.seleniumtools import create_default_driver
import logging


logger = logging.getLogger('platformdatafetcher.fetch_blog_posts_date')


PROXY_CONFIGS = [
    {
        'http': 'http://atul%40theshelf.com:duncan3064@us.proxymesh.com:31280',
        'https': 'http://atul%40theshelf.com:duncan3064@us.proxymesh.com:31280',
    },
    {
        'http': 'http://atul%40theshelf.com:duncan3064@uk.proxymesh.com:31280',
        'https': 'http://atul%40theshelf.com:duncan3064@uk.proxymesh.com:31280',
    },
]


requests_headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 6.1; rv:12.0) Gecko/20100101 Firefox/12.0'}

# expression to match date in format of "AUGUST 18, 2015"
date_expression_01 = "(?i)(?:january|february|march|april|may|june|july|august|september|october|november|december){1}\s+(?:\d{1,2})(?:,|.)(?:st|nd|rd|th){0,1}\s+(?:\d{4})"

# expression to match date in format 1/1/2015
date_expression_02 = "(?i)\d{1,2}[\D\W]{1}\d{1,2}[\D\W]{1}\d{4}"

# expression to match date in format '23. May 2015'
date_expression_03 = "(?i)\d{1,2}[\D\W]{0,1}\s{0,1}\w{3,10}\s{0,1}\d{4}"

def fetch_blog_posts_date(url):
    """
    Searches for Post's Date in current blog posts's url.
    :param url: - url of the post
    :return: fetched datetime as string, method_name as string, title of the page
    """
    result = {
        'status_code': None,
        'title': None,
        'date_published': None,
        'description': None
    }
    if not url:
        return result

    try:
        # print('performing url: %s' % url)

        response = requests.get(url, timeout=10, headers=requests_headers)
        result['status_code'] = response.status_code
        if response.status_code >= 400:
            result['description'] = 'http_error'
            return result

        try:
            page = fromstring(bytes(response.content.decode("UTF-8", "ignore").encode("UTF-8")))
        except:
            result['description'] = 'xml_malformed'
            return result

        title = ''
        # getting title
        titles = page.xpath("//meta[@property='og:title']/@content")
        if len(titles) > 0:
            title = titles[0]

        # First we getting title from /feed page if it exists. If not, we try to fetch /post/comments page.
        # If it does not exists also, we take title from the current page.
        if len(title) == 0:
            try:
                response = requests.get("%s%sfeed" % (url, '' if url.endswith('/') else '/'),
                                        timeout=5,
                                        headers=requests_headers)
                if response.status_code == 200:
                    pg = fromstring(response.content)
                    titles = pg.xpath('//title/text()')
                    if len(titles) > 0 and titles[0].startswith('Comments on: '):
                        title = titles[0].replace('Comments on: ', '', 1)
            except Timeout:
                pass

        if len(title) == 0:
            comments_default_urls = page.xpath("//link[re:test(@href, 'feeds\/\d+\/comments\/default')]/@href",
                                               namespaces={'re': 'http://exslt.org/regular-expressions'})
            if len(comments_default_urls) > 0:
                try:
                    response = requests.get(comments_default_urls[0], timeout=5, headers=requests_headers)
                    if response.status_code == 200:
                        pg = fromstring(response.content)
                        titles = pg.xpath('//feed/title/text()')
                        if len(titles) > 0 and titles[0].startswith('Comments on '):
                            title = titles[0].replace('Comments on ', '', 1)
                except Timeout:
                    pass

        if len(title) == 0:
            page_title = page.xpath("//title/text()")
            # title = title[0].encode('ascii', 'ignore') if title else ''
            if page_title is not None and len(page_title) > 0:
                title = page_title[0]

        result['title'] = ' '.join(title.split())

        # 1. Fetching metas and fields where date format is standard
        meta_published_time = page.xpath("//meta[@property='article:published_time']/@content")
        meta_sailthru_time = page.xpath("//meta[@name='sailthru.date']/@content")
        time_datepublished = page.xpath("//time[@itemprop='datePublished']/@datetime")
        abbr_datepublished = page.xpath("//abbr[@itemprop='datePublished']/@title")
        # recheck
        time_pubdate = page.xpath("//time[@pubdate and @datetime]/@datetime")
        # this one needs to be checked additionally
        time_datetime = page.xpath("//time[@datetime]/@datetime")

        if meta_published_time:
            result['date_published'] = dateutil.parser.parse(meta_published_time[0])
            result['description'] = 'meta_published_time'
            return result
        elif meta_sailthru_time:
            result['date_published'] = dateutil.parser.parse(meta_sailthru_time[0])
            result['description'] = 'meta_sailthru_time'
            return result
        elif time_datepublished:
            result['date_published'] = dateutil.parser.parse(time_datepublished[0])
            result['description'] = 'time_datepublished'
            return result
        elif time_pubdate:
            result['date_published'] = dateutil.parser.parse(time_pubdate[0])
            result['description'] = 'time_pubdate'
            return result
        elif abbr_datepublished:
            result['date_published'] = dateutil.parser.parse(abbr_datepublished[0])
            result['description'] = 'abbr_datepublished'
            return result
        elif time_datetime:
            result['date_published'] = dateutil.parser.parse(time_datetime[0])
            result['description'] = 'time_datetime'
            return result

        # 2. Finding tags containing dates by regexps
        # common for blogspot and derivatives
        json_datepublished = page.xpath(".//*[re:test(text(), '(?i)\"datePublished\"\s*:\s*\"[\d\w\:-]+\"')]/text()",
                                        namespaces={'re': 'http://exslt.org/regular-expressions'})
        if json_datepublished:
            for txt in json_datepublished:
                datetime_txt_part = re.findall(r'(?i)\"datePublished\"\s*:\s*\"[\d\w\:-]+\"', txt)
                if datetime_txt_part and len(datetime_txt_part) > 0:
                    result['date_published'] = dateutil.parser.parse(datetime_txt_part[0].split(':')[1])
                    result['description'] = 'json_datepublished'
                    return result

        nodes_with_date = page.xpath(".//div[@class='date-outer']//h2[@class='date-header']/text()")
        nodes_with_date = nodes_with_date + page.xpath(".//p[@class='blog-date']//span[@class='date-text']/text()")
        nodes_with_date = nodes_with_date + page.xpath(".//div//span[@class='entry-date']/text()")

        # plain date search by text, like 'January 12, 2015'
        nodes_with_date = nodes_with_date + page.xpath(
            ".//*[re:test(text(), '%s')]/text()" % date_expression_01,
            namespaces={'re': 'http://exslt.org/regular-expressions'})

        if nodes_with_date:
            for txt in nodes_with_date:
                date_regexp_01_part = re.findall(date_expression_01, txt)
                if date_regexp_01_part and len(date_regexp_01_part) > 0:
                    result['date_published'] = dateutil.parser.parse(date_regexp_01_part[0])
                    result['description'] = 'date_regexp_01'
                    return result
                date_regexp_02_part = re.findall(date_expression_02, txt)
                if date_regexp_02_part and len(date_regexp_02_part) > 0:
                    result['date_published'] = dateutil.parser.parse(re.sub('[/]', '.', date_regexp_02_part[0]))
                    result['description'] = 'date_regexp_02'
                    return result
                date_regexp_03_part = re.findall(date_expression_03, txt)
                if date_regexp_03_part and len(date_regexp_03_part) > 0:
                    result['date_published'] = dateutil.parser.parse(date_regexp_03_part[0])
                    result['description'] = 'date_regexp_03'
                    return result

        # if we did not get results this far, trying Google search
        xb = None
        try:
            # Creating webdriver with proxy
            proxy = random.choice(PROXY_CONFIGS)
            xb = xbrowser.XBrowser(
                headless_display=settings.AUTOCREATE_HEADLESS_DISPLAY,
                disable_cleanup=False,
                custom_proxy=proxy['http']
            )

            # setting timeouts to xb instance
            xb.driver.set_page_load_timeout(10)
            xb.driver.set_script_timeout(10)
            xb.driver.implicitly_wait(10)

            sleep(randint(8, 15))

            # opening google search page in browser
            try:
                xb.load_url('http://google.com?hl=en')
            except Exception as e:
                print('Exception while loading google.com page and performing scripts: %s' % e)
                result['description'] = 'google_init_error'
                return result

            # finding input element, putting there the given url and press search button
            time.sleep(2)
            try:
                input_field = xb.driver.find_elements_by_xpath('//input[@title="Search"]')
                if input_field:
                    input_field = input_field[0]
                    input_field.send_keys(url)
                    time.sleep(1)
                    submit_button = xb.driver.find_elements_by_xpath('//button[@value="Search"]')
                    if submit_button:
                        submit_button[0].click()

            except NoSuchElementException as e:
                print('No input field found on google.com')
                print(e)
                result['description'] = 'google_input_locating_error'
                return result

            # fetching results from the page
            time.sleep(1)

            # Here we are fetching results from google result page for search
            try:
                g_divs = xb.driver.find_elements_by_xpath("//div[@class='g']")
                if g_divs:
                    for g_div in g_divs:
                        url_to_site = g_div.find_element_by_xpath(".//a")
                        if url in url_to_site.get_attribute('href'):
                            possible_date_chunk = g_div.find_element_by_xpath(".//span[@class='f']")
                            if possible_date_chunk:
                                if 'ago' in possible_date_chunk.text:
                                    date_chunks = possible_date_chunk.text.split()
                                    if len(date_chunks) > 0 and is_integer(date_chunks[0]):
                                        result['date_published'] = datetime.utcnow() - timedelta(days=int(date_chunks[0]))
                                        result['description'] = 'google_search'
                                        return result
                                else:
                                    date_chunks = "".join(possible_date_chunk.text.replace("-", "").split(",")).split()
                                    if len(date_chunks) >= 3 and is_integer(date_chunks[1]) and is_integer(date_chunks[2]):
                                        result['date_published'] = dateutil.parser.parse(possible_date_chunk.text.replace("-", ""))
                                        result['description'] = 'google_search'
                                        return result
                            break
            except NoSuchElementException:
                # did not find elements on a page (divs of results, url in div or date)
                pass
        except Exception as e:
            logger.exception(e, extra={'url': url})
        finally:
            if xb:
                try:
                    xb.driver.quit()
                except:
                    pass

        # PREVIOUS GOOGLE ALGORITHM WITH GOOGLE API
        # if len(result['title']) > 0:
        #     # q = ""
        #     # parsed_url = urlparse(url)
        #     # q += "site:%s " % parsed_url.netloc
        #     # q += " ".join(result['title'].split())
        #
        #     google_response = requests.get(
        #         'https://ajax.googleapis.com/ajax/services/search/web',
        #         params={
        #             'v': '1.0',
        #             'hl': 'ru',
        #             'gl': 'ru',
        #             # 'rsz': 8,
        #             # 'safe': 'active',
        #             # 'filter': 0,
        #             'q': url
        #         },
        #         timeout=10,
        #         headers={
        #             'Referer': 'http://theshelf.com',
        #             'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Ubuntu Chromium/43.0.2357.81 Chrome/43.0.2357.81 Safari/537.36',
        #         }
        #     )
        #
        #     # print('google response status: %s' % google_response.status_code)
        #     if google_response.status_code < 400:
        #         google_json = google_response.json()
        #         print('RESPONSE GOOGLE:')
        #         pprint(google_json)
        #         if google_json:
        #             response_data = google_json.get('responseData', [])
        #             if response_data and 'results' in response_data:
        #                 for entry in response_data['results']:
        #                     if entry['url'] == url:
        #                         possible_date_chunk = entry.get('content', '')[:12]
        #                         if 'ago' in possible_date_chunk:
        #                             date_chunks = possible_date_chunk.split()
        #                             if len(date_chunks) > 0 and is_integer(date_chunks[0]):
        #                                 result['date_published'] = datetime.utcnow() - timedelta(days=int(date_chunks[0]))
        #                                 result['description'] = 'google_search'
        #                                 return result
        #                         else:
        #                             date_chunks = "".join(possible_date_chunk.split(",")).split()
        #                             if len(date_chunks) == 3 and is_integer(date_chunks[1]) and is_integer(date_chunks[2]):
        #                                 result['date_published'] = dateutil.parser.parse(possible_date_chunk)
        #                                 result['description'] = 'google_search'
        #                                 return result

        result['description'] = 'date_not_found'
        return result

    except Timeout:
        result['description'] = 'status_timeout'
        return result
    except ConnectionError:
        result['description'] = 'connection_error'
        return result
    except TooManyRedirects:
        result['description'] = 'too_many_redirects'
        return result
    except DecodeError:
        result['description'] = 'decode_error'
        return result


def is_integer(s):
    """
    checks if s represents an integer number
    :param s:
    :return:
    """
    try:
        int(s)
        return True
    except ValueError:
        return False


def test_thousand():

    page = 1
    size = 1500

    _, influencer_ids, total = es_influencer_query_runner_v2({}, size, page)

    filename = 'datetimes_%s.csv' % datetime.strftime(datetime.utcnow(), '%Y-%m-%d_%H%M%S')
    csvfile = open(filename, 'a+')
    csvfile.write('Num\tInfluencer_Id\tPost_Id\tPost_URL\tStatus_code\tDate_Published\tMethod\tTitle\n')
    csvfile.close()

    ctr = 0
    found_counter = 0
    not_found_counter = 0
    for influencer_id in influencer_ids:
        post = Posts.objects.filter(influencer__id=influencer_id,
                                    platform__platform_name__in=['Blogspot', 'Wordpress', 'Custom'])
        if post.count() > 0:
            result = fetch_blog_posts_date(post[0].url)
            print(result)
            if result['status_code'] is not None and result['status_code'] < 400:
                if result['date_published'] is not None:
                    found_counter += 1
                else:
                    not_found_counter += 1

                csvfile = open(filename, 'a+')
                csvfile.write('%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' % (
                    ctr,
                    influencer_id,
                    post[0].id,
                    post[0].url,
                    result['status_code'],
                    result['date_published'],
                    result['description'],
                    "".join(result['title'].encode('ascii', 'replace').split()) if result['title'] else ''))
                csvfile.close()

                ctr += 1
        if ctr % 100 == 0:
            print('%s documents performed' % ctr)

        if ctr >= 1000:
            break

    csvfile = open(filename, 'a+')
    csvfile.write('Total:\t%s\tWith_date:\t%s\tWithout_date:\t%s\n' % (page*size, found_counter, not_found_counter))
    csvfile.close()


def test_several():
    urls = [
        # "http://withlovefromkat.com/leather-pencil-skirt-with-plaid-shirt/",
        # "http://dgmanila.com/2015/08/the-lazy-blazer/",
        # "http://sunday-suppers.blogspot.com/2010/03/beet-sandwich-with-ricotta-orange.html",
        # "http://www.miarmarioenruinas.com/beautiful-embroidered-shirt/",
        # "http://mariezamboli.com/versace-pop-medusa-sunglasses/",

        # "http://kerihilsondaily.blogspot.com/2015/07/koniec-czekania-keri-zapowiada-nowy.html",
        # "http://l0ve.blogg.no/1440712771_bday.html",
        # "http://www.studiodiy.com/2015/08/27/diy-emoji-heart-balloons/",

        # "http://www.mynewroots.org/site/2015/08/tesss-blueberry-breakfast-mystical-mango-smoothies/",

        # "http://www.bakerella.com/peanut-butter-brownie-ripple-ice-cream/",
        # "http://stupideasypaleo.com/2015/09/01/harder-to-kill-radio-017-why-abs-arent-everything-with-diana-rodgers/",

        # "https://travellingisblog.wordpress.com/2015/08/16/feast-at-faasos/",
        # "http://www.kendieveryday.com/2015/08/flower-power.html",
        # "http://andreabadendyck.blogg.no/1441038585_5_nye_skatter.html",

        # "http://www.pragmaticmom.com/2015/08/tyson-project-a-for-school-fundraising/",
        # "http://www.blogcoisasquegosto.com.br/2015/08/maquiagem-e-penteado-profissional.html",
        # "http://desafiosgastronomicos.blogspot.com/2014/02/desafio-torta-margherita-tao-leve.html",


        # "http://www.bakerella.com/peanut-butter-brownie-ripple-ice-cream/",
        # "http://myfashavenue.com/2015/08/rihanna-x-puma-foreverfaster/",
        # "http://lucyandlydiablog.blogspot.com/2015/08/our-current-hair-care-routine.html",
        # "http://www.brooklynblonde.com/2015/08/on-go.html",
        # "http://www.chickettes.com/chickettes-is-on-vacation/",
        # "http://anastasiac.blogspot.com/2015/07/mood-boards-for-inspiration.html",
        # "http://www.bobwilson123.org/home/may-04th-2015",
        # "http://www.tourisme-montreal.org/blog/things-to-do-in-montreal-august-21-to-27/",
        # "http://www.styledumonde.com/2015/08/paris-fashion-week-fw-2015-street-style-aimee-song-3/",
        # "http://www.babyboybakery.com/2015/08/working-on-something-new.html",
        # "http://wolfcubchronicles.com/",
        # "http://www.iwantyoutoknow.co.uk/2015/08/etsy-blogger-sleepover-in-brighton.html",
        # "http://www.thehonesttoddler.com/2015/08/toddler-news-mom-shares-her-sons.html",
        # "http://www.eat-yourself-skinny.com/2014/08/diy-how-to-make-glitter-letters.html",
        # "http://beckermanbiteplate.blogspot.com/2015/09/biore-deep-cleansing-pore-strips.html",
        # "http://www.jaaackjack.com/2015/08/planner-decorating-made-easy.html",
        # "http://www.marcussamuelsson.com/ginnys-superclub/make-it-messy-with-marcus-samuelsson-at-ginnys-supper-club",
        # "http://onedapperstreet.com/grown/",
        # "http://www.thesweetestthingblog.com/2015/08/howtostyleaponchofall.html",
        # "http://www.rachmartino.com/2015/08/a-splash-of-citrus.html",
        # "http://carolinesmode.com/sv/fanny-ekstrand-6/",
        # "http://heroinered.blogspot.com/2015/05/my-art-school-experience.html",
        # "http://www.notjustanothermilla.com/phnom-penh/",
        # "http://blog.krisatomic.com/?p=7274",
        # "http://www.thehappysloths.com/2015/08/charlotte-tilbury-cheek-to-chic-swish-and-pop-blusher-ecstasy-review-swatches.html",
        # "http://www.beautyandfashiontech.com/2015/08/hemp-oil-for-health-charlottes-web-gel-infused-pen.html",
        # "http://waitbutwhy.com/2015/08/how-and-why-spacex-will-colonize-mars.html",
        # "http://www.modacapital-blog.com/2015/09/corduroy-trend-comeback.html",
        # "http://nicoleandersson.blogspot.com/2015/08/back-in-trenches.html",
        # "http://everythingcurvyandchic.com/2015/07/nude-and-lace-lookbook/",
        # "http://www.nanysklozet.com/2015/08/no-one-cares.html",
        # "http://www.beautyinthebag.com/wordpress/not-done-gorgeous-giveaway-from-neostrata/",
        # "http://www.snapshotfashion.com/blog/2015/9/1/cover-story-vogue-september-2015",
        # "http://www.blogmilkblog.com/2015/08/sale.html",
        # "http://www.frenchcountrycottage.net/2015/08/thoughts.html",
        # "http://tomandlorenzo.com/2015/09/girl-thats-not-your-dress-lorde-in-mary-katrantzou-at-2015-vma-after-party/",
        # "http://damselindior.com/firepits/",
        # "http://stylebubble.co.uk/style_bubble/2015/09/the-first-time.html",
        # "http://www.proudduck.com/2015/08/potty-training-daniel/",
        # "http://www.jadore-fashion.com/2015/08/back-to-school.html",

        'https://www.thrillist.com/eat/austin/the-11-best-burgers-in-austin',
        'http://tastyquery.com/recipe/701222/the-best-bbq-chicken',
        'http://pelletsmokercooking.blogspot.ru/2015/08/smoked-chicken-with-butter-beans.html',
        'http://asunshinyday.com/step-by-steps-on-making-a-kick-a-pulled-pork-on-the-smoker/',
        'http://www.theskinnyfork.com/blog/stubbs-giveaway?rq=Stubb%27s',
        'http://www.realsimple.com/food-recipes/shopping-storing/condiments-you-need',
        'http://unorthodoxepicure.com/2015/08/20/rv-chronicles-ive-done-salted-my-peanuts-with-my-tv-watching/',
        'http://www.bigflavorstinykitchen.com/2015/08/spice-rubbed-smoked-country-style-ribs-with-farm-fresh-veggie-saute.html',
        'http://www.peanutbutterandpeppers.com/2015/08/19/the-best-bbq-chicken/',
        'http://insidetailgating.com/blog/2015/08/21/stubbs-bbq-chicken-dip/',
        'http://goodtaste.tv/2015/08/kickin-sides-for-bbq/',
        'http://www.aspiringsmalltowngirl.com/2015/08/crockpot-ginger-ale-pulled-pork/',
        'http://www.kitchen-concoctions.com/2015/08/grilled-steak-with-corn-and-green-chile.html',
        'http://smokinstevesblog.com/2015/08/11/stubbs-charcoal-briquettes/',
        'http://workplacegourmet.blogspot.ru/2015/08/nutritional-introspection.html',
        'https://cupcakesandsequins.wordpress.com/2015/08/11/homemade-bbq-chicken-pizza/',
        'https://jensdish.wordpress.com/2015/08/14/pizza-on-the-porch/',
        'http://newhope360.com/what-stock/unboxed-13-new-natural-meal-starters-convenience-foods#slide-0-field_images-1249511',
        'http://thefitfork.com/recipe/hatch-salmon-cakes-recipe-green-chile-fish-dinners/',
        'http://www.wgy.com/onair/real-newsmen-wear-aprons-56511/cooking-sauce-13902886',
        'http://www.theskinnyfork.com/blog/cheesy-spinach-verde-enchiladas?rq=Stubb%27s',
        'https://wedishnutrition.wordpress.com/2015/08/10/healthy-bbq-gluten-free/',
        'http://www.havingfunsaving.com/2015/08/how-to-smoke-great-ribs.html',
        'http://www.ohio.com/lifestyle/food/new-in-food-stubb-s-sauces-for-marinating-basting-dipping-1.613303?localLinksEnabled=false',
        'https://justkeeplivin.com/index.php/blog/best-bbq.html',
        'http://www.sweetandsavoryfood.com/2015/08/5-crock-pot-meals-x-2-10-dinners.html',
        'http://www.skinnymom.com/skinny-hawaiian-chicken-cups/',
        'http://gothicgranola.com/2015/08/hippie-dippy-lentil-loaf/',
        'http://tasteologie.notcot.org/post/76036/New-Fashioned-Cowboy-Beans-Ribs-Hopalong-Cassidy-would-/',
        'http://tasteologie.notcot.org/post/77685/Cheesy-Texas-Sriracha-Hatch-Poppers-Is-it-an-appetizer-/',
        'http://verygoodrecipes.com/meatball',
        'http://unorthodoxepicure.com/2015/08/09/the-rv-chronicles-tighter-than-an-elephant-in-a-suitcase/',
        'http://www.theskinnyfork.com/blog/sriracha-meatballs?rq=Stubb%27s',
        'http://unorthodoxepicure.com/2015/08/24/the-rv-chronicles-missing-my-rock/',
        'http://www.dixiechikcooks.com/bacon-wrapped-mini-jalapeno-corn-muffins/',
        'http://www.nola.com/healthy-eating/2015/08/3-day_diet_healthy_to_help_she.html',
        'http://www.austinchronicle.com/daily/food/2015-08-12/hatch-chiles-are-here-again/',
        'http://www.sweetandsavoryfood.com/2015/08/sweet-thai-chili-meatballs-stubbs-bar-b.html',
        'http://www.cookingmaiway.com/2015/08/02/this-was-our-fourth-of-july/',
        'http://www.playboy.com/articles/grilling-season-bbq-sauces',
        'http://grillgirl.com/2015/08/sriracha-skirt-steak-empanadas/',
        'http://www.nibblemethis.com/2015/08/high-low-beef-filet-with-marsala.html',
        'http://www.emilybites.com/2015/08/bacon-bbq-cheeseburger-quesadillas.html',
        'http://www.tmbbq.com/a-few-more-influential-pitmasters/',
        'http://www.makandhercheese.com/bbq-shrimp-and-grits/',
    ]

    not_found = 0
    found = 0
    for url in urls:
        result = fetch_blog_posts_date(url)
        print('Url: %s' % url)
        print('Title: %s' % result['title'])
        print('Date published: %s' % result['date_published'])
        print('Description: %s' % result['description'])
        print('Status_code: %s' % result['status_code'])
        print('=============================================')
        if result['description'] == 'date_not_found':
            not_found += 1
        else:
            found += 1
    print('FOUND: %s  NOT FOUND: %s' % (found, not_found))

