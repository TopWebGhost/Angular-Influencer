source /home/ubuntu/.profile
source venv/bin/activate
pip install python django-mailchimp-v1.3
pip install boto
pip install -I selenium==2.25.0
#wget http://releases.mozilla.org/pub/mozilla.org/firefox/releases/17.0.1/linux-x86_64/en-US/firefox-17.0.1.tar.bz2
#bunzip2 firefox-17.0.1.tar.bz2
#tar -xvf firefox-17.0.1.tar
#export PATH=/home/ubuntu/Projects/firefox:$PATH
pip install mailsnake
pip install django-heroku-memcacheify
# pip install django_endless_pagination
sudo service postgresql stop
python miami_metro/manage.py celeryd -E -Q price_avail_worker -l info -c 3 >& ../celery-output.txt &
sudo service mysql stop
