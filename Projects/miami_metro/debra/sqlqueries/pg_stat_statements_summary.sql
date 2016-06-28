select rolname,
    calls,
    round(total_time::numeric, 3) AS total,
    round((total_time / calls)::numeric, 3) AS per_call,
    rows,
    regexp_replace(query, '[ \t\n]+', ' ', 'g') AS query_text
from pg_stat_statements
join pg_roles r ON r.oid = userid
where calls > 1
and rolname not like '%backup'
order by total_time desc;
