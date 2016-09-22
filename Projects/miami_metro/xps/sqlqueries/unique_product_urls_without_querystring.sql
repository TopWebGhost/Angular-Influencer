select substring(prod_url from 1 for
        (case when position('?' in prod_url) = 0 then
            999
        else
            position('?' in prod_url) - 1
        end)) as base_url,
    count(*) 
from debra_productmodel
group by base_url
having count(*) > 1
order by count(*) desc
;
