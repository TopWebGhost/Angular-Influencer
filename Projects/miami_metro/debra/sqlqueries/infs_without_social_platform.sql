select * from debra_influencer inf
where relevant_to_fashion=true
and is_active=true
and not (show_on_search=true)
and validated_on not like '%info%'
and average_num_comments_per_post >= 5
and not exists (select 1 from debra_platform pl where pl.influencer_id=inf.id and platform_name not in ('Wordpress', 'Blogspot', 'Custom', 'Tumblr'));

