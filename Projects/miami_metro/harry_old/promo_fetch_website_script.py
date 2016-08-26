from celery.decorators import task
import commands
from django.utils.encoding import smart_str, smart_unicode
from debra.models import Brands

@task(name = "harry.promo_fetch_website_script.go_start_scrapy")
def go_start_scrapy():
	print "FETCHING PROMO FROM WEBSITE"
	cmd = "pwd; cd miami_metro/harry; scrapy crawl promofetchwebsite"

	output = commands.getoutput(cmd)
	#print smart_unicode(output)

	print "Done"



