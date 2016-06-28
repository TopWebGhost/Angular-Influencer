DROP INDEX debra_pdolatest_platform_id;
CREATE INDEX debra_pdolatest_operation_id_platform_id ON debra_pdolatest (operation_id, platform_id);
DROP INDEX debra_pdolatest_influencer_id;
CREATE INDEX debra_pdolatest_operation_id_influencer_id ON debra_pdolatest (operation_id, influencer_id);
DROP INDEX debra_pdolatest_brand_id;
CREATE INDEX debra_pdolatest_operation_id_brand_id ON debra_pdolatest (operation_id, brand_id);
DROP INDEX debra_pdolatest_follower_id;
CREATE INDEX debra_pdolatest_operation_id_follower_id ON debra_pdolatest (operation_id, follower_id);
DROP INDEX debra_pdolatest_post_id;
CREATE INDEX debra_pdolatest_operation_id_post_id ON debra_pdolatest (operation_id, post_id);
DROP INDEX debra_pdolatest_post_interaction_id;
CREATE INDEX debra_pdolatest_operation_id_post_interaction_id ON debra_pdolatest (operation_id, post_interaction_id);
DROP INDEX debra_pdolatest_product_model_id;
CREATE INDEX debra_pdolatest_operation_id_product_model_id ON debra_pdolatest (operation_id, product_model_id);

