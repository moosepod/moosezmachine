# moosezmachine

moosezmachine is a Python 3 implementation of a Z-Machine (Z-code interpreter) based off the Z-Machine Standards Document version 1.0 (http://inform-fiction.org/zmachine/standards/z1point0/sect03.html)

moosezmachine needs at least Python 3.4 to work.

This project is a reference implementation -- no effort has been put into optimizations. 

Currently it only handles zcode versions 1 through 3. 

For simplicity, the unicode mappings map to textual equivalents (per 3.8.5.4.1)

## Architecture

The zcode itself is handled by zmachine.interpreter.ZMachine. Story data is loaded into the interpreter by setting raw_data -- note this will throw an exception if the data is too short.

A wrapper object, memory.Memory, is used to intermediate the raw data. This makes it easy to pull out the various ZCode data types (address, single-byte integer, etc).

When zmachine.raw_data is set, zmachine.header is set as well. This object provides convienence methods for the accessing the header data. 

Other utility classes handle zchar interpretation, rng, etc/

## Scripts

python dump_header.py story_file_path: this will load the story file and if valid dump notable header data.

## Licence/Thanks

MooseZMachine is licensed under the MIT license.

I used ZILF to create sample zcode files for testing (http://sourceforge.net/p/zilf/_list/tickets?source=navbar)

ZTools was very helpful for debugging (http://inform-fiction.org/zmachine/ztools.html)
