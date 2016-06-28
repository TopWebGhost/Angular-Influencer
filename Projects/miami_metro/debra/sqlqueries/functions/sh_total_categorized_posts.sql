-- Install with ./theshelf psql -f <PATH>/sh_total_categorized_posts.sql

-- Index influencers with:
-- CREATE INDEX CONCURRENTLY debra_influencer_category_totals ON debra_influencer ((sh_total_categorized_posts(categories)))

-- Query with:
-- SELECT sh_total_categorized_posts(categories) FROM debra_influencer WHERE sh_total_categorized_posts(categories) > 2

CREATE OR REPLACE FUNCTION sh_total_categorized_posts(categories JSON) RETURNS INTEGER AS
$FUNCTION$

BEGIN
    RETURN (
        SELECT COALESCE(SUM(values.post_count), 0)
        FROM (
            -- A hack to turn a JSON value into a regular INTEGER:
            -- convert it to a single-item array, then get it via the ->> operator
            SELECT (array_to_json(array[value])->>0)::INTEGER as post_count
            -- get all post counts for category
            FROM json_each((categories#>>'{count}')::json)
            -- and ignore the 'total' value, if present.
            WHERE key <> 'total'
        ) AS values
    );
END

$FUNCTION$

LANGUAGE plpgsql IMMUTABLE;
