from debra.models import Brands, UserProfile, User
from debra.models import WishlistItem
import gspread
NUM_MAX_TAGS = 30

brand_tags = {}


def get_categorization_data():
    gc = gspread.login('lauren@theshelf.com', 'namaste_india')
    wks = gc.open('Store Tags').sheet1
    list_of_lists = wks.get_all_values()

    keywords = list_of_lists[0]
    for l in list_of_lists[1:]:
        bnames= l[0]
        bname = bnames.split('/')
        for bb in bname:
            print "\nSTORE: %s \n" % bb
            index = 1
            brand_elem = Brands.objects.filter(name__icontains = bb.strip())
            tags = []
            for kk in l[1:]:
                if kk == 'YES':
                    print keywords[index],
                    tags.append(keywords[index])
                index += 1
            for elem in brand_elem:
                brand_tags[elem] = tags

    for b in brand_tags.keys():
        print b, len(brand_tags[b]), brand_tags[b]

'''
Find the similarity between two brands.
0 = no similarity
1 = 100% similarity

We use similarity of tags to measure similarity of brands.

b1 -> t11, t12, t13, t14
b2 -> t21, t22, t23, t24

similarity = b1.b2 (cross product)

'''
def similarity_in_brands(b1, b2):

    #tags_b1 = BrandTags.objects.filter(brand=b1)
    #tags_b2 = BrandTags.objects.filter(brand=b2)
    #t1 = [t.tag for t in tags_b1]
    #t2 = [t.tag for t in tags_b2]

    t1 = brand_tags[b1]
    t2 = brand_tags[b2]

    print "number of t1 tags = %d" % len(t1)
    print "number of t2 tags = %d" % len(t2)

    all_set = set()
    comm = set()
    for t in t1:
        all_set.add(t)
        if t in t2:
            comm.add(t)

    for t in t2:
        all_set.add(t)
    print "Found common tags %s " % comm

    return len(comm)*1.0/len(all_set)



'''
Find relevant bloggers for a given brand

Idea:
a) find all bloggers who have items from this brand in their shelf
b) find all bloggers who have an ad from this brand
c) find all other similar brands (similarity > 50%) and then all bloggers from these brands,
    sorted by similarity

'''
def relevant_bloggers(b1):

    all_bloggers = UserProfile.objects.filter(_can_set_affiliate_links=True)
    level_one_bloggers = []

    level_two_bloggers = {}

    all_brands = Brands.objects.all().exclude(id=b1.id)

    similar_brands = []

    for b in all_brands:
        if b != b1:
            try:
                sim = similarity_in_brands(b, b1)
                if sim > 0.5:
                    similar_brands.append((b, sim))
            except:
                print "problem finding similarity between %s %s " % (b, b1)
                pass

    for a in all_bloggers:
        wi = WishlistItem.objects.filter(user_id = a.user, user_selection__item__brand = b1)
        if len(wi)>0:
            level_one_bloggers.append(a)
            print "added %s %s in relevent bloggers " % (a.user.email, a.user.id)

    print "Found %d number of bloggers that have blogged about %s" % (len(level_one_bloggers), b1)

    for b,sim in similar_brands:
        print "Checking b %s and sim %s " % (b,sim)

    if len(level_one_bloggers) < 5:
        for a in all_bloggers:
            for b,sim in similar_brands:
                print "Checking b %s sim %s"% (b,sim)
                wi = WishlistItem.objects.filter(user_id = a.user, user_selection__item__brand = b)
                if len(wi) > 0:
                    if a in level_two_bloggers.keys():
                        level_two_bloggers[a].append(b)
                    else:
                        level_two_bloggers[a] = []
                        level_two_bloggers[a].append(b)


    return (level_one_bloggers, level_two_bloggers)

