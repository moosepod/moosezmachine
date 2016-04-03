import uuid

from django.db import models
from django.conf import settings
from zmachine import interpreter


class Story(models.Model):
	id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
	title = models.CharField(max_length=100)
	story_data = models.BinaryField()
	created_by = models.ForeignKey(settings.AUTH_USER_MODEL)
	created_when = models.DateTimeField(auto_now_add=True)

	def get_zmachine(self):
		terp_story = interpreter.Story(self.story_data)
		outputs = interpreter.OutputStreams(interpreter.OutputStream(),interpreter.OutputStream())
		inputs = interpreter.InputStreams(interpreter.InputStream(),interpreter.InputStream())
		zmachine = interpreter.Interpreter(terp_story,outputs,inputs,None,None)
		zmachine.reset()
		return zmachine

	def __str__(self):
		return '%s (%s)' % (self.title,self.uuid)

	class Meta:
		verbose_name_plural = "stories"

class StoryInstance(models.Model):
	story = models.ForeignKey(Story)
	user = models.ForeignKey(settings.AUTH_USER_MODEL)
	game_data = models.BinaryField()

	def __str__(self):
		return '%s (%s)' % (self.story,self.user)

	class Meta:
		unique_together = (('story','user'))
