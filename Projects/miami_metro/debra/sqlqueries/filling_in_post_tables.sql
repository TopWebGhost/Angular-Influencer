-- hashtags
with hashtags as (
    select po.id as po_id, regexp_split_to_table(po.hashtags, ', ') as h
    from debra_posts po
)
insert into debra_hashtaginpost (hashtag, post_id)
select lower(h), po_id
from hashtags
where h <> '';

-- mentions
with mentions as (
    select po.id as po_id, regexp_split_to_table(po.mentions, ', ') as h
    from debra_posts po
)
insert into debra_mentioninpost (mention, post_id)
select lower(h), po_id
from mentions
where h <> '';

-- brands
with
brand_names as (
    select po.id as po_id, regexp_split_to_table(po.brand_tags, ', ') as h
    from debra_posts po
),
brand_data as (
    select po_id, h, (select br.id from debra_brands br where br.blacklisted=false and br.name=h order by br.id limit 1) as br_id
    from brand_names
)
insert into debra_brandinpost (brand_id, post_id)
select br_id, po_id
from brand_data
where h <> ''
and br_id is not null
;
