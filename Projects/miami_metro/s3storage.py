from django.contrib.staticfiles.storage import CachedFilesMixin
from pipeline.storage import PipelineMixin
from storages.backends.s3boto import S3BotoStorage

from django.conf import settings

class S3PipelineStorage(PipelineMixin, CachedFilesMixin, S3BotoStorage):
    pass

class StaticPipelineStorage(PipelineMixin, CachedFilesMixin, S3BotoStorage):
    location = settings.STATICFILES_LOCATION

    def hashed_name(self, name, content=None):
        try:
            out = super(StaticPipelineStorage, self).hashed_name(name, content)
        except ValueError:
            # This means that a file could not be found, and normally this would
            # cause a fatal error, which seems rather excessive given that
            # some packages have missing files in their css all the time.
            out = name
        return out

class StaticStorage(S3BotoStorage):
    location = settings.STATICFILES_LOCATION

class MediaStorage(S3BotoStorage):
    location = settings.MEDIAFILES_LOCATION

# # Define bucket and folder for static files.
# StaticStorage = lambda: S3PipelineStorage(
#     bucket=settings.AWS_STORAGE_BUCKET_NAME,
#     location="https://s3.amazonaws.com/"
# )
