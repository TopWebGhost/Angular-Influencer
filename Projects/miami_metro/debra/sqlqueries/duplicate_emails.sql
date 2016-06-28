with email_data as (
select email,
string_to_array(email, ' ') as email_array,
array_length(string_to_array(lower(email), ' '), 1) as email_array_length,
(select count(*) from (select distinct unnest(string_to_array(lower(email), ' '))) _a) as unique_emails,
*
from debra_influencer
where email is not null)
select * from email_data
where email_array_length <> unique_emails
and (show_on_search is null or show_on_search=False)
and validated_on is null

