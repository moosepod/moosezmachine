import uuid

from django.db import models
from django.conf import settings

class Story(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	title = models.CharField(max_length=100)
	story_data = models.TextField()
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL)
	created_when = models.DateTimeField(auto_now_add=True)

	def str(self):
		return '%s (%s)' % (self.title,self.uuid)

	class Meta:
		verbose_name_plural = "stories"

