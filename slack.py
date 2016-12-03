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
from enum import Enum

from slackclient import SlackClient

from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream,RestartException
from zmachine.text import ZTextException
from zmachine.memory import BitArray,MemoryException
from zmachine.instructions import InstructionException

def load_zmachine(filename,restart_flags=None):
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
    WAITING_TO_QUIT          = 1
    PROMPT_FOR_SAVE          = 2
    PROMPT_FOR_RESTORE       = 3

class Terp(object):
    def __init__(self,zmachine,story_filename):
        self.state = RunState.RUNNING
        self.zmachine = zmachine
        self.story_filename = story_filename

    def run(self):
        if self.state != RunState.RUNNING:
            self.state = RunState.RUNNING

    def start_save(self):
    	pass

    def handle_save(self,save_name):
    	pass

    def start_restore(self):
    	pass

    def handle_restore(self,save_name):
    	pass

    def wait_for_quit(self):
    	pass

    def idle(self,input_stream):
        """ Called if no key is pressed """
        if self.state == RunState.RUNNING:            
            self.zmachine.step()

class SlackOutputStream(object):
	def __init__(self,slack_connection):
		self.slack_connection = slack_connection
		self.buffer =''
		self.channel=None

	def refresh(self):
		""" Redraw this screen """
		pass

	def flush(self):
		if self.buffer and self.channel:
			self.slack_connection.api_call('chat.postMessage',channel=self.channel,text=self.buffer)
			self.buffer=''

	def new_line(self):
		self.buffer += '\n'
        
	def print_str(self,txt):
		self.buffer += txt

	def print_char(self,txt):
		self.buffer += txt

	def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
		pass

class MainLoop(object):
	def run(self,sc,player_id,zmachine,story_filename):
		print("Starting terp for player %s" % player_id)

		output_stream = SlackOutputStream(sc)
		zmachine.output_streams.set_screen_stream(output_stream)

		terp = Terp(zmachine,story_filename)
		terp.run()

		if not sc.rtm_connect():
			print("Unable to connect")
		else:
			while True:
				if zmachine.state == Interpreter.WAITING_FOR_LINE_STATE:
					output_stream.flush()
					messages = sc.rtm_read()
					for message in messages:
						if message.get('type') == 'message' and message.get('user') == player_id:
							print(message)
							sc.api_call('chat.postMessage',channel=message['channel'],text='You said: %s' %  message['text'])

						time.sleep(1)
				else:
					terp.idle(None)
			else:
				print("Connection Failed, invalid token?")

def main():
	if sys.version_info[0] < 3:
		raise Exception("Moosezmachine requires Python 3.")

	parser = argparse.ArgumentParser()
	parser.add_argument('story',help='Story file to play')
	parser.add_argument('--player_id',help='Slack ID of player',required=True)
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

	# Load up our zmachine from the story file
	zmachine = load_zmachine(data.story)
	story_path, story_filename = os.path.split(data.story)

	raise Exception('Need channel as well. Eventually add in "connect to username" shortcut')

	# Start the slack-based interpreter
	MainLoop().run(sc, data.player_id, zmachine,story_filename)


if __name__ == "__main__":
    main()
