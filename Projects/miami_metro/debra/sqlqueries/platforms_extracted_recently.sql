select inf.id, inf.blog_url,
inf.fb_url, inf.pin_url, inf.tw_url, inf.insta_url, inf.bloglovin_url, inf.youtube_url, inf.pose_url, inf.lb_url,
pdo.error_msg, pl2.platform_name as pl2_name, pl2.url as pl2_url
from debra_influencer inf
join debra_platform pl on pl.influencer_id=inf.id
join debra_platformdataop pdo on pdo.platform_id=pl.id
join debra_platform pl2 on pl2.influencer_id=inf.id
where pdo.operation='extract_platforms_from_platform'
and started >= current_timestamp - '8 hours'::interval
limit 10000;
