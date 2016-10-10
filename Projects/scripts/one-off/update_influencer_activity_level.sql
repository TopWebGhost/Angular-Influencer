CREATE OR REPLACE FUNCTION public.update_influencer_activity_level(influencer integer)
 RETURNS text
 LANGUAGE plpgsql
AS $function$
BEGIN
    RETURN (
        WITH platforms AS (SELECT p.activity_level FROM debra_platform p WHERE p.influencer_id = influencer AND (p.url_not_found IS NULL OR p.url_not_found = False)),
        levels AS (
            SELECT 'ACTIVE_NEW' AS ACTIVITY_LEVEL FROM PLATFORMS WHERE ACTIVITY_LEVEL = 'ACTIVE_NEW'
            UNION ALL
            SELECT 'ACTIVE_LAST_DAY' AS activity_level FROM platforms WHERE activity_level = 'ACTIVE_LAST_DAY'
            UNION ALL
            SELECT 'ACTIVE_LAST_WEEK' AS activity_level FROM platforms WHERE activity_level = 'ACTIVE_LAST_WEEK'
            UNION ALL
            SELECT 'ACTIVE_LAST_MONTH' AS activity_level FROM platforms WHERE activity_level = 'ACTIVE_LAST_MONTH'
            UNION ALL
            SELECT 'ACTIVE_LAST_3_MONTHS' AS activity_level FROM platforms WHERE activity_level = 'ACTIVE_LAST_3_MONTHS'
            UNION ALL
            SELECT 'ACTIVE_LAST_6_MONTHS' AS activity_level FROM platforms WHERE activity_level = 'ACTIVE_LAST_6_MONTHS'
            UNION ALL
            SELECT 'ACTIVE_LAST_12_MONTHS' AS activity_level FROM platforms WHERE activity_level = 'ACTIVE_LAST_12_MONTHS'
            UNION ALL
            SELECT 'ACTIVE_LONG_TIME_AGO' AS activity_level FROM platforms WHERE activity_level = 'ACTIVE_LONG_TIME_AGO'
            UNION ALL
            SELECT NULL AS activity_level
        )
        SELECT activity_level FROM levels LIMIT 1
    );
END
$function$

