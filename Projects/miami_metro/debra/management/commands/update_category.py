from __future__ import absolute_import, division, print_function, unicode_literals
from django.core.management.base import BaseCommand
from debra.models import Category
import pandas

"""
Command line support to adding new categories in our database.
1. You can specify the name of the category and threshold as well as the input file name (path).
This will overwrite the content of category fields in the Database.
"""


class Command(BaseCommand):
    args = '<category> <threshold> <word_file>'
    help = 'Read category keywords from a file and update the category.'

    def handle(self, *args, **options):
        if len(args) != 3:
            self.stderr.write('Bad args: {}\n'.format(args))
            self.stderr.write('update_category {}\n'.format(self.args))
            return

        category_name = args[0]
        match_threshold = args[1]
        word_file_path = args[2]

        categories = list(Category.objects.filter(name=category_name))

        if len(categories) > 1:
            self.stderr.write('Multiple categories found for name "{}": \n'.format(
                category_name, categories))
            return

        if len(categories) == 0:
            self.stdout.write('Category "{}" not found. Creating one...\n'.format(category_name))
            category = Category.objects.create(name=category_name, match_threshold=match_threshold)
        else:
            category = categories[0]
            self.stdout.write('Found category: {}\n'.format(category))

        #words = self.read_words(word_file_path)
        words = self.read_from_csv(word_file_path)
        self.stdout.write('Loaded {} words.\n'.format(len(words)))

        category.keywords = words
        category.match_threshold = match_threshold
        category.save()

    def read_words(self, word_file_path):
        with open(word_file_path, 'r') as f:
            return [line.strip() for line in f.readlines()]

    # read from file, returns an array of unique phrases
    def read_from_csv(self, file_path):
        pan = pandas.read_csv(file_path)
        vals = pan.columns.values
        res = set()
        for v in vals:
            vv = pan[v]
            for a in vv:
                res.add(a)

        res_str = [str(r) for r in res]
        final_res = []
        for r in res_str:
            if r == 'nan':
                continue
            final_res.append(r.lower())

        return final_res
