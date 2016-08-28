< Work in progress document by Atul (others, please ignore)>

PlatformDataFetcher directory contains many core functionalities for our service.

a) Framework for crawling for new content from platforms
b) Extracting meta-data about an influencer from a blog
c) Comment fetchers (based on disqus, gplus, Facebook)
d) denormalization of data
e) categorization of influencers, posts
f) language detection
g) automatically discovering attributes of influencer



Crawling framework
=================

Daily fetched platform stats

Tasks issued for daily-fetch:

Blogspot 36538
Wordpress 10804
Custom 15736
Tumblr 4402
Facebook 42899
Pinterest 3954
Twitter 49341
Instagram 40011

Total = 207K to be fetched daily


Daily activity level:
<name       #plats     #active-yest-or-last-week   +active-last-month>
Blogspot    52220      21920                        30K
Wordpress   15166      6215                         9K
Custom      19538      10221                        12K
Tumblr      6170       2682                         3.3K
Facebook    53436      24996                        31K
Pinterest   36502      8                            14
Twitter     57423      30578                        35K
Instagram   45984      29091                        33K


Overall, we have 366K platforms for the influencers.show_on_search = True.


observation #1: Pinterest is very low (need to check on that)
observation #2: Not a lot of platforms are active within last 6 months.


Posts created today: 117K so far
Blogspot 26008 (out of 36K platforms)  <= probably good also (not everyone blogs everyday)
Wordpress 9385 (out of 10K platforms)  <= probably good
Custom 25422   (out of 15K platforms)  <= probably good
Tumblr 2079    (out of 4.K platforms)  <= is fine?
Facebook 13097 (out of 42K platforms)  <= not enough resources?
Pinterest 0                            <= something is fishy but we don't get the dates right away for posts for pin
Twitter 20917  (out of 49K platforms)  <= not everyone tweets, but sometimes they do it multiple times a day
Instagram 15014(out of 40K platforms)  <= this is ridiculously low


*** Never fetched
Platform.objects.all().never_fetched().manual_or_from_social_contains().count()
Out[75]: 58981



Observed throughput of each fetcher:
a) Only daily_fetched tasks for blogs (Blogspot, Wordpress, Custom) => 28K platforms on a single machine (20/minute)
   => this can be increased by increasing number of workers to 1.5 times (potentially)
b) Only daily_fetched tasks for social (FB, Pinterest, Twitter, Instagram) =>
   => Instagram with a single worker (uses API): 15/minute => at most 21K platforms
   => Twitter (same, uses API) => at most 21K platforms
   => Facebook (uses API) => slower, 2-3/min => 2.8K - 3.6K/day
   => Pinterest (uses Selenium) => slower, 1/min => 1.2K/day
c) do we need infrequent fetching workers?
   => these workers run platforms who have not been fetched yet (59K) + who are less active (4-5K)
   => this is where new influencers are fetched for the first stage





New Influencer Processing
========================
a) Fetch Posts
     => to detect their activity levels
b) Categorization on posts
c) Categorization for the influencer
d) Issue extraction of information
e) Give it to QA