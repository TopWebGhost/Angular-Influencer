select distinct name, prod_url, cnt
from (select name, designer_name, img_url, prod_url,
           count(*) over (partition by name, designer_name, img_url) as cnt
      from debra_productmodel
      where name is not null and name <> 'Nil') as inner_select
where cnt > 1
order by cnt desc
;
