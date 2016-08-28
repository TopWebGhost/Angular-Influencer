DATA = {}

DATA['blogspot'] = '''
http://pennypincherfashion.com
http://walkinginmemphisinhighheels.com
http://alittledashofdarling.com
http://girlwithalatte.blogspot.com
http://forchicsake.com
http://fashboulevard.com
http://stylelixir.com
http://hooahandhiccups.com
http://moiology.com
http://thestylishhousewife.com
http://bsoup.blogspot.se
http://belledecouture.com
http://shannonhearts.blogspot.com
http://jessicawho.me
http://seersuckerandsaddles.blogspot.com
http://becauseshannasaidso.blogspot.com/
http://seejaneworkplaylive.blogspot.com
http://www.thesweetestthingblog.com/
http://classroomcouture.blogspot.com
'''

DATA['wordpress'] = '''
http://crosswalkmuse.wordpress.com
http://piratesandfireflies.wordpress.com
http://rubyassata.wordpress.com
http://tunesandtunics.wordpress.com
http://annamargrete.wordpress.com
http://mademoiselleandcomag.wordpress.com
http://vdoodle.wordpress.com
http://syntendenza.wordpress.com
http://folknfables.wordpress.com
http://glamside.wordpress.com
http://plasticky.wordpress.com
http://thenewmrshamilton.wordpress.com
http://splashoflace.wordpress.com
http://fashnaddict.wordpress.com
http://necitana.wordpress.com
http://bitsnbows.wordpress.com
http://formalfriday.wordpress.com
http://stardustandsequins.wordpress.com
http://courtneyem.wordpress.com
http://walkinginmyheels.wordpress.com
http://thestylishhousewife.com
http://gbofashion.com
'''

DATA['tumblr'] = '''
http://thediggerman.tumblr.com
http://barbiedollfashion.tumblr.com
http://overratedvogue.tumblr.com
http://americanballade.tumblr.com
http://preppywisz.tumblr.com
http://cafedumonstre.tumblr.com
http://itslightninghearts.tumblr.com
http://rachaelreally.tumblr.com
http://whatiwore.tumblr.com
http://whatiwore.tumblr.com
http://smonetfashion.tumblr.com
http://partytights.tumblr.com
http://sweetlomiranda.tumblr.com
http://thesoutharddiaries.tumblr.com
http://jessicachu.tumblr.com
http://textbook.tumblr.com
http://myidealhome.tumblr.com
http://www.facebook.com/myidealhome.tumblr
http://thegirlnextdior.tumblr.com
http://itsallaboutchanel.tumblr.com
http://pantyhoseparty.tumblr.com
http://pizzarulez.tumblr.com
http://blackstuddedfashion.tumblr.com
http://sarahhawkinson.tumblr.com
http://succarra.tumblr.com
http://lovejewelry.tumblr.com
'''

def parse_urls(s):
    lines = s.split('\n')
    lines = [l.strip() for l in lines if l.strip()]
    return lines

URLS = { k: parse_urls(v) for k, v in DATA.items() }


# select up.id from debra_userprofile up, debra_platform pl
# where up.blog_page = pl.url
# and up.is_trendsetter=true;
USER_PROFILE_IDS_WITH_BLOG_PAGE_MATCHING_PLATFORM = [
 5036,
 3893,
 3993,
 3882,
 4024,
 6533,
 3961,
 4903,
 587,
 4031,
 3858,
 3865,
 3953,
 69,
 10587,
 3872,
 4007,
 2725,
 3887,
 3753,
 4491,
 3527,
 3878,
 3638,
 3958,
 3871,
 4041,
 10599,
 3987,
 10595,
 10589,
 10590,
 10586,
 4004,
 4009,
 563,
 6646,
 4472,
 4037,
 3874,
 3806,
 3925,
 3885,
 4042,
 3862,
 2023,
 3959,
 3880,
 4466,
 3812,
 4420,
 3833,
 4005,
 3908,
 1580,
 3948,
 4028,
 3048,
]

