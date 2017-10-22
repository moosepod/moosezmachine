from django.db import models
from django.conf import settings

class Story(models.Model):
    """ Data for a story """
    title = models.CharField(max_length=100)
    data = models.BinaryField() # Contains raw story data
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    added_when = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.title
    
class StorySession(models.Model):
    """ A running session of a story for a given user """
    story = models.ForeignKey(Story)
    user = models.ForeignKey(settings.AUTH_USER_MODEL)

    def __str__(self):
        return '%s/%s' % (self.story, self.user)

class StoryState(models.Model):
    """ A specific state in the timeline for a given story session """
    session = models.ForeignKey(StorySession)
    state = models.BinaryField() # Saved state at start of this move
    command = models.CharField(max_length=1000) # Command that led to this state
    move = models.PositiveIntegerField() # Move number
    score = models.CharField(max_length=100) # Contents of score part of status bar
    location = models.CharField(max_length=100) # Contents of location part of status bar

    def __str__(self):
        return '%s/%s/%s' % (self.move, self.score, self.location)
