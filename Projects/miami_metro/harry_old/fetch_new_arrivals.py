from celery.decorators import task
import commands
from django.utils.encoding import smart_str, smart_unicode
from debra.models import Brands

@task(name = "harry.fetch_new_arrivals.per_store_task")
def fetch_new_items_store(store_obj):

	

	cmd = "cd miami_metro/harry; nohup scrapy crawl " + store_obj.crawler_name + " -a new_arrivals=1 " + \
			" -a store_name=\"" + store_obj.name + "\" -a start_url=\"" + store_obj.start_url + "\" > /home/ubuntu/" + store_obj.name.replace(' ', '').replace('&', '').replace("'", '') + ".txt "
	print cmd
	res = commands.getoutput(cmd)


@task(name = "harry.fetch_new_arrivals.manager_task")
def fetch_new_items_task():
	supported_brands = Brands.objects.filter(supported=True)

	for s in supported_brands:
		fetch_new_items_store.delay(s)

if __name__ == "__main__":
    br = Brands.objects.get(name="Express")
    fetch_new_items_store(br)