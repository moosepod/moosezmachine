# PHASE 1: single threaded, bind to a a single user.

# Connect to slack web api
# If disconnected, reconnect
# Create lockfile that is cleared on exit. This is used so we can auto-start
# Start main loop

# Need state machine to manage everything?
# Pull next item from queue. Ignore everything but message
# Spin off async handlers for each message

#
# NOTE - on bash subsystem for windows current build, need to comment out lines 37 and 38
# of websocket/_socket.py or it won't work. Socket option is TCP_KEEPCNT 
#

# - Assume entirely in memory
# - Build RTM API output stream
# - Build RTM API input stream
# - Stub out save

import os
import sys
import time
import argparse
import json
from enum import Enum

from slackclient import SlackClient

from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream,RestartException
from zmachine.text import ZTextException
from zmachine.memory import BitArray,MemoryException
from zmachine.instructions import InstructionException

# Tune this number to control frequently you want to check the real time feed for updates. Too high
# and the feed will be overwhelemed.
RTM_FEED_POLL_SLEEP_IN_S=0.5

def load_zmachine(filename,restart_flags=None):
    """ Initialize a zmachine interpreter from tne story file and return it"""
    with open(filename,'rb') as f:
        story = Story(f.read())
        outputs = OutputStreams(OutputStream(),OutputStream())
        inputs = InputStreams(InputStream(),InputStream())
        zmachine = Interpreter(story,outputs,inputs,None,None)
        zmachine.reset(restart_flags=restart_flags)
        zmachine.story.header.set_debug_mode()

    return zmachine

class RunState(Enum):
    RUNNING                  = 0
    PROMPT_FOR_SAVE          = 1
    PROMPT_FOR_RESTORE       = 2

class Terp(object):
    def __init__(self,zmachine,story_filename):
        self.state = RunState.RUNNING
        self.zmachine = zmachine
        self.story_filename = story_filename

    def run(self):
        if self.state != RunState.RUNNING:
            self.state = RunState.RUNNING

    def quicksave(self,save_path,player_id,zmachine):
        filename = '{}.quicksave'.format(player_id)
        message = self.zmachine.save_handler.save_to(filename,self.zmachine,quicksave=True)
        print('quicksave',message)

    def quickrestore(self, save_path, player_id, zmachine):
        filename = '{}.quicksave'.format(player_id)
        message = self.zmachine.restore_handler.restore_from(filename,self.zmachine,quicksave=True)
        print('quickrestore',message)
        if 'Restored from' in message:
            return True
        return False
            
    def start_save(self):
        self.state = RunState.PROMPT_FOR_SAVE
        stream = self.zmachine.output_streams.get_screen_stream()
        self.zmachine.output_streams.get_screen_stream().print_str('Name of file for save? ')
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
        self.zmachine.output_streams.get_screen_stream().print_str('Name of file for restore? ')
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
        pass

    def idle(self,input_stream):
        """ Called if no key is pressed """
        if self.state == RunState.RUNNING:            
            self.zmachine.step()

class SlackInputStream(object):
    """ Input stream for handling commands passed in through slack """
    def __init__(self,slack_connection,player_id,channel_id):
        self.slack_connection=slack_connection
        self.waiting_for_line = False
        self.player_id = player_id
        self.channel_id = channel_id
        self.command_queue = []

    def readline(self):
        command = None

        if not self.command_queue:
            messages = self.slack_connection.rtm_read()
            for message in messages:
                if message.get('type') == 'message' and message.get('user') == self.player_id:
                    print('Received from {}: {}'.format(self.player_id,message))
                    self.command_queue.append(message['text'])

        if self.command_queue:
            command = self.command_queue[0]
            del self.command_queue[0]
            self.waiting_for_line=False
            self.slack_connection.api_call('chat.postMessage',channel=self.channel_id,text='_Processing..._')

        return command

    def char_pressed(self,char):
        pass

    def reset(self):
        self.waiting_for_line = False 
        self.command_queue=[]       

class SlackOutputStream(object):
    def __init__(self,slack_connection,channel_id):
        self.slack_connection = slack_connection
        self.buffer =''
        self.channel_id=channel_id

    def refresh(self):
        """ Redraw this screen """
        pass

    def _post_message(self,msg):
        self.slack_connection.api_call('chat.postMessage',channel=self.channel_id,text=msg)
        print('Posted: %s' % msg)

    def flush(self):
        if self.buffer:
            self._post_message(self.buffer)
            self.buffer=''

    def new_line(self):
        self.buffer += '\n'
        
    def print_str(self,txt):
        self.buffer += txt

    def print_char(self,txt):
        self.buffer += txt

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        status = '`{room_name}`\n`Score: {score} Turns: {turns}`'.format(room_name=room_name,
            score=score,
            turns=turns)
        self.slack_connection.api_call('chat.postMessage',channel=self.channel_id,text=status)

class SaveRestoreMixin(object):
    def fix_filename(self, filename,user_id):
        """ Take a provided filename, strip any unwanted characters, then prefix with our story file name """
        return u'%s_%s_%s.sav' % (user_id,self.terp.story_filename,
            ''.join([c for c in filename if c.isalpha() or c.isdigit() or c==' ' or c=='_']))

class TerpSaveHandler(SaveRestoreMixin):
    def __init__(self, terp,save_path,player_id):
        self.terp=terp
        self.error_action = None
        self.success_action = None
        self.save_path = save_path
        self.player_id = player_id
        # Set to true when a save was just completed. We want to skip
        # autosave in this case. Not set in case of autosave
        self.just_saved = False 

    def save_to(self, filename, interpreter,quicksave=False):
        original_filename = filename
        filename = self.fix_filename(filename,self.player_id)

        try:
            if self.success_action:
                self.success_action.apply(interpreter)
            with open(os.path.join(self.save_path,filename),'w') as f:
                f.write(json.dumps(interpreter.to_save_data()))
            message = '\nSaved to %s' % original_filename
        except Exception as e:
            message = '\nError saving. %s' % (e,)
            if self.error_action:
                self.error_action.apply(interpreter)
        if not quicksave:
            self.just_saved = True

        return message

    def handle_save(self,success_action,error_action):
        self.terp.start_save()
        self.success_action = success_action
        self.error_action = error_action


class TerpRestoreHandler(SaveRestoreMixin):
    def __init__(self, terp,save_path,player_id):
        self.terp=terp
        self.error_action = None
        self.success_action = None
        self.save_path = save_path
        self.player_id = player_id
        # Set to true when a restore was just completed. We want to skip
        # autosave in this case
        self.just_restored = False 

    def restore_from(self, filename, interpreter,quicksave=False):
        original_filename = filename
        filename = self.fix_filename(filename,self.player_id)

        try:
            with open(os.path.join(self.save_path,filename),'r') as f:
                interpreter.restore_from_save_data(f.read())
            message = '\nRestored from %s' % original_filename
        except Exception as e:
            message = '\nError restoring. %s' % (e,)
            if self.error_action:
                self.error_action.apply(interpreter)
        self.just_restored=True
        return message

    def handle_restore(self,error_action):
        self.terp.start_restore()
        self.error_action = error_action

class MainLoop(object):
    def run(self,sc,player_id,channel_id,zmachine,story_filename,save_path,quickrestore=False):
        print("Starting terp for player %s" % player_id)

        output_stream = SlackOutputStream(sc,channel_id)
        zmachine.output_streams.set_screen_stream(output_stream)

        input_stream = SlackInputStream(sc, player_id, channel_id)
        zmachine.input_streams.keyboard_stream=input_stream
        zmachine.input_streams.select_stream(InputStreams.KEYBOARD)

        terp = Terp(zmachine,story_filename)
        terp.run()

        zmachine.save_handler = TerpSaveHandler(terp,save_path,player_id)
        zmachine.restore_handler = TerpRestoreHandler(terp,save_path,player_id)

        print('Connecting')
        if not sc.rtm_connect():
            print("Unable to connect")
        else:
            print("Starting loop")
            output_stream._post_message('_Initializing interpreter..._')

            if quickrestore and terp.quickrestore(save_path, player_id, zmachine):
                zmachine.show_status()
                terp.state = RunState.RUNNING
                zmachine.state = Interpreter.WAITING_FOR_LINE_STATE

            while True:
                if terp.state == RunState.RUNNING:
                    was_running = zmachine.state == Interpreter.RUNNING_STATE

                    terp.idle(None)
                    if not was_running:
                    	# If terp is currently waiting for a line, pause between idle calls. 
                    	#This prevents us from overpolling the real time feed
                    	time.sleep(RTM_FEED_POLL_SLEEP_IN_S)

                    if was_running and zmachine.state != Interpreter.RUNNING_STATE:
                        # If the term has just switched to waiting for line (sread hit)
                        # output our buffer
                        zmachine.output_streams.flush()
                        if zmachine.save_handler.just_saved or zmachine.restore_handler.just_restored:
                            # skip quicksave and reset
                            zmachine.save_handler.just_saved=False
                            zmachine.restore_handler.just_restored=False
                            print('Skipping save')
                        else:
                            terp.quicksave(save_path, player_id,zmachine)
                elif terp.state == RunState.PROMPT_FOR_SAVE:
                    line = input_stream.readline()
                    if line:
                        terp.handle_save(line)
                        input_stream.reset()
                elif terp.state == RunState.PROMPT_FOR_RESTORE:
                    line = input_stream.readline()
                    if line:
                        terp.handle_restore(line)
                        input_stream.reset()
            else:
                print("Connection Failed, invalid token?")

def main():
    if sys.version_info[0] < 3:
        raise Exception("Moosezmachine requires Python 3.")

    parser = argparse.ArgumentParser()
    parser.add_argument('story',help='Story file to play')
    parser.add_argument('--player_id',help='Slack ID of player',required=True)
    parser.add_argument('--channel_id',help='Channel ID of im bot with player',required=True)
    parser.add_argument('--save_path',help='Path to save directory',required=True)
    data = parser.parse_args()

    SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
    if not SLACK_BOT_TOKEN:
        print('SLACK_BOT_TOKEN must be set as an environment variable.')
        return
    
    # Check slack connection
    sc = SlackClient(SLACK_BOT_TOKEN)
    result = sc.api_call('api.test')
    if not result.get('ok'):
        print('Connection to slack failed. Qutting.')
        return
    print('Test connection succeeded.')

    # Start the slack-based interpreter
    quickrestore=True
    while True:
        # Load up our zmachine from the story file
        print('Loading story')
        zmachine = load_zmachine(data.story)
        story_path, story_filename = os.path.split(data.story)

        try:
            MainLoop().run(sc, data.player_id, data.channel_id, zmachine,story_filename,data.save_path,quickrestore)
        except (QuitException,RestartException):
            quickrestore=False



if __name__ == "__main__":
    main()
