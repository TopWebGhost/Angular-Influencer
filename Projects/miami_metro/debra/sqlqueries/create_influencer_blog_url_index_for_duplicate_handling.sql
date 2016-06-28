CREATE INDEX debra_influencer_blog_url_trgm ON debra_influencer USING gist (UPPER(blog_url) gist_trgm_ops);
ANALYZE VERBOSE debra_influencer;
