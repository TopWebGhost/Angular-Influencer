select b.domain_name, sr.id as sr_id, sr.tag, sr.flag, xpe.list_index, xpe.expr
from xps_scrapingresultset srs,
xps_scrapingresultsetentry srse,
xps_scrapingresult sr,
xps_xpathexpr xpe,
debra_brands b
where srs.description = '__included__'
and srs.id=srse.scraping_result_set_id
and sr.id=srse.scraping_result_id
and xpe.scraping_result_id=sr.id
and srs.brand_id = b.id
order by b.id, sr.product_model_id, sr.id, sr.tag, xpe.list_index
;
