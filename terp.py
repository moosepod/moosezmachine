""" Curses-based interpreter. Usage: python terp.py filename """

import sys
import re
import os
import logging
import curses
import curses.ascii
import argparse
import time
import datetime
import json

from enum import Enum
from curses import wrapper

from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream,RestartException
from zmachine.text import ZTextException
from zmachine.memory import BitArray,MemoryException
from zmachine.instructions import InstructionException

from curses_terp import CursesInputStream,CursesOutputStream,STDOUTOutputStream,\
                        FileInputStream,FileStreamEmptyException,FileOutputStream

STATUS_BAR_HEIGHT = 1
STORY_TOP_MARGIN = 1
STORY_BOTTOM_MARGIN = 1 

# How many zcode steps we take before checking for keypress
INPUT_BREAK_FREQUENCY=1000

class RunState(Enum):
    RUNNING                  = 0
    WAITING_TO_QUIT          = 1
    PROMPT_FOR_SAVE          = 2
    PROMPT_FOR_RESTORE       = 3

class ConfigException(Exception):
    pass

class Tracer(object):
    """ Handles logging instructions during a playthrough """
    def __init__(self):
        self.commands = [] # Used when telemetry is on to time each command
        self.start_command('START')
        self.recording=True

    def end_command(self):
        if self.commands:
            self.commands[-1]['end_time'] = time.clock()
        self.recording=False

    def start_command(self,command):
        self.recording=True
        self.commands.append({'command': command, 'instructions': [], 'start_time': time.clock()})

    def log_instruction(self,instruction):
        if self.recording:
            # Bit of a hack here -- but as soon as we see an sread command, stop recording. Sread indicates
            # waiting for command
            if instruction.startswith('varOP:sread'):
                self.end_command()

            self.commands[-1]['instructions'].append(instruction)

    def save_to_path(self,output_path):
        instruction_rx = re.compile('^\w+:(\S+) ')
        with open(output_path,'w') as f:
           for record in self.commands:
                instruction_count = len(record['instructions'])
                total_time = time.clock() - record['start_time']
                f.write('---- %s (%d instuctions,%d ms, %.2f instructions/ms) -----\n' % (record['command'],
                                instruction_count,
                                total_time*1000,
                                1000*(total_time/max(instruction_count,1))))
                instruction_freq = {}
                for instruction in record['instructions']:
                    f.write(instruction)
                    f.write('\n')
                    m = instruction_rx.search(instruction)
                    if m:
                        t = m.group(1)
                        if not instruction_freq.get(t):
                            instruction_freq[t] = 0
                        instruction_freq[t]+=1
                f.write('Instruction frequency:\n')
                for k,v in instruction_freq.items():
                    f.write('{0: <6} {1}\n'.format(v,k))

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
            if ch == curses.ascii.ESC:
                self.wait_for_quit()
            else:
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
            if ch == curses.ascii.ESC:
	            raise QuitException('User forced quit with escape')
            else:
	            self.run()

class SaveRestoreMixin(object):
    def fix_filename(self, filename):
        """ Take a provided filename, strip any unwanted characters, then prefix with our story file name """
        return u'%s_%s.sav' % (self.terp.story_filename,
            ''.join([c for c in filename if c.isalpha() or c.isdigit() or c==' ' or c=='_']))

class TerpSaveHandler(SaveRestoreMixin):
    def __init__(self, terp,save_path):
        self.terp=terp
        self.error_action = None
        self.success_action = None
        self.save_path = save_path

    def save_to(self, filename, interpreter):
        filename = self.fix_filename(filename)

        try:
            self.success_action.apply(interpreter)
            with open(os.path.join(self.save_path,filename),'w') as f:
                f.write(json.dumps(interpreter.to_save_data()))
            message = '\nSaved to %s' % filename
        except Exception as e:
            message = '\nError saving. %s' % (e,)
            self.error_action.apply(self.interpreter)

        return message

    def handle_save(self,success_action,error_action):
        self.terp.start_save()
        self.success_action = success_action
        self.error_action = error_action


class TerpRestoreHandler(SaveRestoreMixin):
    def __init__(self, terp,save_path):
        self.terp=terp
        self.error_action = None
        self.success_action = None
        self.save_path = save_path

    def restore_from(self, filename, interpreter):
        filename = self.fix_filename(filename)

        try:
            with open(os.path.join(self.save_path,filename),'r') as f:
                interpreter.restore_from_save_data(f.read())
            message = '\nRestored from %s' % filename
        except Exception as e:
            message = '\nError restoring. %s' % (e,)
            self.error_action.apply(interpreter)
        return message

    def handle_restore(self,error_action):
        self.terp.start_restore()
        self.error_action = error_action

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

        if self.seed != None:
            self.zmachine.story.rng.enter_predictable_mode(int(self.seed))

        if self.raw:
            output_stream = STDOUTOutputStream(story,status)
        else:
            output_stream = CursesOutputStream(story,status)

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

        self.zmachine.input_streams.keyboard_stream = CursesInputStream(story)
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

        if self.save_path:
            self.zmachine.save_handler = TerpSaveHandler(terp,self.save_path)
            self.zmachine.restore_handler = TerpRestoreHandler(terp,self.save_path)


        counter = 0
        timer = 0
        while True:
            input_stream = self.zmachine.input_streams.active_stream
            try:
                # Check for keypress on defined interval or when we're waiting for a line in the terp
                if counter == INPUT_BREAK_FREQUENCY or input_stream.waiting_for_line:
                    ch = story.getch()
                    counter = 0
                else:
                    counter+=1
                    ch = curses.ERR

                was_waiting_for_line = input_stream.waiting_for_line
                if ch == curses.ERR:
                    if terp.state == RunState.RUNNING:
                        terp.idle(input_stream)
                else:
                    terp.key_pressed(ch,input_stream,self.zmachine.output_streams)

                if input_stream.waiting_for_line and not was_waiting_for_line:
                    # If the term has just switched to waiting for line (sread hit)
                    # output our buffer
                    self.zmachine.output_streams.flush()

                story.refresh()
            except (QuitException,RestartException) as e:
                self.zmachine.output_streams.flush()
                raise e
            except FileStreamEmptyException:
                self.zmachine.input_streams.select_stream(InputStreams.KEYBOARD)
            except Exception as e:
                raise Exception('Unhandled exception "%s" at PC 0x%04x [%s]' % (e,self.zmachine.pc,self.zmachine.last_instruction),e)

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

    try:
        wrapper(loop.loop)
    finally:
        if tracer:
            tracer.save_to_path(trace_file_path)
            print('Instructions logged to %s' % trace_file_path)

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
