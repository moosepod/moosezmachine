
from zmachine.interpreter import Story,Interpreter,OutputStream,OutputStreams,Memory,QuitException,\
                                 StoryFileException,InterpreterException,MemoryAccessException,\
                                 InputStreams,InputStream

class ConfigException(Exception):
    pass

class FileStreamEmptyException(Exception):
    """ Thrown when a file input stream runs out of commands """
    pass

class FileInputStream(object):
    """ Input stream for handling commands stored in a file """
    def __init__(self,output_stream=None,add_newline=True):
        self.commands = []
        self.index = -1
        self.output_stream=output_stream
        self.waiting_for_line = False
        self.add_newline = add_newline

    def load_from_path(self,path):
        with open(path,'r') as f:
            for line in f:
                self.commands.append(line.strip())

    def readline(self):
        self.index += 1
        try:
            command = self.commands[self.index] 
            if self.output_stream:
                self.output_stream.print_str(command)
                if self.add_newline:
                    self.output_stream.new_line()
        except IndexError:
            raise FileStreamEmptyException()

        return command

    def char_pressed(self,char):
        pass

class STDOUTOutputStream(OutputStream):
    def __init__(self):
        super(STDOUTOutputStream,self).__init__()
        self.buffer = ''
        self.status_height,self.status_width=0,0        

    def refresh(self):
        pass

    def new_line(self):
        print('')
        
    def print_str(self,txt):
        print(txt,end='')

    def print_char(self,txt):
        print(txt,end='')

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        pass


class FileOutputStream(OutputStream):
    def __init__(self,path):
        super(FileOutputStream,self).__init__()
        self.buffer = ''
        self.path = path


    def flush(self):
        with open(self.path,'a') as f:
            f.write(str(self.buffer.encode('ascii','replace'),'ascii'))
        self.buffer = ''

    def new_line(self):
        self.buffer += '\n'
        
    def print_str(self,txt):
        self.buffer += str(txt)

    def print_char(self,txt):
        self.buffer += str(txt)

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        pass

class StringIOOutputStream(OutputStream):
    def __init__(self,io_stream):
        self.io_stream = io_stream
        super(StringIOOutputStream,self).__init__()

    def refresh(self):
        pass

    def new_line(self):
        self.io_stream.write('\n')
    
    def print_str(self,txt):
        self.io_stream.write(txt)

    def print_char(self,ch):
        self.io_stream.write(ch)

    def show_status(self,room_name,score_mode=True,hours=0,minutes=0,score=0,turns=0):
        pass