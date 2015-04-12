# moosezmachine

moosezmachine is a Python implementation of a Z-Machine (Z-code interpreter) based off the Z-Machine Standards Document (http://inform-fiction.org/zmachine/standards/z1point1/index.html)

This project is a reference implementation -- no effort has been put into optimizations. 

Currently it only handles through v5.

## Architecture

The zcode itself is handled by zmachine.interpreter.ZMachine. Story data is loaded into the interpreter by setting raw_data -- note this will throw an exception if the data is too short.

When zmachine.raw_data is set, zmachine.header is set as well. This object provides convienence methods for the accessing the header data. 

## Scripts

python dump_header.py story_file_path: this will load the story file and if valid dump notable header data.

## Licence/Thanks

MooseZMachine is licensed under the MIT license.

I used ZILF to create sample zcode files for testing (http://sourceforge.net/p/zilf/_list/tickets?source=navbar)
