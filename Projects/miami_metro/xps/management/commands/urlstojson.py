import json

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    args = '<filename-with-urls>'
    help = 'Prints json for including in a fixture file'

    def handle(self, *args, **options):
        urls = [u.split() for u in open(args[0])]
        ds = [ { 'pk': None, 'model': 'xps.product', 'fields': { 'url': u } } for u in urls]
        self.stdout.write(json.dumps(ds, indent=2))

