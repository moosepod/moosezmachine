import sys
import re
import os
import logging
import argparse
import time
import datetime
import json

from enum import Enum

from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream,RestartException
from zmachine.text import ZTextException
from zmachine.memory import BitArray,MemoryException
from zmachine.instructions import InstructionException

from pygame_terp import PygameWrapper,PygameOutputStream,PygameInputStream
from generic_terp import STDOUTOutputStream,ConfigException,FileStreamEmptyException

SETTINGS = {'dimensions': (640,480),
            'char_dimensions': (80,40),
            'font_name': 'courier',
            'font_size': 12}

# How many zcode steps we take before checking for keypress
INPUT_BREAK_FREQUENCY=1000

class RunState(Enum):
    RUNNING                  = 0
    WAITING_TO_QUIT          = 1
    PROMPT_FOR_SAVE          = 2
    PROMPT_FOR_RESTORE       = 3

class Terp(object):
    def __init__(self,zmachine,story_filename,tracer=None):
        self.state = RunState.RUNNING
        self.zmachine = zmachine
        self.story_filename = story_filename
        self.tracer = tracer

    def run(self):
        if self.state != RunState.RUNNING:
            self.state = RunState.RUNNING

    def start_save(self):
        self.state = RunState.PROMPT_FOR_SAVE
        stream = self.zmachine.output_streams.get_screen_stream()
        self.zmachine.output_streams.get_screen_stream().print_str('Name of file for save (in %s)? ' % 
                                            self.zmachine.save_handler.save_path)
        stream.flush()
        self.zmachine.input_streams.active_stream.readline()

    def handle_save(self,save_name):
        stream = self.zmachine.output_streams.get_screen_stream()
        message = self.zmachine.save_handler.save_to(save_name,self.zmachine)
        stream.print_str(message)
        stream.new_line()
        stream.flush()

        self.run()

    def start_restore(self):
        self.state = RunState.PROMPT_FOR_RESTORE
        self.zmachine.output_streams.get_screen_stream().print_str('Name of file for restore (in %s)? ' % 
                                self.zmachine.save_handler.save_path)
        self.zmachine.output_streams.get_screen_stream().flush()
        self.zmachine.input_streams.active_stream.readline()

    def handle_restore(self,save_name):
        stream = self.zmachine.output_streams.get_screen_stream()
        message = self.zmachine.restore_handler.restore_from(save_name,self.zmachine)
        stream.print_str(message)
        stream.new_line()
        stream.flush()

        self.run()

    def wait_for_quit(self):
        self.state = RunState.WAITING_TO_QUIT
        self.zmachine.output_streams.get_screen_stream().print_str('\n[HIT ESC AGAIN TO QUIT]')
        self.zmachine.output_streams.get_screen_stream().flush()


    def idle(self,input_stream):
        """ Called if no key is pressed """
        if self.state == RunState.RUNNING:            
            self.zmachine.step()

            if self.tracer:
                self.tracer.log_instruction(self.zmachine.last_instruction)

    def key_pressed(self,ch,input_stream,output_streams):
        if self.state in (RunState.RUNNING,RunState.PROMPT_FOR_SAVE,RunState.PROMPT_FOR_RESTORE):
            if input_stream.waiting_for_line:
                input_stream.char_pressed('%s' % chr(ch))

                # If the end result of the press is the end of the input line,
                # start recording, using the entered line as the command
                if input_stream.line_done:
                    if self.state == RunState.PROMPT_FOR_SAVE:
                        self.handle_save(input_stream.text)
                        input_stream.reset()
                    elif self.state == RunState.PROMPT_FOR_RESTORE:
                        self.handle_restore(input_stream.text)
                        input_stream.reset()
                    else:
                        output_streams.command_entered(input_stream.text)
                        output_streams.flush()
                        if self.tracer:
                            self.tracer.start_command(input_stream.text)

        elif self.state == RunState.WAITING_TO_QUIT:
            self.run()

class MainLoop(object):
    def __init__(self,zmachine,raw=False,commands_path=None,story_filename=None,tracer=None,seed=None,transcript_path=None,save_path=None):
        self.zmachine = zmachine
        self.curses_input_stream = None
        self.raw = raw
        self.commands_path = commands_path
        self.tracer = tracer
        self.seed=seed
        self.transcript_path=transcript_path
        self.save_path = save_path
        self.story_filename = story_filename

    def loop(self):
        pygame_wrapper=PygameWrapper(SETTINGS)

        if self.seed != None:
            self.zmachine.story.rng.enter_predictable_mode(int(self.seed))

        if self.raw:
            output_stream = STDOUTOutputStream()
        else:
            output_stream = PygameOutputStream(pygame_wrapper)

        self.zmachine.output_streams.set_screen_stream(output_stream)
        self.output_stream=output_stream

        if self.transcript_path:
            if not self.transcript_path.endswith('.transcript'):
                raise ConfigException('All transcripts must end with the .transcript extension')
            if os.path.isdir(self.transcript_path):
                raise ConfigException('Transcript path must be to a file that ends in .transcript')

            transcript_stream = FileOutputStream(self.transcript_path)
            self.zmachine.output_streams.set_transcript_stream(transcript_stream)
            transcript_stream.print_str('--- Game started at %s ----\n\n' % datetime.datetime.now())
            transcript_stream.flush()

            # Create a command transcript as well
            transcript_stream = FileOutputStream(self.transcript_path + '.commands')
            self.zmachine.output_streams.set_commands_stream(transcript_stream)
            transcript_stream.print_str('--- Game started at %s ----\n\n' % datetime.datetime.now())
            transcript_stream.flush()

        self.zmachine.input_streams.keyboard_stream = PygameInputStream()
        self.zmachine.input_streams.select_stream(InputStreams.KEYBOARD)

        # If provided with a command file, load it as the file stream and select it by default
        if self.commands_path:
            input_stream = FileInputStream(output_stream)
            input_stream.load_from_path(self.commands_path)
            self.zmachine.input_streams.command_file_stream =input_stream
            self.zmachine.input_streams.select_stream(InputStreams.FILE)

        terp = Terp(self.zmachine,self.story_filename,tracer=self.tracer)
        terp.run()
        self.terp = terp

        #if self.save_path:
        #    self.zmachine.save_handler = TerpSaveHandler(terp,self.save_path)
        #    self.zmachine.restore_handler = TerpRestoreHandler(terp,self.save_path)

        counter = 0
        timer = 0
        while pygame_wrapper.tick(waiting_for_text=self.zmachine.input_streams.active_stream.waiting_for_line):
            input_stream = self.zmachine.input_streams.active_stream
            try:
                if terp.state == RunState.RUNNING:
                    terp.idle(input_stream)
               
            except (QuitException,RestartException) as e:
                self.zmachine.output_streams.flush()
                raise e
            except FileStreamEmptyException:
                self.zmachine.input_streams.select_stream(InputStreams.KEYBOARD)
            except Exception as e:
                raise Exception('Unhandled exception "%s" at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction),e)

        # If pygame returns False, treat as a quit
        raise QuitException()

def load_zmachine(filename,restart_flags=None):
    with open(filename,'rb') as f:
        story = Story(f.read())
        outputs = OutputStreams(OutputStream(),OutputStream())
        inputs = InputStreams(InputStream(),InputStream())
        zmachine = Interpreter(story,outputs,inputs,None,None)
        zmachine.reset(restart_flags=restart_flags)
        zmachine.story.header.set_debug_mode()

    return zmachine

def start(path,commands_path,trace_file_path=None,seed=None,restart_flags=None,transcript_path=None,save_path=None):
    tracer = None
    if trace_file_path:
        tracer = Tracer()

    zmachine = load_zmachine(path,restart_flags)
    story_path, story_filename = os.path.split(path)        
    loop = MainLoop(zmachine,
        story_filename=story_filename,
        commands_path=commands_path,
        tracer=tracer,
        seed=seed,
        transcript_path=transcript_path,
        save_path=save_path)

    loop.loop()
   
def main(*args):
    if sys.version_info[0] < 3:
        raise Exception("Moosezmachine requires Python 3.")

    parser = argparse.ArgumentParser()
    parser.add_argument('story',help='Story file to play')
    parser.add_argument('--raw',help='Output to with no curses',required=False,action='store_true')
    parser.add_argument('--commands_path',help='Path to optional command file',required=False)
    parser.add_argument('--save_path',help='Path to directory for saves. Will default to /tmp',required=False,default='/tmp')
    parser.add_argument('--transcript_path',help='Path for transcript. This will also activate transcript by default. A separate commands transcript will also automatically be created.',required=False)
    parser.add_argument('--seed',help='Optional seed for RNG',required=False)
    parser.add_argument('--trace_file',help='Path to file to which the terp will dump all instructions on exit',required=False)
    data = parser.parse_args()

    try:
        restart_flags = None # Per spec, when restarting, preserve bit 0 and bit 1 of flag 2 in header 
        while True:
            try:
                start(data.story,
                    commands_path=data.commands_path,
                    trace_file_path=data.trace_file,
                    seed=data.seed,
                    transcript_path=data.transcript_path,
                    save_path=data.save_path,
                    restart_flags=restart_flags)    
            except RestartException as e:
                restart_flags = e.restart_flags
    except QuitException:

        print("Thanks for playing!")
    except ConfigException as e:
        print(e)

if __name__ == "__main__":
    main()
