import hashlib
import os

from django.db import models
from django.conf import settings

def get_default_user():
    from django.contrib.auth.models import User
    user,created = User.objects.get_or_create(username=settings.DEFAULT_USER_USERNAME)
    return user

class StoryManager(models.Manager):
    def get_or_create_from_path(self, path, title):
        """ Given a path to a story file, hash it, create new story 
            if does not exist, return existing if it does """
        head, filename = os.path.split(path)

        with open(path,'rb') as f:
            story_data = f.read()
        
        tmp_hash =hashlib.sha256()
        tmp_hash.update(story_data)
        story_hash = tmp_hash.hexdigest()
        try:
            story = self.get(story_hash=story_hash)
            return story, False
        except Story.DoesNotExist:
            pass

        story = Story.objects.create(title=title,
                    story_hash=story_hash,
                    data=story_data,
                    added_by=get_default_user())

        return story,True

class Story(models.Model):
    """ Metadata for a story, including the story file data itself """
    title = models.CharField(max_length=100)
    story_hash = models.CharField(max_length=64,unique=True)
    data = models.BinaryField() # Contains raw story data
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    added_when = models.DateTimeField(auto_now_add=True)

    objects = StoryManager()

    def __str__(self):
        return self.title
    
class StorySession(models.Model):
    """ A running session of a story for a given user """
    story = models.ForeignKey(Story)
    user = models.ForeignKey(settings.AUTH_USER_MODEL)

    # Store our random seed for this session
    rng_seed = models.PositiveIntegerField()

    def __str__(self):
        return '%s/%s' % (self.story, self.user)

class StoryState(models.Model):
    """ A specific state in the timeline for a given story session """
    session = models.ForeignKey(StorySession)
    move = models.PositiveIntegerField() # Move number

    # When we branch, we store the state we branched from. State data all immutable
    branch_parent = models.ForeignKey('StoryState', null=True,blank=True)

    state = models.BinaryField() # Saved state at start of this move
    command = models.CharField(max_length=1000) # Command that led to this state
    text = models.TextField() # Text output by this command

    score = models.CharField(max_length=100) # Contents of score part of status bar
    location = models.CharField(max_length=100) # Contents of location part of status bar

    def __str__(self):
        return '%s/%s/%s' % (self.move, self.score, self.location)
