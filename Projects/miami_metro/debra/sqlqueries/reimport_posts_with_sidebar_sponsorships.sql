update debra_posts set products_import_completed=false where id in (select post_id from debra_sponsorshipinfo where sidebar=true);

delete from debra_brandinpost where post_id in (select post_id from debra_sponsorshipinfo where sidebar=true);


