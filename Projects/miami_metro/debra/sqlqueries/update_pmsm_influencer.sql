update debra_productmodelshelfmap pmsm
set influencer_id = po.influencer_id
from debra_posts po
where pmsm.post_id = po.id
and pmsm.influencer_id is null
and po.influencer_id is not null
