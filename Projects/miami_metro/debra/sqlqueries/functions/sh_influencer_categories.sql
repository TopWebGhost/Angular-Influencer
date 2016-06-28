-- Install with ./theshelf psql -f <PATH>/sh_influencer_categories.sql

-- Index influencers with:
-- CREATE INDEX CONCURRENTLY debra_influencer_category_names ON debra_influencer USING GIN ((sh_influencer_categories(categories)))

-- Query with:
-- SELECT sh_influencer_categories(categories) AS cats FROM debra_influencer WHERE sh_influencer_categories(categories) @> array['fashion', 'kids']

CREATE OR REPLACE FUNCTION sh_influencer_categories(categories JSON) RETURNS TEXT[] AS
$FUNCTION$

BEGIN
    RETURN (
        SELECT
            CASE categories::TEXT
                WHEN 'null' THEN ARRAY[]::TEXT[]
                ELSE array(
                    -- A hack to turn a JSON string into a regular TEXT value:
                    -- convert it to a single-item array, then get it via the ->> operator
                    SELECT array_to_json(array[found.item])->>0
                    FROM (SELECT json_array_elements(categories->'found') AS item) AS found
                )
            END
    );
END

$FUNCTION$

LANGUAGE plpgsql IMMUTABLE;
