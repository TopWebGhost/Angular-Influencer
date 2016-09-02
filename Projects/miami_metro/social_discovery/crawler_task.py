from celery.decorators import task
import logging

from pydoc import locate

log = logging.getLogger('social_discovery.crawler_draft')

# Celery Task Helper Functions

KLASS_METHOD = {
    'pipeline': 'pipeline',
    'create_profiles': 'create_new_profiles',
    'perform_post': 'create_profile',
}


@task(name="social_discovery.crawler_draft.crawler_task", ignore_result=True)
def crawler_task(klass_name=None, task_type=None, **kwargs):
    """
    This is a helper universal task to call methods of corresponding classes, for example

    crawler_task(klass_name='CreatorByInstagramHashtags',
        task_type='create_new_profiles',
        hashtags={'singapore': ['oo7d', 'koreanfashion', ]},
        num_pages_to_load=1)

    :param klass_name: name of class of an object to invoke a method, for example, 'CreatorByInstagramHashtags'
    :param task_type: type of the task, for example 'process_hashtag' or 'process_feed', 'process_post'
    :param kwargs: additional arguments
    :return:
    """
    log.info('crawler_task(klass_name=%s, task_type=%s, kwargs=%s) called...' % (klass_name, task_type, kwargs))

    klass_method = KLASS_METHOD.get(task_type, task_type)

    if klass_name is None or task_type is None or klass_method is None:
        log.error('klass_name, task_type or klass_method is None')
        return

    try:
        # Before getting a class we import it from creators, classifiers, processors, upgraders
        klass = None

        for module in ['social_discovery.creators', 'social_discovery.processors',
                       'social_discovery.classifiers', 'social_discovery.upgraders']:
            # try:
            #     # Here we import module dynamically and try to import the class
            #     imported_module = __import__(module, fromlist=[klass_name])
            #     klass = getattr(imported_module, klass_name)
            #     log.info('-----GETTING KLASS:')
            #     log.info(klass)
            #     break
            # except AttributeError:
            #     pass

            klass = locate('%s.%s' % (module, klass_name))
            if klass is not None:
                break

        # # creating an 'objekt' of the class
        objekt = klass()

        # calling the required function with appropriate params
        getattr(klass, klass_method)(objekt, **kwargs)

    except KeyError:
        # log.error('Class %s not found' % klass_name)
        log.exception('Class %s not found' % klass_name)
    except AttributeError:
        # log.error('Method %s of class %s not found' % (klass_method, klass_name))
        log.exception('Method %s of class %s not found. Was called with params: crawler_task(klass_name=%s, task_type=%s, kwargs=%s)' % (klass_method, klass_name, klass_name, task_type, kwargs))
