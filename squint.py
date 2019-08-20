#!/usr/bin/python

import sys
import signal
import locale
import time
import math
import code
import copy

import curses
import curses.textpad
import curses.panel
import configparser
import mysql.connector

import squirrel.squid
import toolbelt


def validate(str):
    return str;

def terminal_size():
    import fcntl, termios, struct
    h, w, hp, wp = struct.unpack('HHHH',
        fcntl.ioctl(0, termios.TIOCGWINSZ,
        struct.pack('HHHH', 0, 0, 0, 0)))
    return w, h


global stdscr;
stdscr = curses.initscr()
stdscr.keypad(True);
stdscr.border(0);

(width, height) = terminal_size();
stdscr.resize(height, width);
stdscr.refresh();

curses.noecho();
curses.start_color();

curses.init_pair(1, 
      curses.COLOR_WHITE,
      curses.COLOR_RED
)

curses.init_pair(2, 
      curses.COLOR_RED,
      curses.COLOR_WHITE
)

curses.init_pair(3, 
      curses.COLOR_YELLOW,
      curses.COLOR_BLACK
)

curses.init_pair(4, 
      curses.COLOR_BLACK,
      curses.COLOR_YELLOW
)



def startup():
    # export PYTHONIOENCODING=utf8
    # reload(sys)
    # locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    signal.signal(signal.SIGINT, signal.SIG_IGN)



# Keybindings for various windows. A binding is a dictionary
# which has key as the key, and the tuple (callback, args) as
# the value.
class KeyBindings():

    bindings = {}

    def __init__(self, bindings=None):
        if bindings == None:
           bindings = {};
        else: self.bindings = bindings;

    def add(self, key, callback, args):
        self.bindings[key] = (callback, args);

    def handle(self, key):
        if key not in self.bindings: return True;
        (callback, args) = self.bindings[key];
        if args == None: return callback();
        else:            return callback(args);

    def legend(self):
        str = "";
        for key in self.bindings:
            str += "   " + key + ": " + self.bindings[key][0].__name__ + '\n';
        notewin.write(str);
        return True;


# Default keybindings for any interactive window.
def default_kb(obj):

    def up(obj):
        obj.cursor.up();
        return True;
        
    def down(obj):
        obj.cursor.down();
        return True;

    def left(obj):
        obj.cursor.left();
        return True;

    def right(obj):
        obj.cursor.right();
        return True;

    def quit(obj=None):
        if obj:
            obj.windowpanel.window.clear();
            obj.windowpanel.window.refresh();
        return False;

    def tab(obj=None):
        cmd = cmdwin.read();
        cmd = cmd.split();
        obj.command(cmd);
        return True;

    def enter(obj):
        if isinstance(obj, MainMenu):
           pos = obj.cursor.xpos;
        else:
           pos = obj.cursor.ypos;
        obj.submenus[pos].draw();
        return True;

    def legend(obj):
        obj.keybindings.legend();

    bindings = {};
    bindings['k'] = (up,    obj);
    bindings['j'] = (down,  obj);
    bindings['h'] = (left,  obj);
    bindings['l'] = (right, obj);
    bindings['q'] = (quit,  obj);
    bindings['?'] = (legend,  obj);
    bindings['\n'] = (enter,  obj);
    bindings['\t'] = (tab,  obj);

    return KeyBindings(bindings);



# Contains a curses window and its panel.  Makes it easier
# to associate windows with their panels.
class WindowPanel():
    
    xoff = 1;
    yoff = 1;
    xlen = 10;
    ylen = 10;

    title  = "";
    colors = None;
    window = None;
    panel  = None;
    border = None;

    def __init__(self, coords, title, colors=None): 

        (xo, yo, xl, yl) = coords;
        self.xoff = xo;
        self.yoff = yo;
        self.xlen = xl;
        self.ylen = yl;
        self.title = title;
        self.colors = colors;

        self.window = curses.newwin(
          self.xlen,
          self.ylen,
          self.xoff,
          self.yoff
        );

        self.panel = curses.panel.new_panel(
          self.window
        );


    def remake(self):
        #print self.xoff, self.yoff, self.xlen, self.ylen;
        if self.xlen > 0 and self.ylen > 0:
           self.window.resize(self.ylen, self.xlen);
        self.window.mvwin(self.yoff, self.xoff);



class Cursor():

      xpos        = 0
      xmin        = 0
      xmax        = 0
      ypos        = 0
      ymin        = 0
      ymax        = 0

      def up(self):
          if self.ypos > self.ymin:
             self.ypos -= 1;
      
      def down(self):
          if self.ypos < self.ymax-1:
             self.ypos += 1;

      def left(self):
          if self.xpos > self.xmin:
             self.xpos -= 1;

      def right(self):
          if self.xpos < self.xmax-1:
             self.xpos += 1;

      def str(self):
          return (self.xpos, self.ypos), (self.xmin, self.xmax, self.ymin, self.ymax);

      def __init__(self, xmin, xmax, ymin, ymax):
          self.xpos = xmin;
          self.xmin = xmin;
          self.xmax = xmax;
          self.ypos = ymin;
          self.ymin = ymin;
          self.ymax = ymax;


# Interactive window with widget such as calendar, 
# The field *commands* is a list of (grammar, callback, args).
class InteractiveWindow():

      windowpanel = None;
      keybindings = None;
      cursor      = None;
      title       = "";
      

      def __init__(self, title, keybindings):
          coords = (1,1,10,10);
          self.title = title;
          self.keybindings = keybindings;
          self.windowpanel = WindowPanel(
            coords, title
          );

      
      def draw(self):
          pass;


      def wait(self):
        stdscr.refresh();
        self.windowpanel.window.border('|', '|', '-', '-', '+', '+', '+', '+' );
        self.windowpanel.window.refresh();
        k = chr(stdscr.getch());
        retval = self.keybindings.handle(k);
        self.windowpanel.window.refresh();
        return retval;


# A window specifically for displaying a MySQL object. It has
# a SQUId, which can be used to query and manipulate the
# object.
class ObjectWindow(InteractiveWindow):

    squid = None;

    def __init__(self, title, keybindings, squid):
        InteractiveWindow.__init__(self, title, keybindings);
        if self.keybindings == None:
           self.keybindings = default_kb(self);
        self.squid = squid;



class NewWindow(ObjectWindow):

    def get_value(self):

        fieldwin = curses.newwin(1, 20, 
            self.windowpanel.yoff+self.cursor.ypos+2,
            self.windowpanel.xoff+self.maxkeylen+5,
        );

        key = self.keys[self.cursor.ypos];
        sqltype = self.squid.fields[key];

        notepad = curses.textpad.Textbox(fieldwin);
        if sqltype == "text":
           if key in self.squid.data:
             result = self.squid.data[key];
           else: result = "";
           result = toolbelt.editors.vim(result);
           stdscr.clear();
           stdscr.refresh();
           self.windowpanel.window.refresh();
        else: result = notepad.edit();

        if sqltype == "datetime":
           result = toolbelt.converters.date(result);

        self.squid.data[key] = result;
        return True;


    def insert(self):
        notewin.write(self.squid.data);
        self.squid.insert(self.squid.data);


    def __init__(self, title, keybindings, squid):

        ObjectWindow.__init__(self, title, keybindings, squid);
        self.keybindings.add('\n', self.get_value, None)
        self.keybindings.add('i', self.insert, None);

        self.squid.query("select max(id) from "+self.squid.table);
        self.squid.data = self.squid.data[0];
        self.squid.data['id'] = self.squid.data['max(id)'] + 1;
        del self.squid.data['max(id)'];

        self.keys = self.squid.get_fields();
        self.reconstruct();


    def reconstruct(self):

        self.cursor = Cursor(0, 0, 0, len(self.keys));
        self.maxkeylen = len(max(self.keys, key=len));
        self.maxkeylen = self.maxkeylen if self.maxkeylen < 20 else 20;
        self.maxvallen = 20;
        self.windowpanel.ylen = len(self.keys) + 5;
        self.windowpanel.xlen = self.maxkeylen + self.maxvallen + 20;
        self.windowpanel.xoff = 2;
        self.windowpanel.yoff = 4;
        self.windowpanel.remake();


    def draw(self):

        keycode = True;

        while keycode == True:

           i = 0;
           for key in self.keys:
               if key in self.squid.data:
                  val = str(self.squid.data[key]);
               else: val = '';
               keyspaces = ' ' * (self.maxkeylen - len(key));
               valspaces = ' ' * (self.maxvallen - len(val));
               color = (i == self.cursor.ypos) + 1;
               self.windowpanel.window.addstr(
                         i+2, 2, key[:20]+keyspaces+' : '+val+valspaces, 
                         curses.color_pair(color)
               );
               i = i + 1;

           keycode = self.wait();

        self.windowpanel.window.clear();
        self.windowpanel.window.refresh();



class EditWindow(ObjectWindow):

    def asc_sort(self):
        self.data.sort(key = lambda x:x[self.cursor.xpos]);
        return True;

    def desc_sort(self):
        self.data.sort(key = lambda x:x[self.cursor.xpos], reverse=True);
        return True;

    def scroll_right(self):
        if self.xmax < len(self.keys):
           self.xmax = self.xmax + 1;
           self.xmin = self.xmin + 1;
           self.cursor.right();
        return True;

    def scroll_left(self):
        if self.xmin > 0:
           self.xmin = self.xmin - 1;
           self.xmax = self.xmax - 1;
           self.cursor.left();
        return True;

    def scroll_down(self):
        if self.ymax <= len(self.data)-1:
           self.ymin = self.ymin + 1;
           self.ymax = self.ymax + 1;
           self.cursor.down();
        return True;

    def scroll_up(self):
        if self.ymin > 0:
            self.ymin = self.ymin - 1;
            self.ymax = self.ymax - 1;
            self.cursor.up();
        return True;

    def __init__(self, title, keybindings, squid):

        ObjectWindow.__init__(self, title, keybindings, squid);
        self.keybindings = default_kb(self);

        self.keybindings.add('>', self.asc_sort,  None);
        self.keybindings.add('<', self.desc_sort, None);

        self.keybindings.add('L', self.scroll_right, None);
        self.keybindings.add('H', self.scroll_left,  None);
        self.keybindings.add('J', self.scroll_down,  None);
        self.keybindings.add('K', self.scroll_up,    None);

        self.keys = self.squid.get_fields();

        self.maxkeylen = len(max(self.keys, key=len));
        self.maxkeylen = self.maxkeylen if self.maxkeylen < 20 else 20;
        self.maxvallen = 10;

        (w, h) = terminal_size();
        self.windowpanel.xlen = w - 6;
        self.windowpanel.ylen = h - 8;
        self.windowpanel.xoff = 2;
        self.windowpanel.yoff = 4;
        self.windowpanel.remake();


    def draw(self):

        sql = cmdwin.read();
        if sql=="": sql="select * from "+self.squid.table;
        self.squid.query(sql);

        if not self.squid.data:
           notewin.write("No results!");
           return;

        self.data = [list(zip(d.values())) for d in self.squid.data]
        self.cursor = Cursor(0, len(self.keys), 0, len(self.data));

        self.xmin = self.cursor.xmin;
        self.xvis = self.windowpanel.xlen / self.maxvallen - 2;
        self.xmax = self.xvis if len(self.keys) > self.xvis else len(self.keys);
        self.ymin = self.cursor.ymin;
        self.yvis = self.windowpanel.ylen - 2;
        self.ymax = self.yvis if len(self.data) > self.yvis else len(self.data);

        keycode = True;

        while keycode:
              
              # Draw the keys
              xpos = 0;
              ypos = 0;
              for xpos in range(self.xmin, self.xmax):
                  dat = self.keys[xpos][0:self.maxvallen-2];
                  numspaces = self.maxvallen - 2 - len(dat);
                  self.windowpanel.window.addstr(
                    1,
                    1+(xpos - self.xmin)*self.maxvallen,
                    dat + ' '*numspaces,
                    curses.color_pair(4)
                  )

              # Draw the data entries
              xpos = 0;
              ypos = 0;
              for ypos in range(self.ymin, self.ymax):
                  for xpos in range(self.xmin, self.xmax):
                      color = (self.cursor.xpos == xpos and self.cursor.ypos == ypos) + 1;
                      dat = str(self.data[ypos][xpos][0])[0:self.maxvallen-2].encode('ascii', 'ignore'),
                      numspaces = self.maxvallen - 2 - len(dat);
                      self.windowpanel.window.addstr(
                        (ypos - self.ymin)+2,
                        1+(xpos - self.xmin)*self.maxvallen,
                        "".join(dat) + ' '*numspaces,
                        curses.color_pair(color)
                      )

              keycode = self.wait();



class ViewWindow(ObjectWindow):


  def __init__(self, title, keybindings, squid):

      ObjectWindow.__init__(self, title, keybindings, squid);
      self.keybindings = default_kb(self);


  def draw(self):

        sql = cmdwin.read();
        self.squid.query(sql);

        if self.squid.data:
           datum = self.squid.data[0]
           keys = datum.keys();
           self.cursor = Cursor(0, len(self.squid.data), 0, len(keys));
           vals = map(str, datum.values());
           maxkeylen = len(max(keys, key=len));
           maxkeylen = maxkeylen if maxkeylen < 20 else 20;
           maxvallen = 20;
           self.windowpanel.ylen = len(keys) + 5;
           self.windowpanel.xlen = maxkeylen + maxvallen + 4;
           self.windowpanel.xoff = 2;
           self.windowpanel.yoff = 4;
           self.windowpanel.remake();

           keycode = True;
           while keycode:

               datum = self.squid.data[self.cursor.xpos]

               i = 0;
               for key in datum:
                   val = str(datum[key])[:20];
                   keyspaces = ' ' * (maxkeylen - len(key));
                   valspaces = ' ' * (maxvallen - len(val));
                   color = (i == self.cursor.ypos) + 1;
                   self.windowpanel.window.addstr(
                         i+2, 
                         2, 
                         key[:20]+keyspaces+' : '+val+valspaces, 
                         curses.color_pair(color)
                   );
                   i = i + 1;

               keycode = self.wait();


class NotificationWindow(InteractiveWindow):

    msg = "";


    def quit(obj=None):
        return False;


    def __init__(self):

        (width, height) = terminal_size();
        InteractiveWindow.__init__(self, None, None);

        self.windowpanel.xoff = 2;
        self.windowpanel.yoff = 4;
        self.windowpanel.xlen = width - 6;
        self.windowpanel.ylen = height - 6;
        self.windowpanel.remake();

        self.keybindings = KeyBindings();
        self.keybindings.add('\n', self.quit, None);


    def draw(self):

        mmax = len(self.msg);
        step = self.windowpanel.xlen - self.windowpanel.xoff*2;
        lmax = mmax / step;
        if lmax <= 0: 
           lmax = 1;
        elif lmax > self.windowpanel.ylen-2:
           lmax = self.windowpanel.ylen-2;

        for x in range(0, lmax):
            self.windowpanel.window.addstr(
                 2+x, 
                 3,
                 self.msg[x*step:(x+1)*step],
                 curses.color_pair(1)
            );

        self.wait();


    def write(self, msg):
        self.msg = str(msg);
        self.draw();


class CmdWindow(InteractiveWindow):

    mainmenu = None;
    linewin  = None;

    def __init__(self, mainmenu=None):

        self.mainmenu = mainmenu;
        InteractiveWindow.__init__(self, None, None);

        (width, height) = terminal_size();
        self.windowpanel.xlen = width - 12;
        self.windowpanel.ylen = 3;
        self.windowpanel.yoff = height - 4;
        self.windowpanel.xoff = 2;

        self.windowpanel.remake();

        self.linewin = curses.newwin(1, width-16, height-3, 10);
        self.draw();


    def draw(self):
        self.windowpanel.window.addstr(
             1, 3,
             " > ",
             curses.color_pair(1)
        );
        self.windowpanel.window.border('|', '|', '-', '-', '+', '+', '+', '+' );
        self.windowpanel.window.refresh();

    def undraw(self):
        self.windowpanel.window.clear();
        self.windowpanel.window.refresh();

    def read(self):
        self.draw();
        cmdpad = curses.textpad.Textbox(self.linewin);
        x = cmdpad.edit(validate);
        for i in range(0, len(x)):
          cmdpad.do_command(curses.KEY_BACKSPACE);
        #self.undraw();
        return x



# A submenu underneath the main menu.
class SubMenu(InteractiveWindow):

    # Commands include submenu titles, and their callbacks open
    # the menu.
    submenus = [];

    def maxlen(self):
        max_len = 0;
        for submenu in self.submenus:
            length = len(submenu.title)
            if length > max_len:
               max_len = length;
        return max_len;


    def __init__(self, title, keybindings, submenus):
        self.submenus = submenus;
        self.cursor = Cursor(0, 0, 0, len(self.submenus));
        InteractiveWindow.__init__(self, title, keybindings);
        self.keybindings = default_kb(self);

        i = 0;
        maxlen = self.maxlen();
        for submenu in submenus:
            if isinstance(submenu, SubMenu):
                submenu.windowpanel.xoff = self.windowpanel.xoff + maxlen;
                submenu.windowpanel.yoff = self.windowpanel.yoff + i;
                submenu.windowpanel.xlen = submenu.maxlen();
                submenu.windowpanel.ylen = len(submenu.submenus);
                submenu.windowpanel.remake();
            i = i + 1;


    def command(self, cmd):
        if len(cmd) > 1:
           for submenu in self.submenus:
               if submenu.title == cmd[0]:
                  submenu.command(cmd[1:]);
        else:
           for submenu in self.submenus:
               if submenu.title == cmd[0]:
                  submenu.draw();
           


    def draw(self, cmd=None):

        maxlen = self.maxlen();
        keycode = True;

        while keycode:

            i = 0;
            for submenu in self.submenus:
                color = (i == self.cursor.ypos) + 1;
                self.windowpanel.window.addstr(
                     i+1, 2,
                     submenu.title,
                     curses.color_pair(color)
                );
                i = i + 1;

            if cmd:
               self.command(cmd);
            else:
               keycode = self.wait();




# A main menu, which is distinct in that it has stdscr.
class MainMenu(SubMenu):


    #cmdwin = None;


    def __init__(self, submenus):
        title = "main";
        SubMenu.__init__(self, title, None, submenus);
        self.cursor = Cursor(0, len(self.submenus), 0, 0);
        self.keybindings = default_kb(self);
        (width, _) = terminal_size();
        self.windowpanel.xlen = width-8;
        self.windowpanel.ylen = 3;
        self.windowpanel.xoff = 2;
        self.windowpanel.remake();

        i = 0;
        maxlen = self.maxlen();
        for submenu in submenus:
            submenu.windowpanel.yoff = self.windowpanel.yoff + 3;
            submenu.windowpanel.xoff = 5 + i * (self.maxlen()+1);
            submenu.windowpanel.xlen = submenu.maxlen() + 4;
            submenu.windowpanel.ylen = len(submenu.submenus) + 2;
            submenu.windowpanel.remake();
            submenu.windowpanel.window.refresh();
            i = i + 1;
        #self.cmdwin = CmdWindow(self);



    def draw(self, cmd=None):

        maxlen = self.maxlen();
        keycode = True;

        while keycode:

            i = 0;
            offset = 2;
            self.windowpanel.window.clear();
            for submenu in self.submenus:
                color = (i == self.cursor.xpos) + 1;
                #print self.windowpanel.yoff, self.windowpanel.xoff+offset, color
                self.windowpanel.window.addstr(
                     self.windowpanel.yoff, 
                     self.windowpanel.xoff + offset, 
                     submenu.title,
                     curses.color_pair(color)
                );
                i = i + 1;
                offset = offset + maxlen + 1;
            
            keycode = self.wait();


# I left off at creating the 'Enter' keybinding for delving into submenus.

global cmdwin;
cmdwin = CmdWindow();
global notewin;
notewin = NotificationWindow();
