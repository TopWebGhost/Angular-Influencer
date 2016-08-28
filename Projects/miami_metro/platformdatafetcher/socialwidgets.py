import logging

import baker
import requests
import lxml.html
import urlparse
from selenium.common.exceptions import NoSuchElementException

from xpathscraper import utils
from platformdatafetcher import platformutils


log = logging.getLogger('platformdatafetcher.socialwidgets')


class SocialWidget(object):
    iframe_srcs = []
    iframe_ids = []
    # If also look at the main, root html document
    root_xpaths = []

    def find_owners_url(self, xbrowser):
        return None


class FacebookLikeBox(SocialWidget):
    iframe_srcs = [
        'facebook.com/plugins/like_box',
        'facebook.com/plugins/likebox',
    ]

    def find_owners_url(self, xbrowser):
        try:
            a_el = xbrowser.driver.find_element_by_xpath(
                '//span[@class="fsl fwb"]/a|//div[@class="pluginConnectButton"]/a'
            )
            return a_el.get_attribute('href')
        except NoSuchElementException:
            return None
        except Exception as e:
            log.exception(e)
            return None

class FacebookCommentBox(SocialWidget):
    iframe_srcs = ['facebook.com/plugins/comments']


class StatigramWidget(SocialWidget):
    iframe_srcs = ['statigr.am/widget']

    def find_owners_url(self, xbrowser):
        try:
            a_el = xbrowser.driver.find_element_by_xpath('//div[@id="header"]//a')
            if not a_el:
                return None
            return a_el.get_attribute('href')
        except Exception as e:
            log.exception(e)
            return None


class TagbrandWidget(SocialWidget):
    iframe_srcs = ['tagbrand.com/widget']
    # No username parsing, just marking this url as a widget's url


class GPlusBadgeWidget(SocialWidget):
    root_xpaths = [
        '//iframe[contains(@src, "plus.google.com")]'
    ]

    def find_owners_url(self, xbrowser):
        try:
            plus_iframes = xbrowser.driver.find_elements_by_xpath(self.root_xpaths[0])
            for iframe in plus_iframes:
                url_and_params = iframe.get_attribute('src')
                if url_and_params:
                    parsed = urlparse.urlparse(url_and_params)
                    query = urlparse.parse_qs(parsed.query)

                    # Try different query string params used by the different badge types.
                    gplus_urls = [param for param_name in ['url', 'blogFollowUrl', 'href']
                                  for param in query.get(param_name, [])]
                    for gplus_url in gplus_urls:
                        if 'plus.google.com' in gplus_url and platformutils.username_from_platform_url(gplus_url) is not None:
                            return platformutils.normalize_social_url(gplus_url)
        except Exception as e:
            log.exception(e)

        return None


class GPlusAboutWidget(SocialWidget):
    root_xpaths = [
        '//div[contains(@class, "widget-content")]//a[contains(@href, "plus.google.com")]',
    ]

    def find_owners_url(self, xbrowser):
        try:
            gplus_anchors = xbrowser.driver.find_elements_by_xpath(self.root_xpaths[0])
            if gplus_anchors:
                gplus_url = gplus_anchors[0].get_attribute('href')
                if platformutils.username_from_platform_url(gplus_url) is not None:
                    return platformutils.normalize_social_url(gplus_url)
        except Exception as e:
            log.exception(e)
        return None

class ChictopiaWidget(SocialWidget):
    iframe_srcs = ['chictopia.com']


class TwitterWidget(SocialWidget):
    iframe_ids = ['twitter-widget-']

    def find_owners_url(self, xbrowser):
        try:
            a_el = xbrowser.driver.find_elements_by_xpath('//a[@class="u-url profile"]')
            if a_el:
                return a_el[0].get_attribute('href')

            f_el = xbrowser.driver.find_elements_by_xpath('//a[@id="follow-button"]')
            if f_el:
                return platformutils.normalize_social_url(f_el[0].get_attribute('href'))

        except Exception as e:
            log.exception(e)

        return None


class WordpressTwitterWidget(SocialWidget):
    root_xpaths = [
        '//aside[contains(@class, "widget_twitter")]',
    ]

    def find_owners_url(self, xbrowser):
        try:
            title_els = xbrowser.driver.find_elements_by_xpath(
                self.root_xpaths[0] + '//h3[@class="widget-title"]/a')
            if not title_els:
                return None
            return title_els[0].get_attribute('href')
        except Exception as e:
            log.exception(e)
        return None


class SnapwidgetWidget(SocialWidget):
    root_xpaths = [
        '//div[@class="widget HTML"]//div[@class="widget-content"]'
    ]

    def find_owners_url(self, xbrowser):
        try:
            div_els = xbrowser.driver.find_elements_by_xpath(self.root_xpaths[0])
            for div in div_els:
                if div.text.strip().startswith('@'):
                    username = div.text.strip().lstrip('@').split()[0]
                    if not username:
                        return None
                    return 'https://instagram.com/%s' % username
        except Exception as e:
            log.exception(e)
        return None


class SnapwidgetIFrameWidget(SocialWidget):
    iframe_srcs = ['snapwidget.com/']

    def find_owners_url(self, xbrowser):
        try:
            a_els = xbrowser.driver.find_elements_by_xpath('//li//a[contains(@href, "snapwidget.com/v/")]')
        except Exception as e:
            log.exception(e)
            return None
        if a_els:
            try:
                link = a_els[0].get_attribute('href')
                r = requests.get(link, timeout=10)
                tree = lxml.html.fromstring(r.content)
                username_els = tree.xpath('//div[@class="username"]')
                if username_els:
                    username = username_els[0].text
                    if not username:
                        return None
                    username = username.strip()
                    return 'https://instagram.com/%s' % username
            except:
                log.exception('While fetching snapwidget content, skipping')
                return None


class AddthisTwitter(SocialWidget):
    root_xpaths = [
        '//a[contains(@class, "addthis_button_twitter_follow")]',
    ]

    def find_owners_url(self, xbrowser):
        try:
            a_els = xbrowser.driver.find_elements_by_xpath(self.root_xpaths[0])
            if a_els:
                tw_username = a_els[0].get_attribute('addthis:userid')
                if tw_username and len(tw_username) > 1:
                    return 'https://twitter.com/%s' % tw_username
        except Exception as e:
            log.exception(e)
        return None

class InstagramIconoSquareWidget(SocialWidget):
    iframe_srcs = ['iconosquare.com/']

    def find_owners_url(self, xbrowser):
        try:
            a_els = xbrowser.driver.find_elements_by_xpath('//a[contains(@href, "instagram.com/")]')
            if a_els:
                inst_url = a_els[0].get_attribute('href')
                if inst_url and len(inst_url) > 1:
                    return inst_url
        except Exception as e:
            log.exception(e)
        return None

WIDGET_CLASSES = [
    FacebookLikeBox,
    FacebookCommentBox,
    StatigramWidget,
    TagbrandWidget,
    GPlusBadgeWidget,
    GPlusAboutWidget,
    ChictopiaWidget,
    TwitterWidget,
    WordpressTwitterWidget,

    # Inline snapwidget cannot be detected reliably
    #SnapwidgetWidget,

    SnapwidgetIFrameWidget,
    AddthisTwitter,
    InstagramIconoSquareWidget,
]


def find_owner_urls_from_widgets(xbrowser):
    res = []

    for cls in WIDGET_CLASSES:
        if cls.root_xpaths:
            log.debug('Using class %r to find widget links in root html', cls)
            try:
                url = cls().find_owners_url(xbrowser)
            except:
                log.exception('While find_owners_url(), skipping')
                continue
            log.info('Found: %r', url)
            if url:
                res.append(url)

    iframes = xbrowser.driver.find_elements_by_tag_name('iframe')
    for iframe in iframes:
        xbrowser.driver.switch_to_default_content()
        try:
            src = iframe.get_attribute('src') or ''
            id = iframe.get_attribute('id') or ''
            if not src and not id:
                continue
        except:
            log.exception('While getting iframe src and id')
            continue
        log.debug('Processing iframe with id %r src %r', id, src)
        xbrowser.driver.switch_to_frame(iframe)
        for cls in WIDGET_CLASSES:
            if any(isrc in src.lower() for isrc in cls.iframe_srcs) or \
               any(iid in id.lower() for iid in cls.iframe_ids):
                log.debug('Found matching widget class: %r', cls)
                try:
                    url = cls().find_owners_url(xbrowser)
                except:
                    log.exception('While find_owners_url(), skipping')
                    continue
                if url:
                    log.debug('Found url: %r', url)
                    res.append(url)
                else:
                    log.debug('Cannot parse social widget url')
    xbrowser.driver.switch_to_default_content()
    return res


if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
