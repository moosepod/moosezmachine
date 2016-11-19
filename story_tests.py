""" Pass in a path to a directory containing story files, command lists, and transcripts, and this 
    script will feed the commands into the running stories and compare with transcript.

    Looks for files ending in z3 . Then looks for files with the same filename and ending in .out and
    .commands

    For all cases where all three files exist, start up a terp using the story file, and run until end,
    feeding in commands from commands file. Then compare output with .out file.
"""

import argparse
import os
import sys
import difflib

from io import StringIO

from zmachine.interpreter import QuitException
from terp import Terp,load_zmachine
from curses_terp import StringIOOutputStream

def test_story(story_path,out_path,commands_path):
    print("Starting test of %s" % story_path)
    story_stream = StringIO()
    zmachine = load_zmachine(story_path)
    zmachine.output_streams.set_screen_stream(StringIOOutputStream(story_stream))

    terp = Terp(zmachine,None)
    terp.run()

    while True:
        try:
            terp.idle()
        except QuitException:
            break
    
    print('Done. Comparing results')
    expected_results = open(out_path,'r').read()
    results = story_stream.getvalue()
    if results == expected_results:
        print('OK.')
    else:
        for line in difflib.context_diff(results, expected_results):
             sys.stdout.write(line)  

def run_tests(story_directory):
    for path in os.listdir(story_directory):
        if path.endswith('.z3'):
            filename,ext = os.path.splitext(path)
            out_file = os.path.join(story_directory, '%s.out' % (filename,))
            commands_file = os.path.join(story_directory,'%s.commands' % (filename))
            if os.path.exists(out_file) and os.path.exists(commands_file):
                test_story(os.path.join(story_directory,path), 
                           out_file,
                           commands_file)

def main(*args):
    if sys.version_info[0]<3:
        raise Exception('Moosezmachine requires Python 3.')
    
    parser = argparse.ArgumentParser()
    parser.add_argument('directory',help='Directory containing test files ')
    data = parser.parse_args()

    run_tests(data.directory)

if __name__ == "__main__":
    main()
