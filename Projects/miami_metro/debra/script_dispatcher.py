import argparse
import pdb
from debra.models import Platform
import helpers as h
import sys

def update_blogs_from_xpaths(csv, start_i, end_i, max_posts=float("inf"), max_pages=float("inf")):
    """
    this command line function reads a csv file which contains information about blogs and their relevant xpaths and
    parses this information into a list of dictionaries to be fed to the Platform.update_blogs_from_xpaths function
    @return the result of Platform.update_blogs_from_xpaths (Number of blogs updated if completed, None if error hit)
    """
    blogs = h.read_csv_file(csv, delimiter='\t',
                            dict_keys=['blog_name', 'blog_url', 'post_urls', 'post_title', 'post_content', 'post_date',
                                       'post_comments', 'next_page', ''])
    return Platform.update_blogs_from_xpaths(blogs, int(start_i), int(end_i), max_posts=max_posts, max_pages=max_pages)


if __name__ == '__main__':
    start_index = sys.argv[1]
    end_index = sys.argv[2]
    update_blogs_from_xpaths('blog_xpaths.tsv', start_index, end_index, 1000, 1000)
