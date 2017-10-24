import hashlib
import os
import random
import time

from django.db import models
from django.conf import settings

from zmachine.interpreter import Story, Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream,RestartException
from zmachine.text import ZTextException
from zmachine.memory import BitArray,MemoryException
from zmachine.instructions import InstructionException

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
        except StoryRecord.DoesNotExist:
            pass

        story = StoryRecord.objects.create(title=title,
                    story_hash=story_hash,
                    data=story_data,
                    added_by=get_default_user())

        return story,True

class StoryRecord(models.Model):
    """ Metadata for a story, including the story file data itself """
    title = models.CharField(max_length=100)
    story_hash = models.CharField(max_length=64,unique=True)
    data = models.BinaryField() # Contains raw story data
    added_by = models.ForeignKey(settings.AUTH_USER_MODEL)
    added_when = models.DateTimeField(auto_now_add=True)

    objects = StoryManager()

    def get_or_start_session(self,user):
        """ Get the existing session for this story/user, or create a new one """
        session,created = StorySession.objects.get_or_create(story=self,
                user=user,
                defaults={'rng_seed':random.randint(1,5000)})
        return session

    def __str__(self):
        return self.title
    
class StorySession(models.Model):
    """ A running session of a story for a given user """
    story = models.ForeignKey(StoryRecord)
    user = models.ForeignKey(settings.AUTH_USER_MODEL)

    # Store our random seed for this session
    rng_seed = models.PositiveIntegerField()

    def get_current_state(self):
        """ Return the most recent StoryState for this session. Creates StoryState
            and starts if none exists
        """
        try:
           return StoryState.objects.filter(session=self).order_by('-move')[0]
        except IndexError:
           pass
            
        state = StoryState(session=self,
                move=1,
                branch_parent=None,
                state=b'',
                command='',
                text='',
                score='',
                room_name='')

        state.generate_next_state(command=None)

        return state
            
    def __str__(self):
        return '%s/%s' % (self.story, self.user)

class StubInputStream(object):
    """ Input stream just used to track when we're waiting for a line """
    def __init__(self,output_stream=None,add_newline=True):
        self.waiting_for_line = False

    def readline(self):
        return None

    def char_pressed(self,char):
        pass

class BufferOutputStream(OutputStream):
    def __init__(self):
        super(BufferOutputStream,self).__init__()
        self.buffer = ''
        self.room_name = ''
        self.score = ''

    def refresh(self):
        pass

    def new_line(self):
        self.buffer += '\n'
        
    def print_str(self,txt):
        self.buffer += txt

    def print_char(self,txt):
        self.buffer += txt

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        self.room_name = room_name
        if score_mode:
            right_string = 'Score: %s Moves: %s' % (score or 0,turns or 0)
        else:
            right_string = '%02d:%02d' % (hours,minutes)

        self.score = right_string

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
    room_name = models.CharField(max_length=100) # Contents of location part of status bar

    def generate_next_state(self,command=None):
        """ Starting from this state and with the given command, create a new StoryState object
            after running the zmachine """
        story = Story(self.session.story.data)
        outputs = OutputStreams(OutputStream(),OutputStream())
        inputs = InputStreams(InputStream(),InputStream())
        zmachine = Interpreter(story,outputs,inputs,None,None)
        zmachine.reset(restart_flags=None)
        zmachine.story.header.set_debug_mode()
        zmachine.story.rng.enter_predictable_mode(self.session.rng_seed)
        
        output_stream = BufferOutputStream()
        input_stream =  StubInputStream(story)
        zmachine.output_streams.set_screen_stream(output_stream)
        zmachine.input_streams.keyboard_stream = input_stream
        zmachine.input_streams.select_stream(InputStreams.KEYBOARD)
    
        start_time = time.time()
        while True and start_time + 2 >= time.time(): # If execution goes more than 2 seconds, cancel.
            zmachine.step()
            if input_stream.waiting_for_line:
                break
        
        state = StoryState.objects.create(session=self.session,
            move=self.move+1,
            branch_parent=self.branch_parent,
            state=self.state,
            command=command or '',
            text=output_stream.buffer,
            score=output_stream.score,
            room_name=output_stream.room_name)

        return state

    def __str__(self):
        return '%s/%s/%s' % (self.move, self.score, self.location)
