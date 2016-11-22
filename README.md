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
- A zmachine.interpreter.OutputStreams object. This is initialized with zmachine.interpreter.OutputStream handlers for streams 1-4 (see section below)
- A zmachine.interpreter.InputStreams object. This is initialized with zmachine.interpreter.InputStream handlers for streams 1-2. (see section below)
- A zmachine.interpreter.SaveHandler
- A zmachine.interpreter.RestoreHandler

To initialize, call reset() on the interpreter object. This will initialize the game from the story file data, and throw an exception if the data is invalid in some way.

The interpreter does nothing on its own. To run the instruction at the current program counter, call interpreter.step(). This will run the instruction and change any internal state. 
After each step, interpreter.last_instruction will bet set to a textual description of the previous instruction for debugging purposes.

### Input

Versions of ZCode 4 and after allow for reading individual characters from the input stream. Moosezmachine sticks with verisons 3 and less and treats input as entirely modal.


## 
python dump_header.py story_file_path: this will load the story file and if valid dump notable header data.

## Licence/Thanks

MooseZMachine is licensed under the MIT license.

I used ZILF to create sample zcode files for testing (http://sourceforge.net/p/zilf/_list/tickets?source=navbar)

ZTools was very helpful for debugging (http://inform-fiction.org/zmachine/ztools.html)

GltOte (http://www.eblong.com/zarf/glk/glkote.html) is used for the web version.
