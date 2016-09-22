import logging
import json
import sys
import os.path

import requests
import baker
from django.conf import settings

from xpathscraper import utils


log = logging.getLogger(__name__)

SHOPSTYLE_BASE_URL = 'http://api.shopstyle.com/api/v2/products?pid=uid289-3680017-16&cat=dresses&limit=100'
SHOPSTYLE_LIMIT = 100


class ShopstyleFetcher(object):
    
    def fetch_colors(self, category, pages=1):
        for page_no in range(pages):
            r = requests.get(SHOPSTYLE_BASE_URL, params= {
                'offset': page_no * SHOPSTYLE_LIMIT,
                'cat': category,
            })
            for product in r.json().get('products', []):
                for color in product.get('colors', []):
                    if color.get('name'):
                        yield color.get('name')


@baker.command
def shopstyle_colors(category, pages):
    sf = ShopstyleFetcher()
    colors = []
    categories = [category]
    for cat in categories:
        new_colors = sf.fetch_colors(cat, int(pages))
        colors += new_colors
    colors = [c.lower() for c in colors]
    colors = list(set(colors))
    colors.sort()
    print json.dumps(colors, indent=2)

COLORS_FILE = os.path.join(settings.PROJECT_PATH, 'xpathscraper/json/colors.json')
@baker.command
def merge_colors():
    """Reads JSON list from stdin with color names, merges it with existing colors.json.
    """
    new_colors = json.load(sys.stdin)
    with open(COLORS_FILE) as f:
        old_colors = json.load(f)
    merged = old_colors + new_colors
    merged = list(set(merged))
    merged.sort()
    with open(COLORS_FILE, 'w') as f:
        json.dump(merged, f, indent=2)

if __name__ == '__main__':
    utils.log_to_stderr()
    baker.run()
