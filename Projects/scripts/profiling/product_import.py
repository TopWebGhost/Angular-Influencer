from hanna import import_from_blog_post
from debra import models
from xpathscraper import utils

utils.log_to_stderr()

pl = models.Platform.objects.get(id=125095)
post = models.Posts.objects.get(id=16933247)
import_from_blog_post.fetch_products_from_post(post.id, None)
