from zmachine.interpreter import OutputStream

class BufferInputStream(object):
    def __init__(self,text):
        super(BufferInputStream,self).__init__()
        self.waiting_for_line = False
        self.text = text

    def readline(self):
        if self.text:
            self.waiting_for_line = False
            text = self.text
            self.text = None
            return text
        self.waiting_for_line = True

        return None

class BufferOutputStream(OutputStream):
    def __init__(self):
        super(BufferOutputStream,self).__init__()
        self.room_name = ''
        self.location = ''
        self.score_text = ''
        self.text=''
    
    def _println(self,msg):
        self.text += msg
        self.text += '\n'

    def _print(self,msg):
        self.text += msg

    def new_line(self):
        self.text += '\n'
        
    def print_str(self,txt):
        self._print(txt)

    def print_char(self,txt):
        self._print(txt)

    def show_status(self, room_name, score_mode=True,hours=0,minutes=0, score=0,turns=0):
        if score_mode:
            self.score_text = 'Score: %s Moves: %s' % (score or 0,turns or 0)
        else:
            self.score_text = '%02d:%02d' % (hours,minutes)

        self.room_name = room_name