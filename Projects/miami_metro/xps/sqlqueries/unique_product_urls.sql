select prod_url, count(*) 
from debra_productmodel
group by prod_url
having count(*) > 1
order by count(*) desc
;
