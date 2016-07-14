from debra.models import *
from social_discovery.blog_discovery import queryset_iterator
from xps import models as xps_models
import datetime


# def delete_PlatformDataOp(chunk_size=50000):
#
#     print('Cleaning debra.PlatformDataOp')
#     total = 0
#     while 1:
#         ids = list(PlatformDataOp.objects.all().values_list('id', flat=True)[:chunk_size])
#         PlatformDataOp.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('debra.PlatformDataOp data deleted: %s / total: %s' % (len(ids), total))
#     print('debra.PlatformDataOp all data deleted: %s' % total)
#
#
# def delete_PdoLatest(chunk_size=50000):
#
#     print('Cleaning debra.PdoLatest')
#     total = 0
#     while 1:
#         ids = list(PdoLatest.objects.all().values_list('id', flat=True)[:chunk_size])
#         PdoLatest.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('debra.PdoLatest data deleted: %s / total: %s' % (len(ids), total))
#     print('debra.PdoLatest all data deleted: %s' % total)
#
#
# def delete_CorrectValue(chunk_size=50000):
#
#     print('Cleaning xps_models.CorrectValue')
#     total = 0
#     while 1:
#         ids = list(xps_models.CorrectValue.objects.all().values_list('id', flat=True)[:chunk_size])
#         xps_models.CorrectValue.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('xps_models.CorrectValue data deleted: %s / total: %s' % (len(ids), total))
#     print('xps_models.CorrectValue all data deleted: %s' % total)
#
#
# def delete_FoundValue(chunk_size=50000):
#
#     print('Cleaning xps_models.FoundValue')
#     total = 0
#     while 1:
#         ids = list(xps_models.FoundValue.objects.all().values_list('id', flat=True)[:chunk_size])
#         xps_models.FoundValue.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('xps_models.FoundValue data deleted: %s / total: %s' % (len(ids), total))
#     print('xps_models.FoundValue all data deleted: %s' % total)
#
#
# def delete_ScrapingResult(chunk_size=50000):
#
#     print('Cleaning xps_models.ScrapingResult')
#     total = 0
#     while 1:
#         ids = list(xps_models.ScrapingResult.objects.all().values_list('id', flat=True)[:chunk_size])
#         xps_models.ScrapingResult.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('xps_models.ScrapingResult data deleted: %s / total: %s' % (len(ids), total))
#     print('xps_models.ScrapingResult all data deleted: %s' % total)
#
#
# def delete_ScrapingResultSet(chunk_size=50000):
#
#     print('Cleaning xps_models.ScrapingResultSet')
#     total = 0
#     while 1:
#         ids = list(xps_models.ScrapingResultSet.objects.all().values_list('id', flat=True)[:chunk_size])
#         xps_models.ScrapingResultSet.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('xps_models.ScrapingResultSet data deleted: %s / total: %s' % (len(ids), total))
#     print('xps_models.ScrapingResultSet all data deleted: %s' % total)
#
#
# def delete_ScrapingResultSetEntry(chunk_size=50000):
#
#     print('Cleaning xps_models.ScrapingResultSetEntry')
#     total = 0
#     while 1:
#         ids = list(xps_models.ScrapingResultSetEntry.objects.all().values_list('id', flat=True)[:chunk_size])
#         xps_models.ScrapingResultSetEntry.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('xps_models.ScrapingResultSetEntry data deleted: %s / total: %s' % (len(ids), total))
#     print('xps_models.ScrapingResultSetEntry all data deleted: %s' % total)
#
#
# def delete_ScrapingResultSize(chunk_size=50000):
#
#     print('Cleaning xps_models.ScrapingResultSize')
#     total = 0
#     while 1:
#         ids = list(xps_models.ScrapingResultSize.objects.all().values_list('id', flat=True)[:chunk_size])
#         xps_models.ScrapingResultSize.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('xps_models.ScrapingResultSize data deleted: %s / total: %s' % (len(ids), total))
#     print('xps_models.SScrapingResultSize all data deleted: %s' % total)
#
#
# def delete_XPathExpr(chunk_size=50000):
#
#     print('Cleaning xps_models.XpathExpr')
#     total = 0
#     while 1:
#         ids = list(xps_models.XPathExpr.objects.all().values_list('id', flat=True)[:chunk_size])
#         xps_models.XPathExpr.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('xps_models.XpathExpr data deleted: %s / total: %s' % (len(ids), total))
#     print('xps_models.XpathExpr all data deleted: %s' % total)
#
#
# def delete_Influencer(chunk_size=500):
#
#     print('Cleaning debra_models.Influencer')
#     total = 0
#     while 1:
#         ids = list(Influencer.objects.exclude(show_on_search=True).values_list('id', flat=True)[:chunk_size])
#         Influencer.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('debra_models.Influencer data deleted: %s / total: %s' % (len(ids), total))
#     print('debra_models.Influencer all data deleted: %s' % total)
#
#
# def delete_Posts(chunk_size=50000):
#
#     print('Cleaning debra_models.Posts')
#     total = 0
#     while 1:
#         ids = list(Posts.objects.exclude(show_on_search=True).values_list('id', flat=True)[:chunk_size])
#         Posts.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('debra_models.Posts data deleted: %s / total: %s' % (len(ids), total))
#     print('debra_models.Posts all data deleted: %s' % total)
#
#
# def delete_Platforms(chunk_size=50000):
#
#     print('Cleaning debra_models.Platforms')
#     total = 0
#     while 1:
#         ids = list(Platform.objects.exclude(influencer__show_on_search=True).values_list('id', flat=True)[:chunk_size])
#         Platform.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('debra_models.Platforms data deleted: %s / total: %s' % (len(ids), total))
#     print('debra_models.Platforms all data deleted: %s' % total)
#
#
# def delete_PostInteractions(chunk_size=50000):
#
#     print('Cleaning debra_models.PostInteractions')
#     total = 0
#     while 1:
#         ids = list(PostInteractions.objects.exclude(post__show_on_search=True).values_list('id', flat=True)[:chunk_size])
#         PostInteractions.objects.filter(id__in=ids).delete()
#
#         if len(ids) < chunk_size:
#             break
#         total += len(ids)
#
#         print('debra_models.PostInteractions data deleted: %s / total: %s' % (len(ids), total))
#     print('debra_models.PostInteractions all data deleted: %s' % total)


def copy_users_slices(start, end):
    print('%s Copying users...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    user_ids = User.objects.using('default').all().order_by('id').values_list('id', flat=True)[start:end]
    users = User.objects.filter(id__in=user_ids)
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using='production')
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s User models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s users.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    

def copy_brand_slices(start, end):
    print('%s Copying Brands...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    user_ids = Brands.objects.using('default').all().order_by('id').values_list('id', flat=True)[start:end]
    users = Brands.objects.filter(id__in=user_ids)
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using='production')
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Brands models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s Brands objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_user_profiles_slicks(start, end):
    print('%s Copying UserProfile (!)...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    user_ids = UserProfile.objects.using('default').all().order_by('id').values_list('id', flat=True)[start:end]
    users = UserProfile.objects.filter(id__in=user_ids)
    ctr = 0
    for obj in queryset_iterator(users):
        obj.influencer = None
        obj.save(using='production')
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s UserProfile models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s UserProfile objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_part_1():
    """
    Part I of copying data:

        django.contrib.auth.models.User  (Django's users table)
        debra.DemographicsLocality  (Has no FKs, is a "reference" ? Should be copied with ALL its data?)
        debra.BrandCategory  (Has no FKs, is a "reference" ? Should be copied with ALL its data?)
        debra.Category    (Has no FKs, is a "reference" ? Should be copied with ALL its data?)
        debra.Brands (Has ManyToMany: debra.BrandCategory, debra.Brands     is a "reference" ? Should be copied with ALL its data?)
        debra.UserProfile  (Has OneToOne to: django.contrib.auth.models.User, debra.Brands, FK to: debra.Influencer)
        debra.Influencer  (Has FK to: django.contrib.auth.models.User, debra.DemographicsLocality, debra.UserProfile)

    :return:
    """



    print('%s Copying DemographicsLocality...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    users = DemographicsLocality.objects.using('default').all()
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using='production')
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s DemographicsLocality models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s DemographicsLocality objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying BrandCategory...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    users = BrandCategory.objects.using('default').all()
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using='production')
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s BrandCategory models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s BrandCategory objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))

    print('%s Copying Category...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    users = Category.objects.using('default').all()
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using='production')
        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Category models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s Category objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_influencers():
    print('%s Copying Influencer (!)...' % datetime.datetime.now().strftime("[%H:%M:%S]"))
    users = Influencer.objects.using('default').filter(show_on_search=True).exclude(blacklisted=True).exclude(blog_url__contains='artificial_blog')
    ctr = 0
    for obj in queryset_iterator(users):
        obj.save(using='production')
        if obj.shelf_user:
            up = obj.shelf_user.userprofile
            up.influencer = obj.id
            up.save(using='production')

        ctr += 1
        if ctr % 1000 == 0:
            print('%s Saved %s Influencer models' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))
    print('%s Copied %s Influencer objects.' % (datetime.datetime.now().strftime("[%H:%M:%S]"), ctr))


def copy_part_2():
    pass
