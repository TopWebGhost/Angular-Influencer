select distinct u.date_joined, inf.id, inf.name, inf.blog_url, (pdo.data_json::json->'hits')::text as hits
from debra_platformdataop pdo
join debra_influencer inf on pdo.influencer_id=inf.id
join auth_user u on inf.shelf_user_id=u.id
where operation='visit_influencer'
order by u.date_joined desc
;
