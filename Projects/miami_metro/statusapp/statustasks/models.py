from django.db import models


class TaskResult(models.Model):
    task = models.TextField(db_index=True)
    result = models.TextField()
    desc_json = models.TextField(null=True)
    executed = models.DateTimeField(auto_now_add=True)
    
    def __unicode__(self):
        return u'task={self.task}, result={self.result}, desc_json={self.desc_json}, executed={self.executed}'.format(self=self)

