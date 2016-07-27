logical_categories = [{
    "apparel": [{
        "dresses": [
            "dress",
            "shift",
            "maxi",
            "gown",
            "romper",
            "sheath"
        ]
    }, {
        "sweaters": [
            "sweater",
            "hood",
            "sweatshirt",
            "knit",
            "cardigan",
            "pullover"
        ]
    }, {
        "pants": [
            "pant",
            "short",
            "bottom",
            "slack",
            "chino",
            "cords",
            "capris",
            "trouser",
            "trunk",
            "cargo",
            "leg",
            "khakis",
            "bermuda",
            "tights",
            "leggings"
        ]
    }, {
        "shirts": [
            "shirt",
            "tank",
            "cami",
            "blouse",
            "tunic",
            "tee",
            "polo",
            "turtleneck",
            "v-neck",
            "crewneck",
            "cowl",
            "henley",
            "button-down",
            "long sleeve"
        ]
    }, {
        "skirts": [
            "skirt",
            "skort",
            "mini",
            "pencil skirt",
            "maxiskirt"
        ]
    }, {
        "denim": [
            "denim",
            "jeans"
        ]
    }, {
        "outerwear": [
            "outerwear",
            "jackets",
            "coat",
            "blazer",
            "vest",
            "sportcoat",
            "trench",
            "peacoat",
            "topcoat",
            "poncho",
            "shawl"
        ]
    }]
}, {
    "intimates": [
        "underwear",
        "underwire",
        "briefs",
        "boxers",
        "bra",
        "panties",
        "intimate",
        "thong",
        "undergarment"
    ]
}, {
    "shoes": [
        "footwear",
        "shoe",
        "sock",
        "pump",
        "heel",
        "flip flops",
        "flip-flops",
        "boots",
        "bootie",
        "loafer",
        "sandal",
        "wedge",
        "sneaker",
        "wingtip",
        "gladiator",
        "stiletto"
    ]
}, {
    "sleepwear": [
        "sleepwear",
        "robe",
        "nightgown",
        "pajama",
        "nightie",
        "loungewear"
    ]
}, {
    "accessories": [
        "belt",
        "mittens",
        "gloves",
        "headband",
        "umbrella", {
            "scarves": [
                "scarf"
            ]
        }, {
            "hats": [
                "beanie",
                "fedora",
                "beret",
                "wide brim",
                "baseball hat",
                "baseball cap",
                "cowboy hat",
                "visor"
            ]
        }
    ]
}, {
    "glasses": [
        "sunglasses",
        "glasses",
        "eyewear",
        "aviator",
        "aviators"
    ]
}, {
    "bags": [
        "wallet",
        "handbag",
        "tote",
        "wristlet",
        "satchel",
        "briefcase",
        "duffel",
        "backpack",
        "clutch",
        "hobo",
        "cross-body",
        "crossbody",
        "purse",
        "messenger",
        "courier"
    ]
}, {
    "jewelry": [
        "bangle",
        "cuff bracelet",
        "brooch",
        "hoops",
        "earrings",
        "necklace",
        "bracelet",
        "pendant",
        "jewelry",
        "watches"
    ]
}, {
    "swimwear": [
        "bikini",
        "one-piece",
        "one piece",
        "swimsuit",
        "swim suit",
        "tankini",
        "bandeau",
        "two-piece",
        "two piece",
        "cover up",
        "coverup",
        "sarong"
    ]
}, {
    "beauty": [
        "fragrance",
        "lipstick",
        "nailpolish",
        "perfume"
    ]
}, {
    "maternity": [
        "maternity",
        "pregnancy",
        "pregnant"
    ]
}, {
    "plus-size": [
        "plus-size",
        "plus size",
        "plus-sized",
        "plus sized"
    ]
}, {
    "active": [
        "yoga",
        "sports bra",
        "workout",
        "runner",
        "wetsuit",
        "leotard",
        "sport"
    ]
}]

def get_rev_mapping(data, parents=None):
    if parents is None:
        parents = []
    out_dict = {}
    for element in data:
        if type(element) == dict:
            subcategory = element.keys()[0]
            if parents:
                out_dict.update({subcategory: [subcategory]+parents})
            else:
                out_dict.update({subcategory: [subcategory]})
            out_dict.update(get_rev_mapping(element.values()[0], [subcategory]+parents))
        else:
            out_dict.update({element: [element]+parents})
    return out_dict

def get_categories(data):
    out = []
    for element in data:
        if type(element) == dict:
            out.append(element.keys()[0])
            out.extend(get_categories(element.values()[0]))
    return out

logical_categories_reverse_mapping = get_rev_mapping(logical_categories)
categories_list = get_categories(logical_categories)
