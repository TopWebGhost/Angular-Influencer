Lookbook scraper
------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

1 - Requirements

sudo apt-get install python-dev libxml2-dev libxslt-dev libcurl4-openssl-dev
pip install lxml
pip install pycurl
pip install Grab
pip install peewee

------------------------------------------------------------------------------------------------------------------------------------------------------------------------------

2 - Files

[lookbook.py] - the scraper itself (you can stop it anytime by pressing CTRL+C)
[db_conn.py] -  structure of sqlite db (ORM)
[2csv.py] - create csv file from sqlite db (also this script converts number of followers to integer,
and don't run it while the scraper is working to prevent blocking of the db)
[check_db.py] - count a total number of users in sqlite db

------------------------------------------------------------------------------------------------------------------------------------------------------------------------------