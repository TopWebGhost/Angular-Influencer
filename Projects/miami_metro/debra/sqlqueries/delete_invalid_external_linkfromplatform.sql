with link_data as
(
    select lfp.id,
           split_part(normalized_dest_url, '/', 1) as domain_name,
           split_part(regexp_replace(regexp_replace(pl.url, 'http://', ''), 'https://', ''), '/', 1) as source_domain_name,
           kind
    from debra_linkfromplatform lfp
    join debra_platform pl on (lfp.source_platform_id=pl.id and (pl.url_not_found is null or pl.url_not_found=false))
    join debra_influencer inf on (inf.id=pl.influencer_id and inf.show_on_search=true and inf.blacklisted=false)
)
delete from debra_linkfromplatform lfp
where lfp.id in
    (select id from link_data
    where kind='common_external'
    and domain_name = source_domain_name)
