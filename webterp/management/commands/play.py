""" Play the story with the given UUID in a curses-based environment """

import sys
from enum import Enum

import logging
import curses
import curses.ascii
from curses import wrapper

import argparse
import time

from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream
from zmachine.text import ZTextException
from zmachine.memory import BitArray,MemoryException
from zmachine.instructions import InstructionException

from curses_terp import CursesInputStream,CursesOutputStream,FileTranscriptStream

from django.core.management.base import BaseCommand, CommandError

import webterp.models

STATUS_BAR_HEIGHT = 1
STORY_TOP_MARGIN = 1
STORY_BOTTOM_MARGIN = 1 

class RunState(Enum):
    RUNNING                  = 0
    WAITING_TO_QUIT          = 1

class ResetException(Exception):
    pass

class Terp(object):
    def __init__(self,zmachine,window):
        self.state = RunState.RUNNING
        self.zmachine = zmachine
        self.window = window

    def run(self):
        if self.state != RunState.RUNNING:
            self.state = RunState.RUNNING

    def wait_for_quit(self):
    	self.state = RunState.WAITING_TO_QUIT
    	self.window.addstr('[HIT ESC AGAIN TO QUIT]')

    def idle(self):
        """ Called if no key is pressed """
        if self.state == RunState.RUNNING:
            self.zmachine.step()

    def key_pressed(self,ch,curses_input_stream):
        if self.state == RunState.RUNNING:
            if ch == curses.ascii.ESC:
                self.wait_for_quit()
            else:
	            if curses_input_stream.waiting_for_line:
	                curses_input_stream.char_pressed('%s' % chr(ch))
        elif self.state == RunState.WAITING_TO_QUIT:
            if ch == curses.ascii.ESC:
	            raise QuitException('User forced quit with escape')
            else:
	            self.run()

class MainLoop(object):
    def __init__(self,zmachine):
        self.zmachine = zmachine
        self.curses_input_stream = None

    def loop(self,screen):
        # Disable automatic echo
        curses.noecho()
        
        # Use unbufferd input
        curses.cbreak()

        # THe main screen
        screen_height,screen_width = screen.getmaxyx()
        if screen_width < 120:
            print('Terminal must be at least 120 characters wide')
            return
        if screen_height < 20:
            print('Terminal must be at least 20 characters in height')
            return     

        # The status bar
        status = curses.newwin(STATUS_BAR_HEIGHT,screen_width,0,0)
        status.addstr(0,0,"",curses.A_REVERSE)
        status.refresh()

        # The story window
        story = curses.newwin(screen_height-(STORY_TOP_MARGIN+STORY_BOTTOM_MARGIN+STATUS_BAR_HEIGHT),
                              screen_width,
                              STATUS_BAR_HEIGHT+STORY_TOP_MARGIN,
                              0)
        story.timeout(1)
        story.refresh()
        curses_output_stream = CursesOutputStream(story,status)
        self.zmachine.output_streams.set_screen_stream(curses_output_stream)

        self.curses_input_stream = CursesInputStream(story)
        self.zmachine.input_streams.keyboard_stream = self.curses_input_stream
        self.zmachine.input_streams.select_stream(0)

        terp = Terp(self.zmachine,story)
        terp.run()

        while True:
            try:
                ch = story.getch()
                if ch == curses.ERR:
                    terp.idle()
                else:
                    terp.key_pressed(ch,self.curses_input_stream)
                story.refresh()
            except Exception as e:
                raise Exception('Unhandled exception "%s" at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction),e)



class Command(BaseCommand):
	def add_arguments(self, parser):
		parser.add_argument('--uuid')

	def handle(self, *args, **options):
		uuid = options.get('uuid')

		if not uuid:
			print('Stories')
			print('------')
			for obj in webterp.models.Story.objects.all():
				print('%s: python3 manage.py play --uuid %s' % (obj.title,obj.id))
			return

		try:
			obj = webterp.models.Story.objects.get(id=uuid)
		except webterp.models.DoesNotExist:
			print("Could not find that story.")
			return

		while True:
			try:
				start(obj,)    
			except ResetException:
				print("Resetting...")
				time.sleep(1)
			except QuitException:
				print("Thanks for playing!")

def start(obj):
	zmachine = obj.get_zmachine()
	loop = MainLoop(zmachine)
	wrapper(loop.loop)

