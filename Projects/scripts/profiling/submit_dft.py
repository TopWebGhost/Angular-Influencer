from platformdatafetcher import pbfetcher
from xpathscraper import utils

utils.log_to_stderr()

pbfetcher.submit_daily_fetch_tasks()
