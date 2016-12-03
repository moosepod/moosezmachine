# PHASE 1: single threaded, bind to a a single user.

# Connect to slack web api
# If disconnected, reconnect
# Create lockfile that is cleared on exit. This is used so we can auto-start
# Start main loop

# Need state machine to manage everything?
# Pull next item from queue. Ignore everything but message
# Spin off async handlers for each message

import os
import sys
import time
import argparse

from slackclient import SlackClient

class SlackTerp(object):
	def run(self,sc,player_id):
		print("Starting terp for player %s" % player_id)
		if sc.rtm_connect():
			while True:
				messages = sc.rtm_read()
				for message in messages:
					if message.get('type') == 'message' and message.get('user') == player_id:
						print(message)
						sc.api_call('chat.postMessage',channel=message['channel'],text='You said: %s' %  message['text'])
					time.sleep(1)
			else:
				print("Connection Failed, invalid token?")

def main():
	if sys.version_info[0] < 3:
		raise Exception("Moosezmachine requires Python 3.")

	parser = argparse.ArgumentParser()
	parser.add_argument('--player_id',help='Slack ID of player',required=True)
	data = parser.parse_args()

	SLACK_BOT_TOKEN = os.environ.get("SLACK_BOT_TOKEN")
	if not SLACK_BOT_TOKEN:
		print('SLACK_BOT_TOKEN must be set as an environment variable.')
		return
	
	sc = SlackClient(SLACK_BOT_TOKEN)
	result = sc.api_call('api.test')
	if not result.get('ok'):
		print('Connection to slack failed. Qutting.')
		return

	SlackTerp().run(sc, data.player_id)


if __name__ == "__main__":
    main()
