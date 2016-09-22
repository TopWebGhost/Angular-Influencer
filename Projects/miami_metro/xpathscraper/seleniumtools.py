import os
import os.path
import copy
import threading
import logging

from selenium import webdriver
from selenium.webdriver.common.proxy import Proxy
import selenium.webdriver.remote.webelement
from selenium.webdriver.firefox import firefox_profile

from . import utils

log = logging.getLogger(__name__)


PAGE_LOAD_TIMEOUT = 180
FIREFOX_PROFILE_DIR = os.path.join(os.path.dirname(__file__), 'seleniumdata/firefoxprofile')


class ElWrap(object):
    """Enable proper __eq__ and __hash__ for Selenium's WebElement
    """
    def __init__(self, el):
        assert isinstance(el, selenium.webdriver.remote.webelement.WebElement)
        self.el = el

    def __cmp__(self, other):
        return cmp(self._id, other._id)

    def __hash__(self):
        return hash(self._id)

    def __repr__(self):
        return '<elwrap>'


class InPlaceFirefoxProfile(firefox_profile.FirefoxProfile):
    def __init__(self, profile_directory):
        self.default_preferences = copy.deepcopy(
            firefox_profile.FirefoxProfile.DEFAULT_PREFERENCES)
        self.profile_dir = profile_directory
        self.tempfolder = None
        self._read_existing_userjs()
        self.extensionsDir = os.path.join(self.profile_dir, "extensions")
        self.userPrefs = os.path.join(self.profile_dir, "user.js")
    def _install_extension(self, *args, **kwargs):
        try:
            firefox_profile.FirefoxProfile._install_extension(self, *args, **kwargs)
        except OSError:
            pass


def driver_pid(driver):
    return driver.binary.process.pid

def set_firefox_profile_prefs(profile, logs=False):
    # profile.set_preference("plugin.state.flash", 0);
    # profile.set_preference('dom.ipc.plugins.enabled.libflashplayer.so', 'false')

    profile.set_preference("media.volume_scale", "0.0");
    profile.set_preference('dom.disable_open_during_load', True)
    profile.set_preference('dom.max_script_run_time', 0)
    profile.set_preference('dom.max_chrome_script_run_time', 0)
    profile.set_preference('security.fileuri.origin_policy', 4)
    profile.set_preference('security.fileuri.strict_origin_policy', False)
    profile.set_preference("capability.policy.policynames", "localfilelinks");
    profile.set_preference("capability.policy.localfilelinks.sites", "http://localhost http://localhost:8000")
    profile.set_preference("capability.policy.localfilelinks.checkloaduri.enabled", "allAccess")
    profile.set_preference('security.mixed_content.block_active_content', False)
    profile.set_preference('devtools.hud.loglimit.console', 1000)
    profile.set_preference('security.csp.enable', False)
    profile.set_preference('security.csp.speccompliant', False)
    profile.set_preference('security.OCSP.enabled', False)
    profile.set_preference('security.turn_off_all_security_so_that_viruses_can_take_over_this_computer', True)
    if logs:
        webdriver_log = '/tmp/webdriver-%s-%s.log' % (os.getpid(), threading.current_thread().ident)
        profile.set_preference("webdriver.log.file", webdriver_log)
        firefox_log = '/tmp/firefox-%s-%s.log' % (os.getpid(), threading.current_thread().ident)
        profile.set_preference("webdriver.firefox.logfile", firefox_log)
        log.info('webdriver log: %s', webdriver_log)
        log.info('firefox log: %s', firefox_log)

def create_default_driver(load_no_images=False, custom_proxy=None):
    kwargs = {}

    my_proxy = custom_proxy or os.getenv('http_proxy')
    if my_proxy:
        # Firefox requires proxy address withtout 'http', Linux requires 'http',
        # so the setting in the 'http_proxy' env. var. should contain http and we
        # strip it here.
        my_proxy = utils.remove_prefix(my_proxy, 'http://')
        proxy_args = {
            'proxyType': 'MANUAL',
            'httpProxy': my_proxy,
            'sslProxy': my_proxy,
            'noProxy': '127.0.0.1,localhost',
        }
        os.putenv('no_proxy', '127.0.0.1,localhost')
        kwargs['proxy'] = Proxy(proxy_args)

    profile = firefox_profile.FirefoxProfile()
    set_firefox_profile_prefs(profile)
    if load_no_images:
        log.debug('Turning off image loading for Firefox')
        profile.set_preference('permissions.default.image', 2)

    log.debug('Creating Firefox window')
    driver = webdriver.Firefox(profile, **kwargs)
    log.debug('Created pid=%s', driver_pid(driver))

    driver.set_page_load_timeout(PAGE_LOAD_TIMEOUT)

    return driver

def load_js_files(driver, filenames):
    for fn in filenames:
        log.debug('Executing %s', fn)
        with open(fn, 'r') as f:
            script = f.read()
            driver.execute_script(script)
        log.debug('Executed')

def execute_jsfun(driver, fun, *args):
    args_str = ', '.join('arguments[%d]' % i for i in range(len(args)))
    call_str = 'return {fun}({args_str})'.format(fun=fun, args_str=args_str)
    res = driver.execute_script(call_str, *args)
    return res

def elements_equivalent(e1, e2):
    return e1._id == e2._id

def element_lists_equivalent(els1, els2):
    if len(els1) != len(els2):
        return False
    return all(elements_equivalent(e1, e2) for e1, e2 in zip(els1, els2))

def element_sets_equivalent(els1, els2):
    return set(e._id for e in els1) == set(e._id for e in els2)

def el_distance(starting_elts, visited, target_el):
    '''Graph search of target_el, starting from starting_elts.
    Returns distance between the nearest starting_elt and target_el.
    '''
    assert starting_elts
    if target_el in starting_elts:
        return 0
    # FIXME: reference JS functions not lxml
    neighbours = {e.getparent() for e in starting_elts}
    for e in starting_elts:
        neighbours.update(e.getchildren())
    neighbours = {n for n in neighbours if n is not None}
    new_starting_elts = neighbours - visited
    new_visited = visited | neighbours
    return 1 + el_distance(new_starting_elts, new_visited, target_el)

