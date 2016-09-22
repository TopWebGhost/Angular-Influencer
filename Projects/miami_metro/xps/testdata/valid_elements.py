# -*- coding: utf-8 -*-

from xpathscraper.resultsenrichment import PriceValue, PriceSingle, PricePair, PriceRange
from decimal import Decimal


# Definition of possible valid elements for various tags (name, image, price)
# for earch Product defined in a fixture file.

VALID_BY_PRODUCT_ID = {

    2: {
            'name': [
                'SEA LIFE CHARM NECKLACE',
            ],
            'img': [
                '//shop.stelladot.com/style/media/catalog/product/cache/0/pdp_image/320x485/9df78eab33525d08d6e5fb8d27136e95/n/3/n397_sealife_2_1.jpg',
                'http://shop.stelladot.com/style/media/catalog/product/n/3/n397_sealife_2_1.jpg', #zoom
            ],
            'price': [
                '$59',
            ],
    },

    4: {
            'name': [
                'Petite Curvy Cropped Jeans in White',
            ],
            'img': [
                'http://richmedia.channeladvisor.com/ImageDelivery/imageService?profileId=52000653&itemID=301197&swatchID=9000&recipeName=pdlg485x503',
                'http://richmedia.channeladvisor.com/ImageDelivery/imageService?profileId=52000653&id=215388&recipeId=230',
            ],
            'price': [
                '$34.88',
            ],
            'size': [],
            'color': [],
    },

    5: {
            'name': [
                'Rebecca Taylor Peplum Pullover',
            ],
            'img': [
                'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/rebec/rebec4053112894/rebec4053112894_q1_1-0_336x596.jpg',
            ],
            'price': [
                '$325',
            ],
    },

    6: {
            'name': [
                'ASOS Midi Skirt in Ponte Stripe',
            ],
            'img': [
                'http://images.asos-media.com/inv/media/3/5/4/7/2807453/blackwhite/image1xl.jpg',
                'http://images.asos-media.com/inv/media/3/5/4/7/2807453/image4xl.jpg',
            ],
            'price': [
                '35.00', '24.50',
            ],
            'size': [u'1', '2', '4', '6', '8', '10', '12'],
            'color': [u'black'],

    },

    7: {
            'name': [
                'Women\'s The Rockstar Demi-Boot Jeans',
            ],
            'img': [
                'http://oldnavy.gap.com/browse/product.do?cid=79765&vid=1&pid=329526042',
                'http://www3.assets-gap.com/webcontent/0005/563/864/cn5563864.jpg',
            ],
            'price': [
                '$34.94', '$34.50',
            ],
            'size': [u'0', u'2', u'8', u'4', u'10', u'6', u'12', u'14', u'16', u'18', u'20'],
            'color': ['rinse'],

    },

    11: {
            'name': [
                'White Scalloped Taryn Boxes',
            ],
            'img': [
                'http://ii.worldmarket.com/fcgi-bin/iipsrv.fcgi?FIF=/images/worldmarket/source/29885_XXX_v1.tif&wid=2000&cvt=jpeg',
            ],
            'price': [
                '$9.99', '$14.99',
            ],
    },

    16: {
            'name': [
                'Factory printed pencil skirt in stretch cotton',
            ],
            'img': [
                'http://s7.jcrew.com/is/image/jcrew/37532_WD6562?$pdp_fs418$',
                'http://s7.jcrew.com/is/image/jcrew/37532_WE8700?$pdp_fs418$',
            ],
            'price': [
                '85.00', '69.50',
            ],
    },

    18: {
            'name': [
                'Any Color Will Do Dress',
            ],
            'img': [
                'http://productshots2.modcloth.net/productshots/0115/7199/1cc25144ddac565e7903c43e715d79d9.jpg?1340229939',
                'http://productshots0.modcloth.net/productshots/0115/7199/64253ade7a954ee05e4a2ce55b7851d4.jpg?1340229939',
            ],
            #'price': [
            #    '47.99',
            #    '$33.99',
            #],
            #'size': [u'S', u'M', u'L'],
    },

    19: {
            'name': [
                'Perfect Leather Flats',
            ],
            'img': [
                'http://richmedia.channeladvisor.com/ImageDelivery/imageService?profileId=52000652&itemID=303935&swatchID=6600&recipeName=pdlg488x600',
                'http://richmedia.channeladvisor.com/ImageDelivery/imageService?profileId=52000652&id=226253&recipeId=115',
            ],
            'price': [
                '69.88',
            ],
    },

    22: {
            'name': [
                'Southwest Medallion Tapestry',
            ],
            'img': [
                'http://images.urbanoutfitters.com/is/image/UrbanOutfitters/23550783_095_b?$zoom$',
            ],
            'price': [
                '39', '29',
            ],
    },

    23: {
            'name': [
                '[BlankNYC] Skinny Color Jeans',
            ],
            'img': [
                'https://s7d9.scene7.com/is/image/madewell/01717_WN9137_m?$pdp_fs418$',
                'https://s7d9.scene7.com/is/image/madewell/01717_WN9138?$pdp_fs418$',
            ],
            'price': [
                '88.00', '64.99',
            ],
            'size': [u'24', u'25', u'28', u'26', u'29', u'27', u'30', u'31'],
            'color': [u'neon peach'],
    },

    26: {
            'name': [
                'Check Messenger Bag, Small Burberry',
                'Burberry Check Messenger Bag, Small',
                'Check Messenger Bag, Small',
            ],
            'img': [
                'http://images.neimanmarcus.com/ca/1/products/mx/NMN1LG4_mx.jpg',
            ],
            'price': [
                '$1,095.00', '$492.00',
            ],
            'size': [],
            'color': [],
    },

    27: {
            'name': [
                'Mossimo Supply Co. Thread Braid Tri Color - Tan',
            ],
            'img': [
                'http://Img3.targetimg3.com/wcsstore/TargetSAS//img/p/14/36/14364682_130222103000.jpg',
                'http://img3.targetimg3.com/wcsstore/TargetSAS//img/p/14/36/14364682_130222103000.jpg',
                'http://img3.targetimg3.com/wcsstore/TargetSAS//img/p/14/36/14361473_130222103000.jpg',
            ],
            'price': [
                '$5.94',
                '$16.99',
            ],
            'size': [u'XS'],
            'color': [],
    },

    34: {
            'name': [
                'Candela Cutout Platform',
            ],
            'img': [
                'http://images01.nastygal.com/resources/nastygal/images/products/processed/20719.2.detail.jpg',
                'http://richmedia.channeladvisor.com/ImageDelivery/imageService?profileId=52000653&id=215388&recipeId=230',
                'http://images01.nastygal.com/resources/nastygal/images/products/processed/20719.1.detail.jpg',
                'http://images05.nastygal.com/resources/nastygal/images/products/processed/20719.3.detail.jpg',
                'http://images01.nastygal.com/resources/nastygal/images/products/processed/20719.2.detail.jpg',
                'http://images03.nastygal.com/resources/nastygal/images/products/processed/20719.0.detail.jpg',
            ],
            'price': [
                '$78.00', '$195.00',
            ],
            'size': [u'5', u'5.5', u'6', u'6.5', u'7', u'7.5', u'8', u'8.5', u'9', u'9.5', u'10'],
            'color': [u'red'],
    },

    35: {
            'name': [
                'Chinese Laundry Women\'s Danger Zone Pump',
            ],
            'img': [
                'http://ecx.images-amazon.com/images/I/41fdUxO10WL._SX395_.jpg',
                'http://ecx.images-amazon.com/images/I/71snFWjf5bL._SX500_.jpg',
                'http://ecx.images-amazon.com/images/I/71snFWjf5bL._SX575_.jpg',
            ],
            'price': [
                u'$24.99 - $99.95'
            ],
            'size': [u'5', u'5.5', u'6', u'6.5', u'7', u'7.5', u'8', u'8.5', u'9', u'9.5', u'10', u'11'],
            'color': ['nude', 'black', 'white', 'bright fuchsia'],

    },

    38: dict(
            name=['Amanda Uprichard Crystal Dress in Grape'],
            img=['http://is4.revolveclothing.com/images/p/n/z/AMAN-WD162_V1.jpg'],
            price=['$206', '$81'],
            color=['grape'],
    ),

    42: dict(
            name=['Light Denim Acid Runner Shorts'],
            img=['http://mediaus.topshop.com/wcsstore/TopShopUS/images/catalog/14J55BBLC_normal.jpg'],
            price=['$20'],
    ),

    43: dict(
            name=['Mona Mia Trinidad Tan Woven Platform Heels',
                  'Mona Mia Trinidad Tan Woven Platform Heels $46',
                  '$46 Mona Mia Trinidad Tan Woven Platform Heels'],
            img=['http://www.lulus.com/images/product/xlarge/shMONAtrinidadtanblacktan.JPG',
                 'http://www.lulus.com/images/product/large/shMONAtrinidadtanblacktan.JPG'],
            price=['$46'],
            size=[u'5', u'5.5', u'6', u'6.5', u'7', u'7.5', u'8', u'8.5', u'9', u'9.5', u'10'],
            color=[u'brown'],

    ),

    44: dict(
            name=['Wedding Dress in White Long Sleeve Evening Dress Coat - NC214'],
            img=['http://img0.etsystatic.com/000/0/6382668/il_570xN.285341386.jpg'],
            price=['$119.99'],
    ),

    49: dict(
            name=['Black Soft PU Slim Jacket'],
            img=['http://img.sheinside.com/images/sheinside.com/201202/1329354088017322535.jpg',
                 ' http://img.sheinside.com/images/sheinside.com/201202/1329354088507437899.jpg'],
            price=['$39'],
            size=[u'S', u'M', u'L'],
            color=['black'],
    ),

    50: dict(
            name=['Pearl Tassel Bracelet'],
            img=['http://a248.e.akamai.net/origin-cdn.volusion.com/gqewz.wpjoq/v/vspfiles/photos/PTB-2T.jpg?1363616408'],
            price=['$29.00'],
            size=[],
            color=[],
    ),

    51: dict(
            name=['Coral chain bracelet'],
            img=['http://media.dorothyperkins.com/wcsstore/DorothyPerkinsUS/images/catalog/49811957_normal.jpg'],
            price=['$15.00', '$4.00'],
            size=[],
            color=['coral'],
    ),

    53: dict(
            name=['T-shirt'],
            img=['http://st.mngbcn.com/rcs/pics/static/T8/fotos/S9/83208101_G5.jpg'],
            price=['$29.99'],
            size=[u'XXS', u'XS', u'S', u'M'],
            color=[],
    ),

    54: dict(
            name=['COACH LEGACY LEATHER MINI TANNER'],
            img=['http://dimg.dillards.com/is/image/DillardsZoom/03916954_zi_brass_black_violet?$c7product$'],
            price=['$258.00'],
    ),

    55: dict(
            name=['I CHI Trails Tee'],
            img=['http://www1.assets-gap.com/Asset_Archive/ATWeb/Assets/Product/895/895107/main/at895107-00p01v01.jpg',
                'http://www3.assets-gap.com/webcontent/0004/000/779/cn4000779.jpg'],
            price=['$39.00'],
            size=[u'XXS', u'XS', u'S', u'M', u'L', u'XL'],
            color=[u'sage'],
    ),

    56: dict(
            name=["D'Orsay Suede Flat / Citron"],
            img=['http://www.shoplesnouvelles.com/media/catalog/product/cache/1/image/9df78eab33525d08d6e5fb8d27136e95/j/e/jenni-kayne-suede-dorsay-flat-citron.jpg'],
            price=['$450.00', '$225.00'],
    ),

    #58: dict(
    #        name=[u'Alexa Velvet Sofa Wildon Home \xae',
    #              u'Wildon Home \xae Alexa Velvet Sofa'],
    #        img=[u'http://img4.wfrcdn.com/lf/8/hash/1261/7852491/1/Wildon-Home-%C2%AE-Alexa-Velvet-Sofa.jpg'],
    #        price=[u'$691.', u'$115.85', u'$20.75'],
    #),

    59: dict(
            name=['Layla Hair On Heel'],
            img=['http://assets.countryroad.com.au/ProductImages_Display/magnify/2/23382_124286_57688.jpg'],
            price=['$99.00', '$74.25'],
    ),

    61: dict(
            name=['Wake Up Top'],
            img=['http://www.stylelately.com/lib/thumbizer/thumb.php?src=/media/catalog/product//c/a/cara_1__1.jpg&w=350&h=480&q=90&zc=1'],
            price=['$34'],
    ),
    
    62: dict(
            name=['Three-Pocket Tank Dress in Stripe'],
            img=['http://s7d2.scene7.com/is/image/Saturday/C_4CMU0105_007_1_M?$productMain$'],
            price=['$47.50', '$95.00'],
    ),

    63: dict(
            name=[u'Stone Cut Out Buckle Platform Boots'],
            img=[u'http://images.newlook.com/is/image/newlook/shoe-gallery/ankle-boots/stone-cut-out-buckle-platform-boots-/290577621?$prod_details_hero$'],
            price=[u'\xa334.99'],
    ),

    66: dict(
            name=[u'Andress Split Maxi',
                   'Andress Split Maxi $58.00',
                 ],
            img=[u'https://saboskirt.com/Images/Product/Original/blackmaxiii_4.jpg'],
            price=[u'$58.00'],
    ),

    67: dict(
            name=[u"Women's Shirt With Lapel Solid Color and Puff Long Sleeve Design"],
            img=[u'http://cloud.faout.com/S/201208/source-img/1343780202824-P-341062.jpg'],
            price=['8.47'],
            size=['m', 'l', 'xl'],
            color=['pink', 'green'],
    ),

    72: dict(
            name=[u'910 Low-Rise Skinny Leg'],
            img=[u'http://www.jbrandjeans.com/store/productimages/regular/2851_pure_l.jpg'],
            price=[u'$101.40', u'$169.00'],
            size=[u'23', u'24', u'25', u'26', u'27', u'28', u'29', u'30', u'31', u'32'],
            color=[u'pure'],
    ),


    79: dict(
            name=[u'Slim Fit Military Field Shirt'],
            img=[u'https://www.sneakoutfitters.com/uploads/image/AO-CHDD-HW-5017-SO43detail1.jpg'],
            price=[u'$25.95'],
            size=['m', 'l', 'xl', 'xxl', 'xxl'],
            color=['white', 'black', 'red', 'light gray', 'khaki'],
    ),


    80: dict(
            name=[u'New Style Design Sport Pants'],
            img=[u'http://farm8.staticflickr.com/7310/9347747193_c2a5936013.jpg'],
            price=[u'$28.95'],
            size=[u'M', u'L', u'XL', u'XXL'],
            color=[u'grey', u'brown', u'black'],
    ),


    82: dict(
            name=[u'Zip Satchel'],
            img=[u'http://i2.ysi.bz/Assets/GalleryImage/54/297/L_g0023229754.jpg'],
            price=['$22.40'],
    ),

    83: dict(
            name=[u'T-Strap Flats'],
            img=[u'http://i2.ysi.bz/Assets/GalleryImage/81/725/L_g0023972581.jpg'],
            price=['22.40'],
    ),

    85: dict(
            name=[u'Selected Femme Houndstooth Cocoon Coat'],
            img=[u'http://images.anthropologie.eu/is/image/Anthropologie/7133445181303_018_e?$redesign-zoom-5x$', 'http://images.anthropologie.eu/is/image/Anthropologie/7133445181303_018_b?$redesign-zoom-5x$'],
            price=[u'\xa3158.00'],
            size=[u'6', u'8', u'10', u'12', u'14', u'16'],
            color=[u'black'],

    ),

    86: dict(
            name=[u'910 Low-Rise Skinny Leg'],
            img=[u'http://www.jbrandjeans.com/store/productimages/details/2851_pure_l_z.jpg'],
            price=[u'$169.00'],
            size=[u'23', u'24', u'25', u'26', u'27', u'28', u'29', u'30', u'31', u'32'],
            color=[u'pure'],
    ),

    87: dict(
            name=[u'811 Photo Ready Mid-Rise Skinny Leg'],
            img=[u'http://www.jbrandjeans.com/store/productimages/details/2867_impression_l_z.jpg'],
            price=[u'$202.00'],
    ),

    88: dict(
            name=[u'Stone Cut Out Buckle Platform Boots'],
            img=[u'http://images.newlook.com/is/image/newlook/shoe-gallery/ankle-boots/stone-cut-out-buckle-platform-boots-/290577621?$prod_details_hero$'],
            #price=[u'\xa334.99'],
            #size=[u'4', u'5', u'6', u'7', u'8'],
            #color=[],
    ),

    89: dict(
            name=[u'Tokyo Doll Grey Wrap Back Blouse'],
            img=[u'http://images.newlook.com/is/image/newlook/womens/tops/shirts-and-blouses/tokyo-doll-grey-wrap-back-blouse-/292084104?$prod_details_hero$'],
            price=[u'\xa317.99'],
    ),

    91: dict(
            name=[u'Elephant Bangle'],
            img=[u'http://cdn1.calypsostbarth.com/media/catalog/product/cache/1/image/424x/040ec09b1e35df139433887a97daa66f/8/0/803_150.jpg'],
            price=[u'$135.00'],
    ),

    95: dict(
            name=[u'Oscar Blandi Pronto Dry Styling Heat Protect Spray'],
            img=[u'http://www.birchbox.com/shop/media/catalog/product/cache/1/image/460x/9df78eab33525d08d6e5fb8d27136e95/o/s/oscarblandi_prontodrystylingheatprotectspray_900x900_1.jpg'],
            price=[u'$23.00'],
    ),

    96: dict(
            name=[u'Oscar Blandi Hair Lift Mousse'],
            img=[u'http://www.birchbox.com/shop/media/catalog/product/cache/1/image/460x/9df78eab33525d08d6e5fb8d27136e95/o/s/oscarblondi_hairliftmousse_900x900_2.jpg'],
            price=[u'$23.00'],
    ),

    99: dict(
            name=[u'Geneva Necklace'],
            img=[u'http://cdn.shopify.com/s/files/1/0005/7472/products/Geneva_Necklace_Julie_Vos_grande.jpg?10008',
                'http://cdn.shopify.com/s/files/1/0005/7472/products/Geneva_Necklace_Julie_Vos_grande.jpg?10014'],
            price=[u'$425.00'],
    ),

    281: dict(
            name=[u'Wanted Amarillo'],
            img=[u'http://a2.zassets.com/images/z/2/3/7/4/1/3/2374132-p-MULTIVIEW.jpg'],
            price=[u'$69.99'],
            size=['5.5', '6', '6.5', '7', '7.5', '8', '8.5', '9', '10'],
            color=['tan', 'black', 'blue', 'burgundy'],
    ),
        
    386: dict(
            name=['Heathered chamois elbow-patch shirt'],
            img=['http://s7.jcrew.com/is/image/jcrew/06791_WN9328?$pdp_fs418$'],
            price=['$98.00', '$98.00', '$103.00'],
    ),

    387: dict(
            name=['SCULPTED FEATHER BIB NECKLACE'],
            img=['https://d2wsknpdpvwfd3.cloudfront.net/assets/products/4345/product/N102G.jpg?1370458207'],
            price=['$78'],
    ),

    388: dict(
            name=['Draped Top'],
            img=['http://lp.hm.com/hmprod?set=key[source],value[/environment/2013/1QA_0280_002R.jpg]&set=key[rotate],value[0.5]&set=key[width],value[3449]&set=key[height],value[4033]&set=key[x],value[671]&set=key[y],value[275]&set=key[type],value[FASHION_FRONT]&hmver=0&call=url[file:/product/large]'],
            price=['$15', '$29.95'],
            color=['gold'],
    ),

    389: dict(
            name=[u'Dot Jacquard Fit & Flare Dress (Regular & Petite)'],
            img=[u'http://g.nordstromimage.com/imagegallery/store/product/Large/14/_8431794.jpg'],
            price=[u'$158.00', u'$158.00', u'$178.00'],
            size=[u'2', u'4', u'6', u'8', u'10', u'12', u'14', u'16'],
            color=[u'black', u'gold'],
    ),

    390: dict(
            name=[u'Sequin Bodice Cutout Back Maxi Dress'],
            img=[u'http://g.nordstromimage.com/imagegallery/store/product/Large/12/_8457272.jpg'],
            price=[u'$88.00'],
            size=[u'X-Small', u'Small', u'Medium', u'Large'],
            color=[u'navy', u'black'],
    ),

    391: dict(
            name=[u"'Bailey Bow' Boot (Women)"],
            img=[u'http://g.nordstromimage.com/imagegallery/store/product/Large/4/_7829784.jpg'],
            price=[u'$204.95'],
            size=[u'5', u'6', u'7', u'8', u'9', u'10', u'11'],
            color=[u'midnight', u'sangria'],
    ),

    392: dict(
            name=[u"'Austyn' Straight Leg Jeans (Washed Out)"],
            img=[u'http://g.nordstromimage.com/imagegallery/store/product/Large/7/_8218407.jpg'],
            price=[u'$198.00'],
            size=[u'28', u'29', u'38', u'30', u'40', u'31', u'32', u'33', u'34', u'36'],
            color=[u'washed out'],
    ),

    393: dict(
            name=[u"'Dover' Boot (Special Purchase)"],
            img=[u'http://g.nordstromimage.com/imagegallery/store/product/Large/9/_8406369.jpg'],
            price=[u'$99.90'],
            size=[u'5', u'5.5', u'9', u'6', u'9.5', u'6.5', u'10', u'7', u'11', u'7.5', u'8', u'8.5'],
            color=[u'black', u'moka'],
    ),

    394: dict(
            name=[u"'Oxford' Wallet"],
            img=[u'http://g.nordstromimage.com/imagegallery/store/product/Large/17/_8333037.jpg'],
            price=[u'Was: $40.00', u'Now: $30.00'],
            size=[],
            color=[u'navy', u'tan pebble'],
    ),

    395: dict(
            name=[u'Cable-knit pocket sweater'],
            img=[u'http://s7.jcrew.com/is/image/jcrew/08873_RD6174_m?$pdp_fs418$'],
            price=[u'$118.00'],
            size=[u'X-SMALL', u'SMALL', u'MEDIUM', u'LARGE', u'X-LARGE'],
            color=[],
    ),

    396: dict(
            name=[u'Printed Tuxedo Tee'],
            img=[u'http://images.anthropologie.com/is/image/Anthropologie/29484144_001_b?$product410x615$'],
            price=[u'$68.00'],
            size=[u'XS', u'S', u'M', u'L', u'XL'],
            color=[u'black', u'green', u'blue', u'mauve', u'red'],
    ),

    397: dict(
            name=[u'Lacy Wayfarers'],
            img=[u'http://images.anthropologie.com/is/image/Anthropologie/29575651_001_b?$product410x615$'],
            price=[u'$58.00'],
            size=[],
            color=[u'black'],
    ),

    398: dict(
            name=[u'Dotscape Dress'],
            img=[u'http://images.anthropologie.com/is/image/Anthropologie/29293248_049_b?$product410x615$'],
            #price=[u'$178.00)', u'$119.95'],
            #size=[u'XS', u'S', u'M', u'L', u'XL'],
            #color=[u'blue'],
    ),

    400: dict(
            name=[u'ASOS Ridley Supersoft High Waist Ultra Skinny Jeans in Busted Blue with Busted Knee'],
            img=[u'http://images.asos-media.com/inv/media/5/9/2/6/3546295/image4xl.jpg'],
            price=[u'$56.95'],
            size=[u'W25', u'W32', u'W26', u'W32', u'W24', u'W30', u'W36', u'W24', u'W28', u'W34', u'W25', u'W30'],
            color=[u'blue'],
    ),

    402: dict(
            name=[u'Vince Speed Stitch Raglan Tee'],
            img=[u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611914121/vince4611914121_q1_1-0_336x596.jpg'],
            price=[u'$115.00'],
            size=[u'XS', u'S', u'M', u'L'],
            color=['Coastal', 'Heather Grey'],
    ),

    403: dict(
            name=[u'Maison Martin Margiela Stamped Leather Booties'],
            img=[u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/margi/margi4035412345/margi4035412345_q1_1-0_336x596.jpg'],
            price=[u'$995.00'],
            size=[u'36', u'36.5', u'38', u'39'],
            color=[],
    ),
        
    404: dict(
            name=[u'Kate Spade New York Cherry Lane Darla Wallet'],
            img=[u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/kates/kates4041111784/kates4041111784_q1_1-0_336x596.jpg'],
            price=[u'$78.00'],
            size=[],
            color=[u'rose gold', 'surprise orange', 'cy blue', 'vivid snapdragon', 'black'],
    ),

    405: dict(
            name=[u'Soft Joie Cade Maxi Dress'],
            img=[u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/softj/softj4029020063/softj4029020063_q1_1-0_336x596.jpg'],
            price=[u'$148.00'],
            #size=[u'XS', u'S', u'M', u'L'],
            #color=['billiard', 'porcelain'],
    ),

    406: dict(
            name=[u'Chnnl Qltd Puffer'],
            img=[u'http://img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/61/14613058_201311061143.jpg'],
            price=[u'$34.99', u'$24.48'],
            size=[u'1', u'1'],
            color=[u'boysenberry', 'limeade', u'raspberry'],
    ),

    407: dict(
            name=[u"Women's Sam & Libby Kamila Thong Sandal with Back Strap - Metallic"],
            img=[u'http://img3.targetimg3.com/wcsstore/TargetSAS//img/p/14/41/14410005_130129163000.jpg'],
            price=[u'$24.99', u'$8.74'],
            #size=[u'5.5', u'6', u'6.5', u'7.5', u'8.5', u'9', u'9.5', u'10', u'11'],
            size=[u'5.5', u'10', u'11'],
            color=[],
    ),

    408: dict(
            name=[u"Merona\xae Women's Bootcut Jeans (Classic Fit) - Assorted Colors"],
            img=[u'http://img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/62/14625654_201307231756.jpg'],
            price=[u'$24.99', u'$14.99'],
            size=[u'2', u'4', u'6', u'8', u'10', u'12', u'14', u'16', u'18'],
            color=[u'dark wash', u'medium wash', u'rinse wash'],
    ),

    409: dict(
            name=[u'Open-Knit Striped Sweater'],
            img=[u'http://www.forever21.com/images/default_330/00091095-03.jpg'],
            price=[u'$22.80'],
            size=[u'Small', u'Medium', u'Large'],
            color=[u'mint cream'],
    ),

    410: dict(
            name=[u'Luxe Wedge Sandals'],
            img=[u'http://www.forever21.com/images/default_330/40496824-03.jpg'],
            price=[u'$36.80'],
            size=[u'6', u'7', u'8', u'9', u'10'],
            color=[u'black', u'nude'],
    ),

    #411: dict(
    #        name=[u'Simply Stated Twisted Ring'],
    #        img=[u'http://www.forever21.com/images/default_330/00126518-02.jpg'],
    #        price=[u'$3.80'],
    #        size=[u'6', u'7', u'8'],
    #        color=[u'gold'],
    #),

    412: dict(
            name=[u'Ore My Darling Dress in Plus Size BB Dakota'],
            img=[u'http://productshots2.modcloth.net/productshots/0135/9685/b1f796fcf6926d4b2d6110345de4fe75.jpg?1384465854'],
            price=[u'$99.99'],
            size=[u'16', u'18', u'20', u'22'],
            color=[],
    ),

    413: dict(
            name=[u'On the Bauble Necklace in Teal'],
            img=[u'http://productshots2.modcloth.net/productshots/0136/2465/e9a01b849858e0534f846b22fb89c9a7.jpg?1384983954'],
            price=[u'$24.99'],
            size=[],
            color=[],
    ),

    419: dict(
            name=[u'Pencil Skirt in LOFT Scuba'],
            img=[u'http://richmedia.channeladvisor.com/ImageDelivery/imageService?profileId=52000653&id=287233&recipeId=230'],
            price=[u'$39.88'],
            #size=[u'regular', 'petite'],
            #color=[u'brick red'],
    ),


    420: dict(
            name=[u'Seychelles Scoundrel Bootie'],
            img=[u'http://pics.ae.com/is/image/aeo/7411_7721_001_f?maskuse=off&wid=1504'],
            price=[u'$130.00'],
            size=[u'5', u'6', u'7', u'8', u'9', u'10', u'11'],
            color=[u'black', 'brown'],
    ),


}


CLICKING_RESULTS = {
16:
[{'colordata': [{'name': u'golden mustard',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/37532_WD6668?$pdp_fs418$',
                 'swatch_image': None}],
  'sizevalue': [u'00']},
 {'colordata': [{'name': u'navy lines',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/37532_WD6562?$pdp_fs418$',
                 'swatch_image': None}],
  'sizevalue': [u'0']},
 {'colordata': [{'name': u'navy lines',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/37532_WD6562?$pdp_fs418$',
                 'swatch_image': None}],
  'sizevalue': [u'6']},
 {'colordata': [{'name': u'golden mustard',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/37532_WD6668?$pdp_fs418$',
                 'swatch_image': u'http://s7.jcrew.com/is/image/jcrew/37532_WD6668_sw?$pdp_sw20$'}],
  'sizevalue': [u'0']},
 {'colordata': [{'name': u'golden mustard',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/37532_WD6668?$pdp_fs418$',
                 'swatch_image': u'http://s7.jcrew.com/is/image/jcrew/37532_WD6668_sw?$pdp_sw20$'}],
  'sizevalue': [u'6']}],

386:
[{'colordata': [{'name': u'hthr oatmeal',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/06791_WN9328?$pdp_fs418$',
                 'swatch_image': None}],
  'sizevalue': [u'X-SMALL']},
 {'colordata': [{'name': u'hthr oatmeal',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/06791_WN9328?$pdp_fs418$',
                 'swatch_image': None}],
  'sizevalue': [u'SMALL']},
 {'colordata': [{'name': u'hthr oatmeal',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/06791_WN9328?$pdp_fs418$',
                 'swatch_image': None}],
  'sizevalue': [u'X-LARGE']},
 {'colordata': [{'name': u'hthr granite',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/06791_WN9327?$pdp_fs418$',
                 'swatch_image': u'http://s7.jcrew.com/is/image/jcrew/06791_WN9327_sw?$pdp_sw20$'}],
  'sizevalue': [u'X-SMALL']},
 {'colordata': [{'name': u'hthr granite',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/06791_WN9327?$pdp_fs418$',
                 'swatch_image': u'http://s7.jcrew.com/is/image/jcrew/06791_WN9327_sw?$pdp_sw20$'}],
  'sizevalue': [u'SMALL']},
 {'colordata': [{'name': u'hthr granite',
                 'product_image': u'http://s7.jcrew.com/is/image/jcrew/06791_WN9327?$pdp_fs418$',
                 'swatch_image': u'http://s7.jcrew.com/is/image/jcrew/06791_WN9327_sw?$pdp_sw20$'}],
  'sizevalue': [u'X-LARGE']}],

388:
[{'colordata': [{'name': u'gold',
                 'product_image': u'http://lp.hm.com/hmprod?set=key[source],value[/model/2013/1QA%200210312%20002%2071%200341.jpg]&set=key[rotate],value[]&set=key[width],value[]&set=key[height],value[]&set=key[x],value[]&set=key[y],value[]&set=key[type],value[STILL_LIFE_FRONT]&hmver=3&call=url[file:/product/zoom]&zap=ver[1.22],size[128],x[4],y[2],layer[100]&sink',
                 'swatch_image': None}],
  'sizevalue': [u'XS']},
 {'colordata': [{'name': u'gold',
                 'product_image': u'http://lp.hm.com/hmprod?set=key[source],value[/model/2013/1QA%200210312%20002%2071%200341.jpg]&set=key[rotate],value[]&set=key[width],value[]&set=key[height],value[]&set=key[x],value[]&set=key[y],value[]&set=key[type],value[STILL_LIFE_FRONT]&hmver=3&call=url[file:/product/large]',
                 'swatch_image': None}],
  'sizevalue': [u'S']},
 {'colordata': [{'name': u'gold',
                 'product_image': u'http://lp.hm.com/hmprod?set=key[source],value[/model/2013/1QA%200210312%20002%2071%200341.jpg]&set=key[rotate],value[]&set=key[width],value[]&set=key[height],value[]&set=key[x],value[]&set=key[y],value[]&set=key[type],value[STILL_LIFE_FRONT]&hmver=3&call=url[file:/product/large]',
                 'swatch_image': None}],
  'sizevalue': [u'M']}],

389:
[{'colordata': [{'name': u'black/ gold',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/14/_8431794.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'2']},
 {'colordata': [{'name': u'black/ gold',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/14/_8431794.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'4']},
 {'colordata': [{'name': u'black/ gold',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/14/_8431794.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'6']}]
,

390:
[{'colordata': [{'name': u'navy/ black',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/12/_8457272.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'Medium']},
 {'colordata': [{'name': u'navy/ black',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/12/_8457272.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'Large']}]
,

391:
[{'colordata': [{'name': u'midnight',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/4/_7829784.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'5']},
 {'colordata': [{'name': u'sangria',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/4/_7829784.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'6']},
 {'colordata': [{'name': u'sangria',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/4/_7829784.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'7']},
 {'colordata': [{'name': u'princess pink',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/18/_8100138.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'5']},
 {'colordata': [{'name': u'princess pink',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/18/_8100138.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'6']},
 {'colordata': [{'name': u'princess pink',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/18/_8100138.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'7']},
 {'colordata': [{'name': u'midnight',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/6/_7817986.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'6']},
 {'colordata': [{'name': u'midnight',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/6/_7817986.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'7']},
 {'colordata': [{'name': u'sangria',
                 'product_image': u'http://g.nordstromimage.com/imagegallery/store/product/Large/4/_7829784.jpg',
                 'swatch_image': u'http://g.nordstromimage.com/imagegallery/store/product/SwatchSmall/5/_7829785.jpg'}],
  'sizevalue': [u'5']}]
,

396:
[{'colordata': [{'name': u'green',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_030_c?$product410x615$',
                 'swatch_image': None}],
  'sizevalue': [u'XS']},
 {'colordata': [{'name': u'green',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_030_b?$product410x615$',
                 'swatch_image': None}],
  'sizevalue': [u'S']},
 {'colordata': [{'name': u'green',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_030_b?$product410x615$',
                 'swatch_image': None}],
  'sizevalue': [u'M']},
 {'colordata': [{'name': u'red',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_060_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_060_s3.png'}],
  'sizevalue': [u'XS']},
 {'colordata': [{'name': u'red',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_060_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_060_s3.png'}],
  'sizevalue': [u'S']},
 {'colordata': [{'name': u'red',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_060_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_060_s3.png'}],
  'sizevalue': [u'M']},
 {'colordata': [{'name': u'mauve',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_054_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_054_s3.png'}],
  'sizevalue': [u'XS']},
 {'colordata': [{'name': u'mauve',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_054_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_054_s3.png'}],
  'sizevalue': [u'S']},
 {'colordata': [{'name': u'mauve',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_054_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_054_s3.png'}],
  'sizevalue': [u'M']},
 {'colordata': [{'name': u'blue',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_040_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_040_s3.png'}],
  'sizevalue': [u'XS']},
 {'colordata': [{'name': u'blue',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_040_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_040_s3.png'}],
  'sizevalue': [u'S']},
 {'colordata': [{'name': u'blue',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_040_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_040_s3.png'}],
  'sizevalue': [u'M']},
 {'colordata': [{'name': u'black',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_001_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_001_s3.png'}],
  'sizevalue': [u'XS']},
 {'colordata': [{'name': u'black',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_001_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_001_s3.png'}],
  'sizevalue': [u'S']},
 {'colordata': [{'name': u'black',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_001_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_001_s3.png'}],
  'sizevalue': [u'M']},
 {'colordata': [{'name': u'green',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_030_b?$product410x615$',
                 'swatch_image': None}],
  'sizevalue': [u'XXS P']},
 {'colordata': [{'name': u'green',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_030_b?$product410x615$',
                 'swatch_image': None}],
  'sizevalue': [u'XS P']},
 {'colordata': [{'name': u'green',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_030_b?$product410x615$',
                 'swatch_image': None}],
  'sizevalue': [u'S P - sold out']},
 {'colordata': [{'name': u'black',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_001_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_001_s3.png'}],
  'sizevalue': [u'S - sold out']},
 {'colordata': [{'name': u'black',
                 'product_image': u'http://images.anthropologie.com/is/image/Anthropologie/29484144_001_b?$product410x615$',
                 'swatch_image': u'/anthro/images/swatches/29484144_001_s3.png'}],
  'sizevalue': [u'M - sold out']}]
,

401:
[{'colordata': [{'name': u'black',
                 'product_image': u'http://www3.assets-gap.com/webcontent/0007/285/770/cn7285770.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'5']},
 {'colordata': [{'name': u'black',
                 'product_image': u'http://www3.assets-gap.com/webcontent/0007/285/770/cn7285770.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'9']}]
,

402:
[{'colordata': [{'name': u'coastal',
                 'product_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611914121/vince4611914121_q1_1-0_336x596.jpg',
                 'swatch_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611914121/vince4611914121_sw_1-0.jpg'}],
  'sizevalue': [u'XS']},
 {'colordata': [{'name': u'coastal',
                 'product_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611914121/vince4611914121_q1_1-0_336x596.jpg',
                 'swatch_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611914121/vince4611914121_sw_1-0.jpg'}],
  'sizevalue': [u'S']},
 {'colordata': [{'name': u'coastal',
                 'product_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611914121/vince4611914121_q1_1-0_336x596.jpg',
                 'swatch_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611914121/vince4611914121_sw_1-0.jpg'}],
  'sizevalue': [u'M']},
 {'colordata': [{'name': u'heather grey',
                 'product_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611910495/vince4611910495_q1_1-0_336x596.jpg',
                 'swatch_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611910495/vince4611910495_sw_1-0.jpg'}],
  'sizevalue': [u'XS']},
 {'colordata': [{'name': u'heather grey',
                 'product_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611910495/vince4611910495_q1_1-0_336x596.jpg',
                 'swatch_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611910495/vince4611910495_sw_1-0.jpg'}],
  'sizevalue': [u'S']},
 {'colordata': [{'name': u'heather grey',
                 'product_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611910495/vince4611910495_q1_1-0_336x596.jpg',
                 'swatch_image': u'http://g-ecx.images-amazon.com/images/G/01/Shopbop/p/pcs/products/vince/vince4611910495/vince4611910495_sw_1-0.jpg'}],
  'sizevalue': [u'M']}]
,

408:
[{'sizevalue': [u'4']},
 {'sizevalue': [u'6']},
 {'colordata': [{'name': u'medium wash',
                 'product_image': u'http://img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/62/14624731_201307231756.jpg',
                 'swatch_image': u'http://Img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/62/14624731_Swatch.jpg'}],
  'sizevalue': [u'2']},
 {'colordata': [{'name': u'medium wash',
                 'product_image': u'http://img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/62/14624731_201307231756.jpg',
                 'swatch_image': u'http://Img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/62/14624731_Swatch.jpg'}],
  'sizevalue': [u'4']},
 {'colordata': [{'name': u'medium wash',
                 'product_image': u'http://img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/62/14624731_201307231756.jpg',
                 'swatch_image': u'http://Img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/62/14624731_Swatch.jpg'}],
  'sizevalue': [u'6']},
 {'colordata': [{'name': u'dark wash',
                 'product_image': u'http://img3.targetimg3.com/wcsstore/TargetSAS//img/p/14/62/14624510_201307231756.jpg',
                 'swatch_image': u'http://Img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/62/14624510_Swatch.jpg'}],
  'sizevalue': [u'2']},
 {'colordata': [{'name': u'dark wash',
                 'product_image': u'http://img3.targetimg3.com/wcsstore/TargetSAS//img/p/14/62/14624510_201307231756.jpg',
                 'swatch_image': u'http://Img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/62/14624510_Swatch.jpg'}],
  'sizevalue': [u'4']},
 {'colordata': [{'name': u'dark wash',
                 'product_image': u'http://img3.targetimg3.com/wcsstore/TargetSAS//img/p/14/62/14624510_201307231756.jpg',
                 'swatch_image': u'http://Img2.targetimg2.com/wcsstore/TargetSAS//img/p/14/62/14624510_Swatch.jpg'}],
  'sizevalue': [u'6']}]
,

409:
[{'colordata': [{'name': u'mint/cream',
                 'product_image': u'http://www.forever21.com/images/default_330/00091095-03.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'Small']},
 {'colordata': [{'name': u'mint/cream',
                 'product_image': u'http://www.forever21.com/images/default_330/00091095-03.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'Medium']},
 {'colordata': [{'name': u'mint/cream',
                 'product_image': u'http://www.forever21.com/images/default_330/00091095-03.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'Large']}]
,

410:
[{'colordata': [{'name': u'nude',
                 'product_image': u'http://www.forever21.com/images/default_330/40496824-04.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'6']},
 {'colordata': [{'name': u'nude',
                 'product_image': u'http://www.forever21.com/images/default_330/40496824-04.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'7']},
 {'colordata': [{'name': u'nude',
                 'product_image': u'http://www.forever21.com/images/default_330/40496824-04.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'8']},
 {'colordata': [{'name': u'black',
                 'product_image': u'http://www.forever21.com/images/default_330/40496824-03.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'6']},
 {'colordata': [{'name': u'black',
                 'product_image': u'http://www.forever21.com/images/default_330/40496824-03.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'7']},
 {'colordata': [{'name': u'black',
                 'product_image': u'http://www.forever21.com/images/default_330/40496824-03.jpg',
                 'swatch_image': None}],
  'sizevalue': [u'8']}]
,

412:
[{'sizevalue': [u'16']}, {'sizevalue': [u'18']}, {'sizevalue': [u'20']}]
,


417:
[{'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('69.90')))],
  'colordata': [{'name': u'cobalt blue',
                 'product_image': u'http://images.express.com/is/image/expressfashion/20_030_8785_807_22?iv=hu9TB2&wid=351&hei=410',
                 'swatch_image': u'//images.express.com/is/image/expressfashion/20_030_8785_807_s?$swatch$'}],
  'sizevalue': [u'Large - Only 2 left']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('69.90')))],
  'colordata': [{'name': u'ensign blue',
                 'product_image': u'http://images.express.com/is/image/expressfashion/20_030_8785_176_14?iv=d7PSf2&wid=351&hei=410',
                 'swatch_image': u'//images.express.com/is/image/expressfashion/20_030_8785_176_s?$swatch$'}],
  'sizevalue': [u'XX Large - Only 1 left']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('69.90')))],
  'colordata': [{'name': u'charcoal',
                 'product_image': u'http://images.express.com/is/image/expressfashion/20_030_8785_934_30?iv=rghTr0&wid=351&hei=410',
                 'swatch_image': u'//images.express.com/is/image/expressfashion/20_030_8785_934_s?$swatch$'}],
  'sizevalue': [u'X Small - Only 1 left']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('69.90')))],
  'colordata': [{'name': u'charcoal',
                 'product_image': u'http://images.express.com/is/image/expressfashion/20_030_8785_934_30?iv=rghTr0&wid=351&hei=410',
                 'swatch_image': u'//images.express.com/is/image/expressfashion/20_030_8785_934_s?$swatch$'}],
  'sizevalue': [u'Small - Only 1 left']}]
,

420:
[{'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('64.99')))],
  'colordata': [{'name': u'black',
                 'product_image': u'http://pics.ae.com/is/image/aeo/7411_7721_001_f?maskuse=off&wid=1119&size=1121,1254&fit=crop&qlt=70,0',
                 'swatch_image': None}],
  'sizevalue': [u'5']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('64.99')))],
  'colordata': [{'name': u'black',
                 'product_image': u'http://pics.ae.com/is/image/aeo/7411_7721_001_f?maskuse=off&wid=1119&size=1121,1254&fit=crop&qlt=70,0',
                 'swatch_image': None}],
  'sizevalue': [u'6']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('64.99')))],
  'colordata': [{'name': u'black',
                 'product_image': u'http://pics.ae.com/is/image/aeo/7411_7721_001_f?maskuse=off&wid=1119&size=1121,1254&fit=crop&qlt=70,0',
                 'swatch_image': None}],
  'sizevalue': [u'6 1/2']}]
,

424:
[ {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('48.00')))],
  'sizetypevalue': [u'petite'],
  'sizevalue': [u'8']},
  {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('48.00')))],
  'colordata': [{'name': u'pink',
                 'product_image': None,
                 'swatch_image': u'/anthro/images/swatches/28621472_066_s3.png'}],
  'sizetypevalue': [u'petite'],
  'sizevalue': [u'8']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('48.00')))],
  'colordata': [{'name': u'blue',
                 'product_image': None,
                 'swatch_image': u'/anthro/images/swatches/28621472_040_s3.png'}],
  'sizetypevalue': [u'petite'],
  'sizevalue': [u'8']}]
,

430:
[{'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('78.00')))],
  'colordata': [{'name': u'navy/sterling',
                 'product_image': 'https://product-images-from-canvas.s3.amazonaws.com/http%3A/www.cwonder.com/Categories/Clothing/Sweaters/Chevron-Bateau-Sweater/product/CWW-H13-SW640.html%20navy/sterling?Signature=najBp5gDLXRKryrKFWKEbLVHvZM%3D&Expires=1398100713&AWSAccessKeyId=AKIAJYJDNH3B4757RTRA',
                 'swatch_image': None}],
  'sizevalue': [u'XS']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('78.00')))],
  'colordata': [{'name': u'ash heather grey/buttercup',
                 'product_image': 'https://product-images-from-canvas.s3.amazonaws.com/http%3A/www.cwonder.com/Categories/Clothing/Sweaters/Chevron-Bateau-Sweater/product/CWW-H13-SW640.html%20ash%20heather%20grey/buttercup?Signature=I8nvkvbK2SVd6NDF4owJjoDrdT0%3D&Expires=1398100733&AWSAccessKeyId=AKIAJYJDNH3B4757RTRA',
                 'swatch_image': None}],
  'sizevalue': [u'S']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('78.00')))],
  'colordata': [{'name': u'ecru/ash heather grey',
                 'product_image': 'https://product-images-from-canvas.s3.amazonaws.com/http%3A/www.cwonder.com/Categories/Clothing/Sweaters/Chevron-Bateau-Sweater/product/CWW-H13-SW640.html%20ecru/ash%20heather%20grey?Signature=J%2FFHYVDabiqwqQ1HwT4ceC%2FJKXc%3D&Expires=1398100750&AWSAccessKeyId=AKIAJYJDNH3B4757RTRA',
                 'swatch_image': None}],
  'sizevalue': [u'XS']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('78.00')))],
  'colordata': [{'name': u'ecru/ash heather grey',
                 'product_image': 'https://product-images-from-canvas.s3.amazonaws.com/http%3A/www.cwonder.com/Categories/Clothing/Sweaters/Chevron-Bateau-Sweater/product/CWW-H13-SW640.html%20ecru/ash%20heather%20grey?Signature=XCvSbkDS4Oai8t2X5sdPpfsCXWs%3D&Expires=1398100764&AWSAccessKeyId=AKIAJYJDNH3B4757RTRA',
                 'swatch_image': None}],
  'sizevalue': [u'S']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('78.00')))],
  'sizevalue': [u'XS']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('78.00')))],
  'sizevalue': [u'S']},
 {'checkoutprice': [PriceSingle(price_value=PriceValue(currency=u'$', value=Decimal('78.00')))],
  'colordata': [{'name': u'navy/sterling',
                 'product_image': 'https://product-images-from-canvas.s3.amazonaws.com/http%3A/www.cwonder.com/Categories/Clothing/Sweaters/Chevron-Bateau-Sweater/product/CWW-H13-SW640.html%20navy/sterling?Signature=wBS0vMmFIcziAD7XA%2FibQZ7UrSY%3D&Expires=1398100820&AWSAccessKeyId=AKIAJYJDNH3B4757RTRA',
                 'swatch_image': None}],
  'sizevalue': [u'S']}]
,

}

INVALID_PRODUCT_PAGES = [
        1,
        4,
        5,
        8,
        9,
        10,
        11,
        12,
        13,
        18,
        19,
        20,
        21,
        24,
        25,
        26,
        28,
        29,
        30,
        32,
        33,
        34,
        36,
        37,
        39,
        41,
        42,
        51,
        53,
        59,
        62,
        85,
        91,
        95,
]
