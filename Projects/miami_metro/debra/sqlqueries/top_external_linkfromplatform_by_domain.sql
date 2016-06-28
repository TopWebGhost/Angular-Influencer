with link_data as
(
    select split_part(normalized_dest_url, '/', 1) as domain_name, pl.id as source_pl_id
    from debra_linkfromplatform lfp
    join debra_platform pl on (lfp.source_platform_id=pl.id and (pl.url_not_found is null or pl.url_not_found=false))
    join debra_influencer inf on (inf.id=pl.influencer_id and inf.show_on_search=true and inf.blacklisted=false)
    where kind='common_external'
),
link_distinct_data as
(
    select distinct domain_name, source_pl_id
    from link_data
),
domain_counts as (
    select domain_name, count(*) as cnt
    from link_data
    where domain_name <> ''
    group by domain_name
    having count(*) >= 5
    order by count(*) desc
),
domain_distinct_counts as (
    select domain_name, count(*) as cnt_distinct
    from link_distinct_data
    where domain_name <> ''
    group by domain_name
    having count(*) >= 5
    order by count(*) desc
)
select dc.domain_name, dc.cnt, ddc.cnt_distinct
from domain_counts dc
join domain_distinct_counts ddc on dc.domain_name = ddc.domain_name
order by ddc.cnt_distinct desc

