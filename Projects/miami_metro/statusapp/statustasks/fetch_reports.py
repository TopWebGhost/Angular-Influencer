import subprocess
import sys
import os.path
import datetime

BASE_URL = 'http://107.170.29.25:9000'
OUT_DIR = sys.argv[1]

URLS = [
    '/theshelf-status/',
    '/influencer-stats/',
    '/platform-stats/',
    '/fetcherdata-stats/',
    '/shelf-stats/',
    '/pmsm-images-stats/',
    '/execute-sql/?sql=SQL_LATEST_POST/',
    '/execute-sql/?sql=SQL_POSTS_COUNTS/',
]

def call(args):
    print 'Calling:', args
    return subprocess.call(args)

def main():
    for u in URLS:
        full_url = BASE_URL + u
        call(['wget', '--save-cookies', 'cookies.txt',
              '--post-data', 'username=ubuntu&password=superfastubuntu',
              'http://107.170.29.25:9000/accounts/login/'])
        call(['wget', '--load-cookies', 'cookies.txt',
              '-k', full_url,
              '-O', os.path.join(OUT_DIR, u.strip('/')+'-'+datetime.datetime.now().strftime('%y%m%d-%H%M%S')+\
                                 '.html')])

if __name__ == '__main__':
    main()
