# moosezmachine

moosezmachine is a Python 3 implementation of a Z-Machine (Z-code interpreter) based off the Z-Machine Standards Document version 1.0 (http://inform-fiction.org/zmachine/standards/z1point0/sect03.html)

moosezmachine needs at least Python 3.4 to work.

This project is a reference implementation -- no effort has been put into optimizations. 

Currently it only handles zcode versions 1 through 3. 

For simplicity, the unicode mappings map to textual equivalents (per 3.8.5.4.1)

## Architecture

Moosezmachine includes a number of interpreters for various purposes (command line, testing, etc). They all work in the following basic way:

The core object is the Interpreter (in zmachine.interpreter). This object acts as the virtual machine for the ZCode in the story file.

To initialize an Interpreter, you ned:
- A zmachine.interpreter.Story. This is intialized with the bytes from the the target story file 
- A zmachine.interpreter.OutputStreams object. This is initialized with zmachine.interpreter.OutputStream handlers for streams 1-4
  - Stream 1 is the normal output stream (the screen)
  - Stream 2 is the transcript stream
  - Stream 3 is a special memory-only stream
  - Stream 4 is a special stream that only records the player's commands
- A zmachine.interpreter.InputStreams object. This is initialized with zmachine.interpreter.InputStream handlers for streams 1-2.
  - Stream 1 is the normal input stream (keyboard)
  - Stream 2 is a list of commands
- A zmachine.interpreter.SaveHandler
- A zmachine.interpreter.RestoreHandler

To initialize, call reset() on the interpreter object. This will initialize the game from the story file data, and throw an exception if the data is invalid in some way.

The interpreter does nothing on its own. To run the instruction at the current program counter, call interpreter.step(). This will run the instruction and change any internal state. 

The internal state will be one of:

- Interpreter.RUNNING_STATE: can call step to run next instruction
- Interpreter.WAITING_FOR_LINE_STATE: waiting for the next command.

If the state is WAITING_FOR_LINE_STATE, calling step() will call readline() on the interpreters InputStreams. If it returns anything but None, the intepreter will tokenize and process the command and set the state to RUNNING_STATE again.

After each step, interpreter.last_instruction will bet set to a textual description of the previous instruction for debugging purposes.

### Input

Versions of ZCode 4 and after allow for reading individual characters from the input stream. Moosezmachine sticks with verisons 3 and less and treats input as entirely modal.

An input stream needs only to implement a zero-parameter function, readline(). This should return None if no input is ready, or the input text if it has been completed.

### Output

An output stream needs to implement three functions:

- new_line: send output to the next line
- print_str(str): handle output of a string of unicode text. This may or may not have newline characterse in it.
- show_status(room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0): display the status bar with the provided info (see section 8.2)

## Licence/Thanks

MooseZMachine is licensed under the MIT license.

I used ZILF to create sample zcode files for testing (http://sourceforge.net/p/zilf/_list/tickets?source=navbar)

ZTools was very helpful for debugging (http://inform-fiction.org/zmachine/ztools.html)

GltOte (http://www.eblong.com/zarf/glk/glkote.html) is used for the web version.
