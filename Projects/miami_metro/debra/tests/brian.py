'''
price tracker tests
'''

from django.test import TestCase
from assertion_extras import equal_with_threshold as almost_equal
from brian.generic_tracker import ProductPage

class FindProductContainerTests(TestCase):
    '''
    Tests for finding the product containers for various stores
    '''
    def base_test(self, product_page, expected, in_test=False):
        '''
        the base test for this class compares the result of calling containing_product_div on this product page
        to the expected result
        @param product_page - the ProductPage instance to be tested
        @param expected - the expected result
        @param in_test (optional) - should an assertIn be performed?
        '''
        if in_test:
            self.assertIn(product_page.containing_product_div(), expected)
        else:
            self.assertEqual(product_page.containing_product_div(), expected)

    def test_abercrombie(self):
        product_page = ProductPage('http://www.abercrombie.com/shop/us/mens-skinny-jeans/a-and-f-skinny-jeans-981564_01')
        self.base_test(product_page, "product-5563")

    def test_amazon(self):
        product_page = ProductPage("http://www.amazon.com/gp/product/B00930H9P2/ref=s9_al_bw_g241_ir01?pf_rd_m=ATVPDKIKX0DER&pf_rd_s=merchandised-search-3&pf_rd_r=0AFVP2QVBEEA3CD1CEJJ&pf_rd_t=101&pf_rd_p=1634066002&pf_rd_i=7352921011")
        self.base_test(product_page, ['a-row', 'ppd', 'PrimeStripeContent', 'instantOrderUpdate_feature_div'], in_test=True)

    def test_american_eagle(self):
        product_page = ProductPage('http://www.ae.com/web/browse/product.jsp?productId=1144_9704_443&catId=cat6470451')
        self.base_test(product_page, 'pContent')

    def test_ann_taylor(self):
        product_page = ProductPage("http://www.anntaylor.com/one-button-tweed-jacket/321485?colorExplode=false&skuId=14764806&catid=cata000013&productPageType=fullPriceProducts&defaultColor=7030")
        self.base_test(product_page, ['grid g-2col', 'main-bd-inner', 'main-bd'], in_test=True)

    def test_anthropolaga(self):
        product_page = ProductPage('http://www.anthropologie.com/anthro/product/clothes-blouses/29167848.jsp?cm_sp=Fluid-_-29167848-_-Regular_1')
        self.base_test(product_page, ['productdetail', 'main-container'], in_test=True)

    def test_asos(self):
        product_page = ProductPage('http://us.asos.com/D-Struct-Flag-Sneakers/11n9pk/?iid=3312355&cid=1935&sh=0&pge=0&pgesize=36&sort=-1&clr=Blue&mporgp=L0QtU3RydWN0L0QtU3RydWN0LUZsYWctUGxpbXNvbGxzL1Byb2Qv')
        self.base_test(product_page, ['content-wrapper-left', 'content-wrapper', 'ctl00_ContentMainPage_pnlMainContent'], in_test=True)

    def test_athleta(self):
        product_page = ProductPage('http://athleta.gap.com/browse/product.do?cid=1000054&vid=1&pid=918993&mlink=46750,7184035,TSAlacrity9_24&clink=7184035')
        self.base_test(product_page, ['mainContentWrapper', 'mainContent'], in_test=True)

    def test_banana_republic(self):
        product_page = ProductPage('http://bananarepublic.gap.com/browse/product.do?cid=32643&vid=1&pid=554779002')
        self.base_test(product_page, ['mainContentWrapper', 'mainContent'], in_test=True)

    def test_bloomingdales(self):
        product_page = ProductPage('http://www1.bloomingdales.com/shop/product/modern-fiction-leather-cap-toe-oxfords?ID=831579&CategoryID=1001314#fn=spp%3D1%26ppp%3D96%26sp%3D1%26rid%3D82%26spc%3D139')
        self.base_test(product_page, 'pdp_container')

    def test_dsw(self):
        product_page = ProductPage('http://www.dsw.com/shoe/aston+grey+drake+oxford?prodId=250482&category=dsw12cat1970002&activeCats=cat20192,dsw12cat1970002')
        self.base_test(product_page, 'productContentZone')


class FindProductInfoTests(TestCase):
    '''
    Tests for finding the product info for various products
    '''
    def xpath_fetches_correct(self, xpath, text, product_page, is_price=False):
        '''
        a test to be performed for every test that verifies a given xpath points to a given element on a given page
        @param xpath - the xpath to verify
        @param text - the text that the xpath should point to
        @param product_page - the product page in question
        @param is_price - flag designating whether the value returned by this xpath should be a price
        for almost_equal comparison of strings. So only for unicode results should this be True
        '''
        xpath_element_value = product_page.get_value_at_xpath(xpath, is_price=is_price)
        self.assertTrue(almost_equal(xpath_element_value, text))

    def base_test(self, product_page, expected):
        '''
        the base test for this class compares the result of calling product_info on this product page
        to the expected result
        @param product_page - the ProductPage instance to be tested
        @param expected - a dictionary containing the expected result. The dictionary should contain:
               product_img, name, price
        '''
        result = product_page.product_info()

        self.assertTrue(almost_equal(result['product_img'], expected['product_img']))
        self.assertTrue(almost_equal(result['name'], expected['name']))
        self.assertEqual(result['price'], expected['price'])

        #verify that the xpaths points to the correct text
        self.xpath_fetches_correct(result['product_img_xpath'], result['product_img'], product_page)
        self.xpath_fetches_correct(result['name_xpath'], result['name'], product_page)
        self.xpath_fetches_correct(result['price_xpath'], result['price'], product_page, is_price=True)

        #cleanup
        product_page.close_driver()


    def test_abercrombie(self):
        product_page = ProductPage('http://www.abercrombie.com/shop/us/mens-skinny-jeans/a-and-f-skinny-jeans-981564_01')
        expected = {'product_img': 'http://anf.scene7.com/is/image/anf/anf_55563_01_prod1?$anfProductImage500$',
                    'name': 'A&F Skinny Jeans',
                    'price': 39}
        self.base_test(product_page, expected)

    def test_amazon(self):
        product_page = ProductPage("http://www.amazon.com/gp/product/B00930H9P2/ref=s9_al_bw_g241_ir01?pf_rd_m=ATVPDKIKX0DER&pf_rd_s=merchandised-search-3&pf_rd_r=0AFVP2QVBEEA3CD1CEJJ&pf_rd_t=101&pf_rd_p=1634066002&pf_rd_i=7352921011")
        expected = {'product_img': 'http://ecx.images-amazon.com/images/I/81balIlRdtL._SY679_.jpg',
                    'name': 'Stuhrling Original Men\'s 133.33151 Symphony Aristocrat Executive Automatic Skeleton Black Watch',
                    'price': 525}
        self.base_test(product_page, expected)

    def test_american_eagle(self):
        product_page = ProductPage('http://www.ae.com/web/browse/product.jsp?productId=1144_9704_443&catId=cat6470451')
        expected = {'product_img': 'http://www.ae.com//pics.ae.com/is/image/aeo/1144_9704_443_of?maskuse=off&wid=1119&size=1121,1254&fit=crop&qlt=70,0',
                    'name': 'AE Solid V-Neck Sweater',
                    'price': 24.99}
        self.base_test(product_page, expected)

    def test_ann_taylor(self):
        product_page = ProductPage("http://www.anntaylor.com/one-button-tweed-jacket/321485?colorExplode=false&skuId=14764806&catid=cata000013&productPageType=fullPriceProducts&defaultColor=7030")
        expected = {'product_img': 'http://richmedia.channeladvisor.com/ImageDelivery/imageService?profileId=52000652&itemID=321485&swatchID=7030&recipeName=pdlg488x600',
                    'name': 'One Button Tweed Jacket',
                    'price': 198}
        self.base_test(product_page, expected)

    def test_anthropolaga(self):
        product_page = ProductPage('http://www.anthropologie.com/anthro/product/clothes-blouses/29167848.jsp?cm_sp=Fluid-_-29167848-_-Regular_1')
        expected = {'product_img': 'http://images.anthropologie.com/is/image/Anthropologie/29167848_013_b?$product410x615$',
                    'name': 'Arrossire Sequined Top',
                    'price': 88.00}
        self.base_test(product_page, expected)

    def test_asos(self):
        product_page = ProductPage('http://us.asos.com/D-Struct-Flag-Sneakers/11n9pk/?iid=3312355&cid=1935&sh=0&pge=0&pgesize=36&sort=-1&clr=Blue&mporgp=L0QtU3RydWN0L0QtU3RydWN0LUZsYWctUGxpbXNvbGxzL1Byb2Qv')
        expected = {'product_img': 'http://images.asos-media.com/inv/media/5/5/3/2/3312355/blue/image1xl.jpg',
                    'name': 'D Struct Flag Sneakers',
                    'price': 62.29}
        self.base_test(product_page, expected)

    def test_athleta(self):
        product_page = ProductPage('http://athleta.gap.com/browse/product.do?cid=1000054&vid=1&pid=918993&mlink=46750,7184035,TSAlacrity9_24&clink=7184035')
        expected = {'product_img': 'http://athleta.gap.com/resources/productImage/v1/918993002/VLI',
                    'name': 'Alacrity Half Zip',
                    'price': 79.00}
        self.base_test(product_page, expected)

    def test_banana_republic(self):
        product_page = ProductPage('http://bananarepublic.gap.com/browse/product.do?cid=32643&vid=1&pid=554779002')
        expected = {'product_img': 'http://bananarepublic.gap.com/resources/productImage/v1/554779002/VLI',
                    'name': 'Tailored-Fit Grey Cotton Two-Button Blazer',
                    'price': 225.00}
        self.base_test(product_page, expected)

    def test_bloomingdales(self):
        product_page = ProductPage('http://www1.bloomingdales.com/shop/product/modern-fiction-leather-cap-toe-oxfords?ID=831579&CategoryID=1001314#fn=spp%3D1%26ppp%3D96%26sp%3D1%26rid%3D82%26spc%3D139')
        expected = {'product_img': 'http://images.bloomingdales.com/is/image/BLM/products/5/optimized/8395995_fpx.tif?wid=356&qlt=90,0&layer=comp&op_sharpen=0&resMode=sharp2&op_usm=0.7,1.0,0.5,0&fmt=jpeg',
                    'name': 'Modern Fiction Leather Cap Toe Oxfords',
                    'price': 285.00}
        self.base_test(product_page, expected)

    def test_dsw(self):
        product_page = ProductPage('http://www.dsw.com/shoe/aston+grey+drake+oxford?prodId=250482&category=dsw12cat1970002&activeCats=cat20192,dsw12cat1970002')
        expected = {'product_img': 'http://s7d2.scene7.com/is/image/DSWShoes/250482_230_ss_01?scl=3.125&qlt=70&fmt=jpeg&wid=480&hei=359&op_sharpen=1',
                    'name': 'Aston Grey Drake Oxford',
                    'price': 79.95}
        self.base_test(product_page, expected)

    def test_express(self):
        product_page = ProductPage("http://www.express.com/clothing/knit+blazer/pro/9393143/cat560005")
        expected = {'product_img': 'http://images.express.com/is/image/expressfashion/27_939_3143_432_17?iv=NJETZ2&wid=351&hei=410',
                    'name': 'KNIT BLAZER',
                    'price': 198.00}
        self.base_test(product_page, expected)

    def test_forever_21(self):
        product_page = ProductPage("http://www.forever21.com/Product/Product.aspx?BR=f21&Category=bottom_pants&ProductID=2000065458&VariantID=")
        expected = {'product_img': 'http://www.forever21.com/images/default_330/00065458-03.jpg',
                    'name': 'Bold Geo Harem Pants',
                    'price': 22.80}
        self.base_test(product_page, expected)

    def test_gap(self):
        product_page = ProductPage("http://www.gap.com/browse/product.do?cid=91741&vid=1&pid=768237002")
        expected = {'product_img': 'http://www.gap.com/resources/productImage/v1/768237002/VLI',
                    'name': 'Slub arch logo pullover hoodie',
                    'price': 54.95}
        self.base_test(product_page, expected)

    def test_gilly_hicks(self):
        product_page = ProductPage("http://www.gillyhicks.com/shop/us/clothing-long-sleeve-graphic-tees/cheeky-definition-graphic-hoodie-1315172_01")
        expected = {'product_img': 'http://anf.scene7.com/is/image/anf/gh_39111_01_prod1?$ghProductImage500$',
                    'name': 'Cheeky Definition Graphic Hoodie Tee',
                    'price': 34.50}
        self.base_test(product_page, expected)

    def test_hollister(self):
        product_page = ProductPage("http://www.hollisterco.com/shop/us/dudes-skinny-jeans/hollister-skinny-jeans-1150452_01")
        expected = {'product_img': 'http://anf.scene7.com/is/image/anf/hol_65128_01_prod1?$holProductImage500$',
                    'name': 'Hollister Skinny Jeans',
                    'price': 59.50}
        self.base_test(product_page, expected)

    def test_jcrew(self):
        product_page = ProductPage("http://www.jcrew.com/mens_feature/NewArrivals/accessories/PRDOVR~54175/54175.jsp?color_name=blue-grey-plaid")
        expected = {'product_img': 'http://s7.jcrew.com/is/image/jcrew/54175_SP8629?$pdp_fs418$',
                    'name': 'Cashmere plaid scarf',
                    'price': 110.00}
        self.base_test(product_page, expected)

    def test_jcrew_factory(self):
        product_page = ProductPage("http://factory.jcrew.com/mens-clothing/bags_accessories/belts/PRDOVR~09213/09213.jsp")
        expected = {'product_img': 'http://s7.jcrew.com/is/image/jcrew/09213_SP9145?$pdp_fs418$',
                    'name': 'Factory reversible leather belt',
                    'price': 39.50}
        self.base_test(product_page, expected)

     #lane bryant is wack. Come back to this one later
#    def lane_bryant(self):
#        product_page = ProductPage("http://www.lanebryant.com/active/active-view-all/20230c20233/index.cat")
#        expected = {'product_img': 'http://assets.charmingshoppes.com/is/image/LaneBryant/2013-octobr-terry-hoodie?$thumbnail$&wid=229&hei=298',
#                    'name': 'Factory reversible leather belt',
#                    'price': '39.50'}
#        self.base_test(product_page, expected)

    def test_loft(self):
        product_page = ProductPage("http://www.loft.com/julie-skinny-corduroy-pants/314298?colorExplode=false&skuId=14505287&catid=catl000015&productPageType=fullPriceProducts&defaultColor=7512")
        expected = {'product_img': 'http://richmedia.channeladvisor.com/ImageDelivery/imageService?profileId=52000653&itemID=314298&swatchID=7512&recipeName=pdlg485x503',
                    'name': 'Julie Skinny Corduroy Pants',
                    'price': 59.50}

    def test_macys(self):
        product_page = ProductPage("http://www1.macys.com/shop/product/ralph-lauren-polo-red-gift-set?ID=1050356&CategoryID=30088#fn=sp%3D1%26spc%3D1472%26ruleId%3D57%26slotId%3Drec(2)")
        expected = {'product_img': 'http://slimages.macys.com/is/image/MCY/products/4/optimized/1749494_fpx.tif?$filterlrg$&wid=370',
                    'name': 'Ralph Lauren Polo Red Gift Set',
                    'price': 144.00}
        self.base_test(product_page, expected)
