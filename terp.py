""" Curses-based interpreter. Usage: python terp.py filename """

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

from curses_terp import CursesInputStream,CursesOutputStream,FileTranscriptStream,STDOUTOutputStream,\
                        FileInputStream

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
    def __init__(self,zmachine,raw,commands):
        self.zmachine = zmachine
        self.curses_input_stream = None
        self.raw = raw
        self.commands = commands

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
        if self.raw:
            output_stream = STDOUTOutputStream(story,status)
        else:
            output_stream = CursesOutputStream(story,status)

        self.zmachine.output_streams.set_screen_stream(output_stream)

        if self.commands:
            self.curses_input_stream = FileInputStream(output_stream)
            self.curses_input_stream.load_from_path(self.commands)
        else:
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
            except QuitException as e:
                raise e
            except Exception as e:
                raise Exception('Unhandled exception "%s" at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction),e)


def load_zmachine(filename):
    with open(filename,'rb') as f:
        story = Story(f.read())
        outputs = OutputStreams(OutputStream(),OutputStream())
        inputs = InputStreams(InputStream(),InputStream())
        zmachine = Interpreter(story,outputs,inputs,None,None)
        zmachine.reset()
        zmachine.story.header.set_debug_mode()

    return zmachine

def main(*args):
    if sys.version_info[0] < 3:
        raise Exception("Moosezmachine requires Python 3.")

    parser = argparse.ArgumentParser()
    parser.add_argument('story',help='Story file to play')
    parser.add_argument('--raw',help='Output to with no curses',required=False,action='store_true')
    parser.add_argument('--commands',help='Path to optional command file',required=False)
    data = parser.parse_args()

    try:
        while True:
            try:
                start(data.story,raw=data.raw,commands=data.commands)    
            except ResetException:
                print("Resetting...")
                time.sleep(1)
    except QuitException:
        print("Thanks for playing!")

def start(filename,raw,commands):
    zmachine = load_zmachine(filename)
    loop = MainLoop(zmachine,raw=raw,commands=commands)
    wrapper(loop.loop)

if __name__ == "__main__":
    main()
