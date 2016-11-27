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
from curses_terp import StringIOOutputStream,FileInputStream

def test_story(story_path,out_path,commands_path,dump):
    print("Starting test of %s" % story_path)
    story_stream = StringIO()
    zmachine = load_zmachine(story_path)
    output_stream = StringIOOutputStream(story_stream)
    zmachine.output_streams.set_screen_stream(output_stream)
    input_stream = FileInputStream(output_stream,add_newline=False)
    input_stream.load_from_path(commands_path)
    zmachine.input_streams.keyboard_stream = input_stream
    zmachine.input_streams.select_stream(0)
    zmachine.story.rng.enter_predictable_mode(0)

    terp = Terp(zmachine,None,'testing')
    terp.run()

    while True:
        try:
            terp.idle(input_stream)
        except QuitException:
            break
    
    print('Done. Comparing results')
    expected_results = open(out_path,'r').read()
    results = story_stream.getvalue()
    if dump:
        print(results)
    if results == expected_results:
        print('OK.')
    else:
        counter = 0
        got = results.split('\n')
        expected_lines = expected_results.split('\n')
        for line,expected in zip(got,expected_lines):
            counter+=1
            if line != expected:
                print('Line %d\nGot     : %s\nExpected: %s\n' % (counter,line,expected))
                print('Context for got:\n%d) %s\n%d) %s\n%d) %s\n\n' % (counter-2,
                    got[counter-2],
                    counter-1,
                    got[counter-1],
                    counter,got[counter]))
                print('Context for expected:\n%d) %s\n%d) %s\n%d) %s' % (counter-2,
                        expected_lines[counter-2],
                        counter-1,
                        expected_lines[counter-1],
                        counter,
                        expected_lines[counter]))
                return

def run_tests(story_directory,dump):
    for path in os.listdir(story_directory):
        if path.endswith('.z3') or path.endswith('.z5'):
            filename,ext = os.path.splitext(path)
            out_file = os.path.join(story_directory, '%s.out' % (filename,))
            commands_file = os.path.join(story_directory,'%s.commands' % (filename))
            if os.path.exists(out_file) and os.path.exists(commands_file):
                test_story(os.path.join(story_directory,path), 
                           out_file,
                           commands_file,
                           dump=dump)

def main(*args):
    if sys.version_info[0]<3:
        raise Exception('Moosezmachine requires Python 3.')
    
    parser = argparse.ArgumentParser()
    parser.add_argument('directory',help='Directory containing test files ')
    parser.add_argument('--dump',help='Print test output ',required=False,action='store_true')
    data = parser.parse_args()

    run_tests(data.directory,dump=data.dump)

if __name__ == "__main__":
    main()
