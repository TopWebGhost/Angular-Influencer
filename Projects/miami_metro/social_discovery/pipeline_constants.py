# QUEUES for Pipeline modules categories
CREATORS_QUEUE_NAME = 'profiles_pipeline_creators'
CLASSIFIERS_QUEUE_NAME = 'profiles_pipeline_classifiers'
PROCESSORS_QUEUE_NAME = 'profiles_pipeline_processors'
UPGRADERS_QUEUE_NAME = 'profiles_pipeline_upgraders'
CONNECT_PROFILES_QUEUE_NAME = 'profiles_pipeline_connect_to_influencers'

# Queues for that youtube-link in profiles tasks.
YOUTUBE_CREATORS_QUEUE_NAME = 'profiles_pipeline_creators_youtube'
YOUTUBE_CLASSIFIERS_QUEUE_NAME = 'profiles_pipeline_classifiers_youtube'
YOUTUBE_PROCESSORS_QUEUE_NAME = 'profiles_pipeline_processors_youtube'
YOUTUBE_UPGRADERS_QUEUE_NAME = 'profiles_pipeline_upgraders_youtube'
YOUTUBE_PIPELINE_QUEUE_NAME = 'social_profiles_pipeline_youtube'

QUEUE_TO_REFETCH_PROFILES = 'social_profiles_refetch_queue'

# name of queue for pipelines' tasks (obsolete?)
PIPELINE_QUEUE_NAME = 'social_profiles_pipeline'

# for different types of reprocess logic
REPROCESS_PROFILES_QUEUE_NAME = 'reprocess_profiles'

# This is a value of minimum friends count of profile. Profiles with lesser friends will be skipped automatically.
# Default value is 1000
MINIMUM_FRIENDS_COUNT = 1000


def get_queue_name_by_pipeline_step(klassname=None):
    """
    returns queue name for particular step of pipeline (simply according to naming)
    :param klassname: name of pipeline's step
    :return: name of queue to put task in
    """
    if isinstance(klassname, str):
        klassname = klassname.lower()
        if 'haveyoutube' in klassname.lower():
            if 'creator' in klassname:
                return YOUTUBE_CREATORS_QUEUE_NAME
            elif 'classifier' in klassname:
                return YOUTUBE_CLASSIFIERS_QUEUE_NAME
            elif 'processor' in klassname:
                return YOUTUBE_PROCESSORS_QUEUE_NAME
            elif 'upgrader' in klassname:
                return YOUTUBE_UPGRADERS_QUEUE_NAME
            else:
                return YOUTUBE_PIPELINE_QUEUE_NAME

        if 'creator' in klassname:
            return CREATORS_QUEUE_NAME
        elif 'classifier' in klassname:
            return CLASSIFIERS_QUEUE_NAME
        elif 'processor' in klassname:
            return PROCESSORS_QUEUE_NAME
        elif 'upgrader' in klassname:
            return UPGRADERS_QUEUE_NAME
        else:
            return PIPELINE_QUEUE_NAME
    return None
