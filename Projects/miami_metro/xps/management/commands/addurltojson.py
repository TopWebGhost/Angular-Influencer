import json
import os.path
import os
import subprocess

from django.core.management.base import BaseCommand

TEST_URLS_FILENAME = os.path.join(os.path.dirname(__file__), '../../fixtures/test_urls.json')

class Command(BaseCommand):
    args = '<url>'
    help = 'Adds url to test_urls.json'

    def handle(self, *args, **options):
        with open(TEST_URLS_FILENAME, 'r') as f:
            data = json.load(f)
        max_pk = max(u['pk'] for u in data)
        new_d = { 'pk': max_pk + 1, 'model': 'debra.ProductModel', 'fields': { 'prod_url': args[0] } }
        data.append(new_d)
        with open(TEST_URLS_FILENAME, 'w') as f:
            f.write(json.dumps(data, indent=2))
        self.stdout.write(str(max_pk + 1) + '\n')
        settings_module = os.environ.get('DJANGO_SETTINGS_MODULE')
        assert settings_module and settings_module != 'settings', 'Production settings module used'
        subprocess.call(['python', 'manage.py', 'loaddata', 'xps', 'test_urls'])
        subprocess.call(['python', 'manage.py', 'extractxpaths', '--test', str(max_pk + 1)])

