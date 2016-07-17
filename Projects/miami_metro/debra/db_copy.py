from debra.models import *
from social_discovery.blog_discovery import queryset_iterator
from xps import models as xps_models
import datetime
import gc

from django.db.models import Q


"""
This is a file with scripts to copy data for
Influencers.objects.filter.filter(show_on_search=True).exclude(blacklisted=True).exclude(blog_url__contains='artificial_blog')
and their correcponding objects to new DB of reduced size.

SOURCE DATABASE: 'default'
TARGET DATABASE: 'production'

Strategy of copying:
    1. Initially we copy all required tables to copy designated Influencers ASAP.
    2. After that we copy the rest of the tables using filtering by these influencers.
    3. If a table we currently copy is relatively small and has no FKs or has FKs to another small table(s),
        then we copy it in full and iteratively in one function.
    4. If table has a big amount of entries (100K+), then we import data in slices on several tmux sessions
        (for example, 0...100000 entries in the first session, 100K...200K in the second, etc.)

Part I: copying all required tables and Influencers table.
Part II: copying remaining tables.
PART III: Separate copying of ProductModelShelfMap and dependent tables

"""

SOURCE_DB_NAME = 'default'
TARGET_DB_NAME = 'production'

# PART I
# copying table django.contrib.auth.models.User, suggested slice offset: 200000
def copy_users_slices(start, end):
    print('%s Copying users...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    user_ids = User.objects.using(SOURCE_DB_NAME).all().order_by('id').values_list('id', flat=True)[start:end]
    users = User.objects.using(SOURCE_DB_NAME).filter(id__in=user_ids)
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s User models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s users.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# copying tables: DemographicsLocality, BrandCategory, Category. They are small tables.
def copy_part1_01():
    print('%s Copying DemographicsLocality...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    users = DemographicsLocality.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s DemographicsLocality models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s DemographicsLocality objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying BrandCategory...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    users = BrandCategory.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s BrandCategory models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s BrandCategory objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying Category...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    users = Category.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Category models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s Category objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# copying table debra.Brands, suggested slice offset: 100000
def copy_brand_slices(start, end):
    print('%s Copying Brands...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    user_ids = Brands.objects.using(SOURCE_DB_NAME).all().order_by('id').values_list('id', flat=True)[start:end]
    users = Brands.objects.using(SOURCE_DB_NAME).filter(id__in=user_ids)
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Brands models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s Brands objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# copying table debra.UserProfile, suggested slice offset: 100000
# Because UserProfile table and Influencer table have mutual FKs, UserProfile's FK to influencer is set to None.
# On Influencer copying it will be restored.
def copy_user_profiles_slices(start, end):
    print('%s Copying UserProfile (!)...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    user_ids = UserProfile.objects.using(SOURCE_DB_NAME).all().order_by('id').values_list('id', flat=True)[start:end]
    users = UserProfile.objects.using(SOURCE_DB_NAME).filter(id__in=user_ids)
    ctr = 0
    for obj in queryset_iterator(users):
        obj.influencer = None
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s UserProfile models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s UserProfile objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

# copying table debra.Influencer one by one. Restoring UserProfile FK.
def copy_influencers():
    print('%s Copying Influencer (!)...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    users = Influencer.objects.using(
        SOURCE_DB_NAME
    ).filter(
        show_on_search=True
    ).exclude(
        blacklisted=True
    ).exclude(
        blog_url__contains='artificial_blog'
    )
    ctr = 0
    for obj in queryset_iterator(users):
        if obj.average_num_comments_per_post is None:
            obj.average_num_comments_per_post = 0.0
        obj.save(using=TARGET_DB_NAME)
        if obj.shelf_user:
            up = obj.shelf_user.userprofile
            up.influencer = obj
            up.save(using=TARGET_DB_NAME)

        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Influencer models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s Influencer objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# PART II: copying remaining tables
# Copying debra.Platform table in slices. Recommended offset: ???
def copy_platform_slices(start, end):
    print('%s Copying Platform objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    # TODO: Extra platform filter/exclude ?
    obj_ids = Platform.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True,
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = Platform.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Platform models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s Platform objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.Platform table in slices. Recommended offset: ???
def copy_posts_slices(start, end):
    print('%s Copying Posts objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    # TODO: show_on_search VS influencer__show_on_search ?
    obj_ids = Posts.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True,
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = Posts.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        if not Platform.objects.filter(id=obj.platform_id).exists():
            obj.platform.save(using=TARGET_DB_NAME)
            print('Saved extra platform: %s' % obj.platform.id)
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Posts models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s Posts objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.Posts table in slices. Recommended offset: ???
def copy_posts_slices2(start, end):
    print('%s Copying Posts objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    plat_ids = Platform.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True,
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]

    ctr = 0
    for obj_id in list(plat_ids):
        post_ids = Posts.objects.using(SOURCE_DB_NAME).filter(platform_id=obj_id).order_by('id').values_list('id', flat=True)
        posts = Posts.objects.using(SOURCE_DB_NAME).filter(id__in=post_ids)
        for p_obj in queryset_iterator(posts):
            try:
                # if not Platform.objects.filter(id=p_obj.platform_id).exists():
                #     p_obj.platform.save(using=TARGET_DB_NAME)
                #     print('Saved extra platform: %s' % p_obj.platform.id)
                p_obj.save(using=TARGET_DB_NAME)
                ctr += 1
            except IntegrityError:
                pass
            if ctr % 1000 == 0:
                print('%s Saved %s Posts models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
            if ctr % 1000000 == 0:
                print('garbage collecting')
                gc.collect()
    print('%s Copied %s Posts objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))



# Copying debra.Follower table in slices. Recommended offset: ???
def copy_follower_slices(start, end):
    print('%s Copying Follower objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = Follower.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True,
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = Follower.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Follower models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s Follower objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.PostInteractions table in slices. Recommended offset: ???
def copy_postinteractions_slices(start, end):
    print('%s Copying PostInteractions objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    # TODO: is it enough to filter only by platform? Or should we also filter by Posts and Follower?
    obj_ids = PostInteractions.objects.using(SOURCE_DB_NAME).filter(
        platform__influencer__show_on_search=True
    ).exclude(
        platform__influencer__blacklisted=True,
    ).exclude(
        platform__influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = PostInteractions.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s PostInteractions models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s PostInteractions objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_part2_01():
    """
    Copying a list of small tables:
        MandrillBatch  (No FKs) => 155K
        MandrillEvent   (FK: MandrillBatch) => 360K
        OpDict   (No FKs) => 125
        PlatformApiCalls   (No FKs) => 71K
         # OperationStatus  (NO Fks) => 2MIL
        Contract   (No FKs) => 5982
        CloudFrontDistribution   (No FKs) => 21
        SiteConfiguration  (No FKs) => 1
        FetcherApiDataSpec  (No FKs) => ~30
        FetcherApiDataValue  (FK: FetcherApiDataSpec)  => ~65
        FetcherApiDataAssignment   (FKs: FetcherApiDataSpec, FetcherApiDataValue) => ~165
        UserFollowMap   (FK: UserProfile) => 56453
        UserProfileBrandPrivilages   (FK: UserProfileBrandPrivilages, Brands) => 1023
        Shelf  (FK: Brands, User) => 196991
        BrandCampaign   (FK: Brands) => 0
        SearchQueryArchive   (FK: Brands, User) => 145641
        Color   (No FKs)  => 320

    :return:
    """
    # ~155K
    print('%s Copying MandrillBatch...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = MandrillBatch.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s MandrillBatch models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s MandrillBatch objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # ~360K
    print('%s Copying MandrillEvent...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = MandrillEvent.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s MandrillEvent models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s MandrillEvent objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # ~125
    print('%s Copying OpDict...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = OpDict.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s OpDict models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s OpDict objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # ~71K
    print('%s Copying PlatformApiCalls...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = PlatformApiCalls.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s PlatformApiCalls models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s PlatformApiCalls objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # # ~2MIL
    # print('%s Copying OperationStatus...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = OperationStatus.objects.using(SOURCE_DB_NAME).all()
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s OperationStatus models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s OperationStatus objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # ~5982
    print('%s Copying Contract models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = Contract.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Contract models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s Contract objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # ~21
    print('%s Copying CloudFrontDistribution models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = CloudFrontDistribution.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s CloudFrontDistribution models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s CloudFrontDistribution objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying SiteConfiguration models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # TODO: Do not see a table for it
    objects = SiteConfiguration.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s SiteConfiguration models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s SiteConfiguration objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying FetcherApiDataSpec models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = FetcherApiDataSpec.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s FetcherApiDataSpec models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s FetcherApiDataSpec objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying FetcherApiDataValue models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = FetcherApiDataValue.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s FetcherApiDataValue models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s FetcherApiDataValue objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying FetcherApiDataAssignment models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = FetcherApiDataAssignment.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s FetcherApiDataAssignment models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s FetcherApiDataAssignment objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying UserFollowMap models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = UserFollowMap.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s UserFollowMap models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s UserFollowMap objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying UserProfileBrandPrivilages models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = UserProfileBrandPrivilages.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s UserProfileBrandPrivilages models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s UserProfileBrandPrivilages objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying Shelf models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = Shelf.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Shelf models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s Shelf objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying BrandCampaign models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = BrandCampaign.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s BrandCampaign models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s BrandCampaign objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying SearchQueryArchive models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = SearchQueryArchive.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s SearchQueryArchive models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s SearchQueryArchive objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying Color models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = Color.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Color models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s Color objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_part2_02():
    """
        Filtering by influencers:

        InfluencerValidationQueue   (FK: Influencer) => 884
        SimilarWebVisits  (FKs: Influencer) => 233932
        SimilarWebVisitsReport  (FKs: Influencer) =>34837
        SimilarWebTrafficShares  (FKs: Influencer) => 113820
        MailProxy (FK: Influencer, Brands, User) => 15849
        MailProxyMessage   (FK: 'MailProxy') => 425516
    """

    # print('%s Copying InfluencerValidationQueue models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = InfluencerValidationQueue.objects.using(SOURCE_DB_NAME).filter(
    #     influencer__show_on_search=True
    # ).exclude(
    #     influencer__blacklisted=True
    # ).exclude(
    #     influencer__blog_url__contains='artificial_blog'
    # )
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s InfluencerValidationQueue models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s InfluencerValidationQueue objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # print('%s Copying SimilarWebVisits models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = SimilarWebVisits.objects.using(SOURCE_DB_NAME).filter(
    #     influencer__show_on_search=True
    # ).exclude(
    #     influencer__blacklisted=True
    # ).exclude(
    #     influencer__blog_url__contains='artificial_blog'
    # )
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s SimilarWebVisits models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s SimilarWebVisits objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # print('%s Copying SimilarWebVisitsReport models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = SimilarWebVisitsReport.objects.using(SOURCE_DB_NAME).filter(
    #     influencer__show_on_search=True
    # ).exclude(
    #     influencer__blacklisted=True
    # ).exclude(
    #     influencer__blog_url__contains='artificial_blog'
    # )
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s SimilarWebVisitsReport models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s SimilarWebVisitsReport objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # print('%s Copying SimilarWebTrafficShares models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = SimilarWebTrafficShares.objects.using(SOURCE_DB_NAME).filter(
    #     influencer__show_on_search=True
    # ).exclude(
    #     influencer__blacklisted=True
    # ).exclude(
    #     influencer__blog_url__contains='artificial_blog'
    # )
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s SimilarWebTrafficShares models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s SimilarWebTrafficShares objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    print('%s Copying MailProxy models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = MailProxy.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    )
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s MailProxy models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s MailProxy objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying MailProxyMessage models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = MailProxyMessage.objects.using(SOURCE_DB_NAME).filter(
        thread__influencer__show_on_search=True
    ).exclude(
        thread__influencer__blacklisted=True
    ).exclude(
        thread__influencer__blog_url__contains='artificial_blog'
    )
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s MailProxyMessage models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s MailProxyMessage objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_part2_03():
    """
        Filtering by influencers:

        InfluencersGroup   (FKs: Brands, UserProfile) => 1436
        InfluencerGroupMapping   (FKs: Influencer, InfluencerGroup, MailProxy) => 354049
        InfluencerBrandUserMapping   (FKs: Influencer, Brands, User) => 9809
        InfluencerAnalyticsCollection   (FKs: InfluencersGroup) => 369
        InfluencerAnalytics   (FKs: Influencer, InfluencerAnalyticsCollection) => 12876
        debra.PostAnalyticsCollection   (FKs: Brands, User, InfluencersGroup) => 891
        InfluencerCategoryMentions   (FK: Influencer) => 3687

        debra.BrandJobPost  (FK: Brands, User, InfluencersGroup, ROIPredictionReport, PostAnalyticsCollection, PostAnalyticsCollection)  => 461
        debra.ROIPredictionReport   (FKs: PostAnalyticsCollection, InfluencerAnalyticsCollection, Brands, User, BrandJobPost)  => 392

        InfluencerJobMapping   (FKs: InfluencerGroupMapping, BrandJobPost, MailProxy, Contract, InfluencerAnalytics) => 12133

        AlexaRankingInfo   (FK: Platform) => 23005
        AlexaMetricByCountry   (FK: AlexaRankingInfo) => 29890

        ContentTagCount  (FKs: Platform) => 97,277
        PlatformDataWarning   (FKs: Platform, Influencer) => 30958

        PostShelfMap   (FK: UserProfile, Shelf, Posts)   => 0
        InfluencerCustomerComment  (FKs: Influencer, Brands) => 53
        InfluencerCheck (FKs: Influencer, Platform) => 115025
        FeedCheck  (FKs: Platform) => 27076
        PostLengthCheck   (FKs: Influencer, Platform) => 40326

        PostAnalytics   (FKs: Brands, PostAnalyticsCollection, Contract) => 72506
        PostAnalyticsCollectionTimeSeries  (FKs: PostAnalyticsCollection) => 388
        EngagementTimeSeries   (FKs: Influencer, Platform) => 36
        PlatformFollower  (FK: Follower, Platform) => 38944
    """

    # print('%s Copying InfluencersGroup models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = InfluencersGroup.objects.using(SOURCE_DB_NAME).all()
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s InfluencersGroup models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s InfluencersGroup objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # print('%s Copying InfluencerGroupMapping models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = InfluencerGroupMapping.objects.using(SOURCE_DB_NAME).filter(
    #     influencer__show_on_search=True
    # ).exclude(
    #     influencer__blacklisted=True
    # ).exclude(
    #     influencer__blog_url__contains='artificial_blog'
    # )
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s InfluencerGroupMapping models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s InfluencerGroupMapping objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # print('%s Copying InfluencerBrandUserMapping models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = InfluencerBrandUserMapping.objects.using(SOURCE_DB_NAME).filter(
    #     influencer__show_on_search=True
    # ).exclude(
    #     influencer__blacklisted=True
    # ).exclude(
    #     influencer__blog_url__contains='artificial_blog'
    # )
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s InfluencerBrandUserMapping models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s InfluencerBrandUserMapping objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # print('%s Copying InfluencerAnalyticsCollection models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = InfluencerAnalyticsCollection.objects.using(SOURCE_DB_NAME).all()
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s InfluencerAnalyticsCollection models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s InfluencerAnalyticsCollection objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # print('%s Copying InfluencerAnalytics models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = InfluencerAnalytics.objects.using(SOURCE_DB_NAME).filter(
    #     influencer__show_on_search=True
    # ).exclude(
    #     influencer__blacklisted=True
    # ).exclude(
    #     influencer__blog_url__contains='artificial_blog'
    # )
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s InfluencerAnalytics models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s InfluencerAnalytics objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # print('%s Copying PostAnalyticsCollection models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = PostAnalyticsCollection.objects.using(SOURCE_DB_NAME).all()
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s PostAnalyticsCollection models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s PostAnalyticsCollection objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # print('%s Copying InfluencerCategoryMentions models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = InfluencerCategoryMentions.objects.using(SOURCE_DB_NAME).filter(
    #     influencer__show_on_search=True
    # ).exclude(
    #     influencer__blacklisted=True
    # ).exclude(
    #     influencer__blog_url__contains='artificial_blog'
    # )
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s InfluencerCategoryMentions models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s InfluencerCategoryMentions objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # print('%s Copying BrandJobPost (!)...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = BrandJobPost.objects.using(SOURCE_DB_NAME).all()
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.report = None
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s BrandJobPost models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s BrandJobPost objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # # copying table debra.ROIPredictionReport one by one. Restoring BrandJobPost FK report.
    # print('%s Copying ROIPredictionReport (!)...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # users = ROIPredictionReport.objects.using(
    #     SOURCE_DB_NAME
    # ).all()
    # ctr = 0
    # for obj in queryset_iterator(users):
    #     obj.save(using=TARGET_DB_NAME)
    #     if obj.main_campaign:
    #         bjp = BrandJobPost.objects.using(TARGET_DB_NAME).get(id=obj.main_campaign.id)
    #         bjp.report = obj
    #         bjp.save(using=TARGET_DB_NAME)
    #
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s Influencer models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s Influencer objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # # InfluencerJobMapping   (FKs: InfluencerGroupMapping, BrandJobPost, MailProxy, Contract, InfluencerAnalytics) => 12133
    # print('%s Copying InfluencerJobMapping models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = InfluencerJobMapping.objects.using(SOURCE_DB_NAME).all()
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     try:
    #         obj.save(using=TARGET_DB_NAME)
    #         ctr += 1
    #     except IntegrityError:
    #         pass
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s InfluencerJobMapping models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s InfluencerJobMapping objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # # AlexaRankingInfo   (FK: Platform) => 23005
    # print('%s Copying AlexaRankingInfo models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = AlexaRankingInfo.objects.using(SOURCE_DB_NAME).all()
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     try:
    #         obj.save(using=TARGET_DB_NAME)
    #     except IntegrityError:
    #         pass
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s AlexaRankingInfo models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s AlexaRankingInfo objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # # AlexaMetricByCountry   (FK: AlexaRankingInfo) => 29890
    # print('%s Copying AlexaMetricByCountry models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = AlexaMetricByCountry.objects.using(SOURCE_DB_NAME).all()
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     try:
    #         obj.save(using=TARGET_DB_NAME)
    #     except IntegrityError:
    #         pass
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s AlexaMetricByCountry models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s AlexaMetricByCountry objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # # ContentTagCount  (FKs: Platform) => 97,277
    # print('%s Copying ContentTagCount models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = ContentTagCount.objects.using(SOURCE_DB_NAME).filter(
    #     platform__influencer__show_on_search=True
    # ).exclude(
    #     platform__influencer__blacklisted=True
    # ).exclude(
    #     platform__influencer__blog_url__contains='artificial_blog'
    # )
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s ContentTagCount models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s ContentTagCount objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    #
    # # PlatformDataWarning   (FKs: Platform, Influencer) => 30958
    # print('%s Copying PlatformDataWarning models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    # objects = PlatformDataWarning.objects.using(SOURCE_DB_NAME).filter(
    #     influencer__show_on_search=True
    # ).exclude(
    #     influencer__blacklisted=True
    # ).exclude(
    #     influencer__blog_url__contains='artificial_blog'
    # )
    # ctr = 0
    # for obj in queryset_iterator(objects):
    #     obj.save(using=TARGET_DB_NAME)
    #     ctr += 1
    #     if ctr % 1000 == 0:
    #         print('%s Saved %s PlatformDataWarning models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    # print('%s Copied %s PlatformDataWarning objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # PostShelfMap   (FK: UserProfile, Shelf, Posts)   => 0
    print('%s Copying PostShelfMap models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = PostShelfMap.objects.using(SOURCE_DB_NAME).filter(
        post__influencer__show_on_search=True
    ).exclude(
        post__influencer__blacklisted=True
    ).exclude(
        post__influencer__blog_url__contains='artificial_blog'
    )
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s PostShelfMap models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s PostShelfMap objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # InfluencerCustomerComment  (FKs: Influencer, Brands) => 53
    print('%s Copying InfluencerCustomerComment models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = InfluencerCustomerComment.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    )
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s InfluencerCustomerComment models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s InfluencerCustomerComment objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # InfluencerCheck (FKs: Influencer, Platform) => 115025
    print('%s Copying InfluencerCheck models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = InfluencerCheck.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    )
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s InfluencerCheck models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s InfluencerCheck objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # FeedCheck  (FKs: Platform) => 27076
    print('%s Copying FeedCheck models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = FeedCheck.objects.using(SOURCE_DB_NAME).filter(
        platform__influencer__show_on_search=True
    ).exclude(
        platform__influencer__blacklisted=True
    ).exclude(
        platform__influencer__blog_url__contains='artificial_blog'
    )
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s FeedCheck models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s FeedCheck objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # PostLengthCheck   (FKs: Influencer, Platform) => 40326
    print('%s Copying PostLengthCheck models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = PostLengthCheck.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    )
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s PostLengthCheck models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s PostLengthCheck objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # PostAnalytics   (FKs: Brands, PostAnalyticsCollection, Contract) => 72506
    print('%s Copying PostAnalytics models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = PostAnalytics.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s PostAnalytics models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s PostAnalytics objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # PostAnalyticsCollectionTimeSeries  (FKs: PostAnalyticsCollection) => 388
    print('%s Copying PostAnalyticsCollectionTimeSeries models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = PostAnalyticsCollectionTimeSeries.objects.using(SOURCE_DB_NAME).all()
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s PostAnalyticsCollectionTimeSeries models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s PostAnalyticsCollectionTimeSeries objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # EngagementTimeSeries   (FKs: Influencer, Platform) => 36
    print('%s Copying EngagementTimeSeries models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = EngagementTimeSeries.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    )
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s EngagementTimeSeries models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s EngagementTimeSeries objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    # PlatformFollower  (FK: Follower, Platform) => 38944
    print('%s Copying PlatformFollower models...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    objects = PlatformFollower.objects.using(SOURCE_DB_NAME).filter(
        platform__influencer__show_on_search=True
    ).exclude(
        platform__influencer__blacklisted=True
    ).exclude(
        platform__influencer__blog_url__contains='artificial_blog'
    )
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s PlatformFollower models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s PlatformFollower objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.OperationStatus table in slices. Recommended offset: ???
def copy_operationstatus_slices(start, end):
    print('%s Copying OperationStatus objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = OperationStatus.objects.using(SOURCE_DB_NAME).all().order_by('id').values_list('id', flat=True)[start:end]
    objects = OperationStatus.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s OperationStatus models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s OperationStatus objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.BrandSavedCompetitors table in slices. Recommended offset: ???
def copy_brandsavedcompetitors_slices(start, end):
    print('%s Copying BrandSavedCompetitors objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = BrandSavedCompetitors.objects.using(SOURCE_DB_NAME).all().order_by('id').values_list('id', flat=True)[start:end]
    objects = BrandSavedCompetitors.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s BrandSavedCompetitors models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s BrandSavedCompetitors objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.BrandMentions table in slices. Recommended offset: ???
def copy_brandmentions_slices(start, end):
    print('%s Copying BrandMentions objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = BrandMentions.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = BrandMentions.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s BrandMentions models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s BrandMentions objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.PromoInfo table in slices. Recommended offset: ???
def copy_promoinfo_slices(start, end):
    print('%s Copying PromoInfo objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = Promoinfo.objects.using(SOURCE_DB_NAME).all().order_by('id').values_list('id', flat=True)[start:end]
    objects = Promoinfo.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s PromoInfo models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s PromoInfo objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.PopularityTimeSeries table in slices. Recommended offset: ???
def copy_popularitytimeseries_slices(start, end):
    print('%s Copying PopularityTimeSeries objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = PopularityTimeSeries.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = PopularityTimeSeries.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s PopularityTimeSeries models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s PopularityTimeSeries objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.FetcherTask table in slices. Recommended offset: ???
def copy_fetchertask_slices(start, end):
    print('%s Copying FetcherTask objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = FetcherTask.objects.using(SOURCE_DB_NAME).filter(
        platform__influencer__show_on_search=True
    ).exclude(
        platform__influencer__blacklisted=True
    ).exclude(
        platform__influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = FetcherTask.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s FetcherTask models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s FetcherTask objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.PostCategory (7,612,732) table in slices. Recommended offset: ???
def copy_postcategory_slices(start, end):
    print('%s Copying PostCategory objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = PostCategory.objects.using(SOURCE_DB_NAME).filter(
        posts__influencer__show_on_search=True
    ).exclude(
        posts__influencer__blacklisted=True
    ).exclude(
        posts__influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = PostCategory.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s PostCategory models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s PostCategory objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

# Copying debra.LinkFromPlatform (1.6 Mil) table in slices. Recommended offset: ???
def copy_linkfromplatform_slices(start, end):
    print('%s Copying LinkFromPlatform objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = LinkFromPlatform.objects.using(SOURCE_DB_NAME).filter(
        platform__influencer__show_on_search=True
    ).exclude(
        platform__influencer__blacklisted=True
    ).exclude(
        platform__influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = LinkFromPlatform.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s LinkFromPlatform models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s LinkFromPlatform objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.LinkFromPost (18MIL) table in slices. Recommended offset: ???
def copy_linkfrompost_slices(start, end):
    print('%s Copying LinkFromPost objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = LinkFromPost.objects.using(SOURCE_DB_NAME).filter(
        posts__influencer__show_on_search=True
    ).exclude(
        posts__influencer__blacklisted=True
    ).exclude(
        posts__influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = LinkFromPost.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s LinkFromPost models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s LinkFromPost objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.SponsorshipInfo (0.5 MIL) table in slices. Recommended offset: ???
def copy_sponsorshipinfo_slices(start, end):
    print('%s Copying SponsorshipInfo objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = SponsorshipInfo.objects.using(SOURCE_DB_NAME).filter(
        posts__influencer__show_on_search=True
    ).exclude(
        posts__influencer__blacklisted=True
    ).exclude(
        posts__influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = SponsorshipInfo.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s SponsorshipInfo models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s SponsorshipInfo objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.ContentTag (6.5 MIL)  table in slices. Recommended offset: ???
def copy_contenttag_slices(start, end):
    print('%s Copying ContentTag objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = ContentTag.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = ContentTag.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s ContentTag models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s ContentTag objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.BrandInPost (40.7 MIL) table in slices. Recommended offset: ???
def copy_brandinpost_slices(start, end):
    print('%s Copying BrandInPost  objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = BrandInPost.objects.using(SOURCE_DB_NAME).filter(
        posts__influencer__show_on_search=True
    ).exclude(
        posts__influencer__blacklisted=True
    ).exclude(
        posts__influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = BrandInPost.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s BrandInPost models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s BrandInPost objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.MentionInPost (30.5 MIL)  table in slices. Recommended offset: ???
def copy_mentioninpost_slices(start, end):
    print('%s Copying MentionInPost objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = MentionInPost.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = MentionInPost.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s MentionInPost models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s MentionInPost objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# Copying debra.BrandInPost (158 MIL) table in slices. Recommended offset: ???
def copy_hashtaginpost_slices(start, end):
    print('%s Copying HashtagInPost objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = HashtagInPost.objects.using(SOURCE_DB_NAME).filter(
        posts__influencer__show_on_search=True
    ).exclude(
        posts__influencer__blacklisted=True
    ).exclude(
        posts__influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = HashtagInPost.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s HashtagInPost models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s HashtagInPost objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


# PART III: Separate copying of ProductModelShelfMap and dependent tables
# ProductModel   (FK: Brands)  => ~26.7 MIL
# ColorSizeModel   (FK: ProductModel, Color) => 28,334,214
# ProductPrice    (FK: ColorSizeModel)  => 165,747,243
#
# ProductsInPosts   (FK: Posts, ProductModel, ) => 0
# ProductModelShelfMap  (FK: UserProfile, Shelf, Posts, ProductModel, ProductPrice, Promoinfo, Influencer, ProductModelShelfMap (self!)) => 30,446,478

# TODO: How it is better to save required dependent tables here?

def copy_productmodel_slices(start, end):
    print('%s Copying ProductModel objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = ProductModel.objects.using(SOURCE_DB_NAME).filter(
        productmodelshelfmap__influencer__show_on_search=True
    ).exclude(
        productmodelshelfmap__influencer__blacklisted=True
    ).exclude(
        productmodelshelfmap__influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = ProductModel.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s ProductModel models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s ProductModel objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_colorsizemodel_slices(start, end):
    print('%s Copying ColorSizeModel objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = ProductModel.objects.using(TARGET_DB_NAME).all().order_by('id').values_list('id', flat=True)[start:end]
    objects = ColorSizeModel.objects.using(SOURCE_DB_NAME).filter(product_id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s ColorSizeModel models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s ColorSizeModel objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_productprice_slices(start, end):
    print('%s Copying ProductPrice objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = ColorSizeModel.objects.using(TARGET_DB_NAME).all().order_by('id').values_list('id', flat=True)[start:end]
    objects = ProductPrice.objects.using(SOURCE_DB_NAME).filter(product_id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s ProductPrice models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s ProductPrice objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_productsinposts_slices(start, end):
    print('%s Copying ProductModel objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = ProductsInPosts.objects.using(SOURCE_DB_NAME).filter(
        post__influencer__show_on_search=True
    ).exclude(
        post__influencer__blacklisted=True
    ).exclude(
        post__influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = ProductModel.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s ProductModel models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s ProductModel objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_productmodelshelfmap_slices(start, end):
    print('%s Copying ProductModelShelfMap objects...' % datetime.datetime.now().strftime("[%H:%M:%S]"))

    obj_ids = ProductModelShelfMap.objects.using(SOURCE_DB_NAME).filter(
        influencer__show_on_search=True
    ).exclude(
        influencer__blacklisted=True
    ).exclude(
        influencer__blog_url__contains='artificial_blog'
    ).order_by('id').values_list('id', flat=True)[start:end]
    objects = ProductModelShelfMap.objects.using(SOURCE_DB_NAME).filter(id__in=obj_ids)
    ctr = 0
    for obj in queryset_iterator(objects):
        obj.save(using=TARGET_DB_NAME)
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s ProductModelShelfMap models [%s:%s]' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr, start, end))
    print('%s Copied %s ProductModelShelfMap objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
