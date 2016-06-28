insert into debra_pdolatest (operation_id, latest_started, platform_id, influencer_id, product_model_id, post_id, follower_id, post_interaction_id, brand_id)
select od.id, max(pdo.started), pdo.platform_id, pdo.influencer_id, pdo.product_model_id, pdo.post_id, pdo.follower_id, pdo.post_interaction_id, pdo.brand_id
from debra_platformdataop pdo
join debra_opdict od on pdo.operation=od.operation
left join debra_platform pl on pdo.platform_id=pl.id
left join debra_influencer inf on pdo.influencer_id=inf.id
where pdo.operation not like 'fieldchange%'
and (pl.id is null or (pl.url_not_found is null or pl.url_not_found=false))
and (inf.id is null or inf.blacklisted=False)
group by pdo.operation, pdo.platform_id, pdo.influencer_id, pdo.spec_custom, pdo.product_model_id, pdo.post_id, pdo.follower_id, pdo.post_interaction_id, pdo.brand_id, od.id
