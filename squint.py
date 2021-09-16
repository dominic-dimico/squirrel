#!/usr/bin/python

import sys
import signal
import locale
import time
import math
import code
import copy
import threading;
import re;

import curses
import curses.textpad
import curses.panel
import configparser
import MySQLdb

import squirrel.squid
import toolbelt


# I may be able to create a Squint class (representing the application) and
# keep all these globals inside of it.  The Squint (i.e. the application) has
# the tab, notification, command windows, and the main menu; so then it should
# be possible to move these around inside of it.

# Alternatively, use some sort of interprocess communication, like Queue.  It
# may make sense to have these windows running as separate threads, especially
# notification window.  IPC would be better for that anyway.


def validate(str):
    return str;

def terminal_size():
    import fcntl, termios, struct
    h, w, hp, wp = struct.unpack('HHHH',
        fcntl.ioctl(0, termios.TIOCGWINSZ,
        struct.pack('HHHH', 0, 0, 0, 0)))
    return w, h


global stdscr;
global cmdwin;
global notewin;
global tabwin;
global lock;
global tabpos;

lock = threading.Lock();
tabpos = -1;


def startup():

    global stdscr;
    global cmdwin;
    global notewin;

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

    # export PYTHONIOENCODING=utf8
    # reload(sys)
    # locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
    signal.signal(signal.SIGINT, signal.SIG_IGN)

    cmdwin = CmdWindow();
    notewin = NotificationWindow();
    tabwin = TabWindow();

    return (cmdwin, notewin, tabwin);



# Default keybindings for any interactive window.
def default_kb(obj):

    def xbegin(obj):
        obj.cursor.xpos = obj.cursor.xmin;
        return True;

    def xend(obj):
        obj.cursor.xpos = obj.cursor.xmax;
        return True;

    def ybegin(obj):
        obj.cursor.ypos = obj.cursor.ymin;
        return True;

    def yend(obj):
        obj.cursor.ypos = obj.cursor.ymax;
        return True;

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
            stdscr.refresh();
        return False;

    def tab(obj=None):
        #lock.acquire();
        cmd = cmdwin.read();
        #lock.release();
        obj.command(cmd);
        return True;

    def enter(obj):
        if isinstance(obj, MainMenu):
           pos = obj.cursor.xpos;
           obj.submenus[pos].draw();
        else: 
            pos = obj.cursor.ypos;
            #t = threading.Thread(target=obj.submenus[pos].draw);
            #tabs.append((t, obj));
            #tabpos = (tabpos + 1) % len(tabs);
            #t.start();
            obj.submenus[pos].draw();
            obj.windowpanel.window.clear();
            obj.windowpanel.window.refresh();
        return True;


    def legend(obj):
        obj.keybindings.legend();
        return True;


    bindings = {};

    bindings['w'] = (WindowPanel.up, obj.windowpanel);
    bindings['s'] = (WindowPanel.down, obj.windowpanel);
    bindings['a'] = (WindowPanel.left, obj.windowpanel);
    bindings['d'] = (WindowPanel.right, obj.windowpanel);
    bindings['W'] = (WindowPanel.yup, obj.windowpanel);
    bindings['S'] = (WindowPanel.ydown, obj.windowpanel);
    bindings['A'] = (WindowPanel.xdown, obj.windowpanel);
    bindings['D'] = (WindowPanel.xup, obj.windowpanel);

    bindings['g'] = (ybegin, obj);
    bindings['G'] = (yend,   obj);
    bindings['^'] = (xbegin, obj);
    bindings['$'] = (xend,   obj);

    bindings['k'] = (up,    obj);
    bindings['j'] = (down,  obj);
    bindings['h'] = (left,  obj);
    bindings['l'] = (right, obj);
    bindings['q'] = (quit,  obj);
    bindings['?'] = (legend,  obj);
    bindings['\n'] = (enter,  obj);
    bindings['\t'] = (tab,  obj);

    return toolbelt.keybindings.KeyBindings(bindings);



# Contains a curses window and its panel.  Makes it easier
# to associate windows with their panels.
class WindowPanel():
    
    title  = "";
    colors = None;
    window = None;
    panel  = None;
    border = None;
    coords = None;

    def __init__(self, coords, title, colors=None): 

        (xl, yl, xo, yo) = coords;
        self.coords = Coords(xl, yl, xo, yo);
        self.title = title;
        self.colors = colors;

        self.window = curses.newwin(
          self.coords.ylen,
          self.coords.xlen,
          self.coords.yoff,
          self.coords.xoff
        );

        self.panel = curses.panel.new_panel(
          self.window
        );


    def resize(self, xl, yl, xo, yo):
        self.coords.xlen = xl;
        self.coords.ylen = yl;
        self.coords.xoff = xo;
        self.coords.yoff = yo;
        self.remake();


    def remake(self):
        if self.coords.xlen > 0 and self.coords.ylen > 0:
           self.window.resize(self.coords.ylen, self.coords.xlen);
        self.window.mvwin(self.coords.yoff, self.coords.xoff);


    def redraw(self):
        self.window.clear();
        self.remake();
        self.window.refresh();


    def up(self):
        if not self.coords.violation(0, 0, 0, -1):
           self.coords.yoff -= 1;
           self.redraw();
        return True;
    

    def down(self):
        if not self.coords.violation(0, 0, 0, 1):
           self.coords.yoff += 1;
           self.redraw();
        return True;
  

    def left(self):
        if not self.coords.violation(0, 0, -1, 0):
           self.coords.xoff -= 1;
           self.redraw();
        return True;
  

    def right(self):
        if not self.coords.violation(0, 0, 0, 1):
           self.coords.xoff += 1;
           self.redraw();
        return True;
  

    def xup(self):
        if not self.coords.violation(1, 0, 0, 0):
           self.coords.xlen += 1;
           self.redraw();
        return True;
    

    def xdown(self):
        if not self.coords.violation(-1, 0, 0, 0):
           self.coords.xlen -= 1;
           self.redraw();
        return True;
  

    def yup(self):
        if not self.coords.violation(0, 1, 0, 0):
           self.window.refresh();
           self.redraw();
        return True;
    

    def ydown(self):
        if not self.coords.violation(0, -1, 0, 0):
           self.coords.ylen -= 1;
           self.redraw();
        return True;
  


# Interactive window with widget such as calendar, 
# The field *commands* is a list of (grammar, callback, args).
class InteractiveWindow():

      windowpanel = None;
      keybindings = None;
      cursor      = None;
      title       = "";
      

      def __init__(self, title, keybindings):
          coords = (10,10,1,1);
          self.title = title;
          self.keybindings = keybindings;
          self.windowpanel = WindowPanel(
            coords, title
          );

      
      def draw(self):
          pass;


      def wait(self):

        # Refresh all
        stdscr.refresh();
        self.windowpanel.window.border('|', '|', '-', '-', '+', '+', '+', '+' );
        self.windowpanel.window.refresh();
        #tabwin.windowpanel.window.refresh();

        # Wait until focus gained
        #obj = None;
        #while self != obj:
        #   curses.napms(500);
        #   (t, obj) = tabs[tabpos];

        # Wait until lock acquired to get input
        #lock.acquire();
        x = stdscr.getch();
        try: k = chr(x);
        except: return True;
        #lock.release();

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

    def setmaxid(self):
        self.squid.query("select max(id) from "+self.squid.table);
        self.squid.data = self.squid.data[0];
        self.squid.data['id'] = self.squid.data['max(id)'] + 1;
        del self.squid.data['max(id)'];

    def getmaxid(self):
        return self.squid.getmaxid();


class NewWindow(ObjectWindow):

    def get_value(self):

        fieldwin = curses.newwin(1, 20, 
            self.windowpanel.coords.yoff+self.cursor.ypos+2,
            self.windowpanel.coords.xoff+self.maxkeylen+5,
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
        else: 
           #lock.acquire();
           result = notepad.edit().rstrip();
           #lock.release();

        if sqltype == "datetime":
           result = toolbelt.converters.date(result);

        if isinstance(self.squid.data, list):
           self.squid.data[self.cursor.xpos][key] = result;
        else: self.squid.data[key] = result;
        return True;


    def insert(self):
        notewin.write(self.squid.data);
        self.squid.insert(self.squid.data);


    def __init__(self, title, keybindings, squid):

        ObjectWindow.__init__(self, title, keybindings, squid);
        self.keybindings.add('\n', self.get_value, None)
        self.keybindings.add('i', self.insert, None);

        self.keys = self.squid.describe();
        self.reconstruct();


    def reconstruct(self):

        self.cursor = toolbelt.coordinates.Cursor(0, 0, 0, len(self.keys));
        self.maxkeylen = len(max(self.keys, key=len));
        self.maxkeylen = self.maxkeylen if self.maxkeylen < 20 else 20;
        self.maxvallen = 20;
        self.windowpanel.resize(
          self.maxkeylen + self.maxvallen + 20,
          len(self.keys) + 5,
          2,
          4
        );


    def gather(self, cmd):
        for i in range(len(cmd)):
            key = self.keys[i];
            self.squid.data[key] = cmd[i];


    def draw(self, args=None):

        keycode = True;
        self.setmaxid();
        self.reconstruct();

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



class EditWindow(ObjectWindow):


    def insert(self):
        self.squid.data = self.data;
        self.squid.insert();


    def view_foreignkey(self):
        key = self.keys[self.cursor.xpos];
        result = self.data[self.cursor.ypos][key];
        if not isinstance(self.squid.fields[key], tuple):
           return True;
        (squid, field) = self.squid.fields[key];
        vw = ViewWindow(squid.table, None, squid);
        args = {};
        args['sql'] = "select * from %s where %s='%s'" % (squid.table, field, result);
        vw.draw(args);
        return True;


    def view_foreignkey_table(self):
        key = self.keys[self.cursor.xpos];
        if not isinstance(self.squid.fields[key], tuple):
           return True;
        (squid, field) = self.squid.fields[key];
        ew = EditWindow(squid.table, None, squid);
        args = {};
        args['sql'] = "select * from %s" % (squid.table);
        ew.draw(args);
        return True;


    def get_value(self):

        key = self.keys[self.cursor.xpos];
        sqltype = self.squid.fields[key];

        if sqltype == "text":
           result = self.data[self.cursor.ypos][key];
           if result == None: result = "";
           result = toolbelt.editors.vim(result);
           stdscr.clear();
           stdscr.refresh();
           self.windowpanel.window.refresh();
        else: result = cmdwin.read().rstrip();

        # If it's a tuple, then it's a foreign key; tuple has (squid, field)
        # indicating which table and field the foreign key points to
        if isinstance(sqltype, tuple):
           (squid, field) = sqltype;
           save = self.data;
           try:
               squid.query('select id from %s where %s="%s"' % (squid.table, field, result));
               result = squid.data[0]['id'];
           except: result = 0;
           self.data = save;

        if sqltype == "datetime":
           result = toolbelt.converters.date(result);

        self.data[self.cursor.ypos][key] = result;

        return True;


    def asc_sort(self):
        self.data = sorted(self.data, key = lambda x: x[self.keys[self.cursor.xpos]]);
        return True;

    def desc_sort(self):
        self.data = sorted(self.data, key = lambda x: x[self.keys[self.cursor.xpos]], reverse=True);
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


    def delete_row(self):
        self.data = self.data[0:self.cursor.ypos] + self.data[self.cursor.ypos+1:];
        self.ymax -= 1;
        self.cursor.ymax -= 1;
        return True;


    def duplicate_row(self):
        maxid = self.getmaxid();
        self.data = self.data[0:self.cursor.ypos] + [self.data[self.cursor.ypos], dict(self.data[self.cursor.ypos])] + self.data[self.cursor.ypos+1:];
        self.data[self.cursor.ypos+1]['id'] = maxid;
        self.ymax += 1;
        self.cursor.ymax += 1;
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

        self.keybindings.add('a', self.view_foreignkey_table, None);
        self.keybindings.add('v', self.view_foreignkey, None);
        self.keybindings.add('i', self.insert,          None);
        self.keybindings.add('d', self.delete_row,    None);
        self.keybindings.add('y', self.duplicate_row, None);
        self.keybindings.add('\n', self.get_value, None)

        self.keys = self.squid.describe();

        self.maxkeylen = len(max(self.keys, key=len));
        self.maxkeylen = self.maxkeylen if self.maxkeylen < 20 else 20;
        self.maxvallen = 15;

        (width, height) = terminal_size();
        self.windowpanel.resize(
            width - 6,
            height - 8,
            2,
            4 
        )

    
    def gather(self, cmd):
        d = {}
        d['sql'] = 'select * from '+ self.squid.table + ' ' + " ".join(cmd);
        return d;


    def draw(self, args=None):


        if not args: args = {};
        if 'fields' in args: self.squid.fields = args['fields'];
        if not 'sql' in args: args['sql'] = cmdwin.read();
        if args['sql']=="":   args['sql']="select * from "+self.squid.table;
        notewin.write(args['sql']);
        self.squid.query(args['sql']);

        if not self.squid.data:
           if not 'data' in args:
              notewin.write("No results!");
              return;
           else: self.squid.data = args['data'];


        #if 'hidden' in args:
        #   self.hidden = args['hidden'];
        #if not hasattr(self, "hidden"):
        #   self.hidden = [];
        #if 'keys' in args:
        #   self.keys = list(set(args['keys']) - set(self.hidden));

        self.data = self.squid.data;
        self.cursor = toolbelt.coordinates.Cursor(0, len(self.keys), 0, len(self.data));

        self.xmin = self.cursor.xmin;
        self.xvis = self.windowpanel.coords.xlen / self.maxvallen - 2;
        self.xmax = self.xvis if len(self.keys) > self.xvis else len(self.keys);
        self.ymin = self.cursor.ymin;
        self.yvis = self.windowpanel.coords.ylen - 2;
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
              #notewin.write(type(self.data[0]));
              for ypos in range(self.ymin, self.ymax):
                  for xpos in range(self.xmin, self.xmax):
                      color = (self.cursor.xpos == xpos and self.cursor.ypos == ypos) + 1;
                      dat = str(self.data[ypos][self.keys[xpos]])[0:self.maxvallen-2].encode('ascii', 'ignore'),
                      numspaces = self.maxvallen - 2 - len(dat);
                      self.windowpanel.window.addstr(
                        (ypos - self.ymin)+2,
                        1+(xpos - self.xmin)*self.maxvallen,
                        "".join(dat) + ' '*numspaces,
                        curses.color_pair(color)
                      )

              keycode = self.wait();



class ViewWindow(NewWindow):


  def update(self):
      self.squid.update(self.squid.data[self.cursor.xpos]); 
      notewin.write("Updated!");
      return True;


  def __init__(self, title, keybindings, squid):

      NewWindow.__init__(self, title, keybindings, squid);
      self.keybindings = default_kb(self);
      self.keybindings.add('u', self.update, None);
      self.keybindings.add('\n', self.get_value, None)


  def gather(self, cmd):
        d = {}
        d['sql'] = 'select * from '+ self.squid.table + ' ' + "".join(cmd);
        return d;


  def draw(self, args=None):

        if not args:
           args = {};
        if not 'sql' in args:
           args['sql'] = cmdwin.read();
        if args['sql']=="": 
           args['sql']="select * from "+self.squid.table;
        self.squid.query(args['sql']);

        if self.squid.data:
           datum = self.squid.data[0]
           keys = datum.keys();
           self.cursor = toolbelt.coordinates.Cursor(0, len(self.squid.data), 0, len(keys));
           vals = map(str, datum.values());
           maxkeylen = len(max(keys, key=len));
           maxkeylen = maxkeylen if maxkeylen < 20 else 20;
           maxvallen = 20;
           self.windowpanel.resize(
             len(keys) + 5,
             maxkeylen + maxvallen + 4,
             2,
             4 
           )


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

        InteractiveWindow.__init__(self, None, None);

        (width, height) = terminal_size();
        self.windowpanel.resize(
             width - 6,
             height - 6,
             2,
             4 
        )
        self.keybindings = toolbelt.keybindings.KeyBindings();
        self.keybindings.add('\n', self.quit, None);


    def draw(self):

        mmax = len(self.msg);
        step = self.windowpanel.coords.xlen - self.windowpanel.coords.xoff*2;
        lmax = mmax / step;
        if lmax <= 0: 
           lmax = 1;
        elif lmax > self.windowpanel.coords.ylen-2:
           lmax = self.windowpanel.coords.ylen-2;

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
        self.windowpanel.resize(
             width - 4,
             3,
             2,
             height - 6,
        )
        self.linewin = curses.newwin(
          1, 
          width-8, 
          height-5, 
          10
        );
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
        nmenus = 0;
        if self.submenus: nmenus = len(self.submenus);
        self.cursor = toolbelt.coordinates.Cursor(0, 0, 0, nmenus);
        InteractiveWindow.__init__(self, title, keybindings);
        self.keybindings = default_kb(self);
        if not self.submenus: return;

        i = 0;
        maxlen = self.maxlen();
        for submenu in submenus:
            if isinstance(submenu, SubMenu):
                submenu.windowpanel.resize(
                     submenu.maxlen(),
                     len(submenu.submenus),
                     self.windowpanel.coords.xoff + maxlen,
                     self.windowpanel.coords.yoff + i 
                );
            i = i + 1;



    def delve(self, cmd):

        if len(cmd) < 1:
           self.draw();

        #notewin.write(self);
        for submenu in self.submenus:
            if submenu.title == cmd[0]:
               if isinstance(submenu, SubMenu):
                  submenu.delve(cmd[1:]);
                  return;
               else: break;

        cmd = cmd[1:];
        cmd = submenu.gather(cmd);
        submenu.draw(args=cmd);



    def command(self, cmd):

        parts = re.findall('\[[\w+\d+ ]+\]|\w+', cmd);
        cmd = [re.sub('\[|\]', '', p) for p in parts]
        #notewin.write(str(parts)+str(cmd));

        if len(cmd) < 1: 
           return;

        for submenu in self.submenus:
            if submenu.title == cmd[0]:
               self.delve(cmd);
               return;


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
        nmenus = 0 if not self.submenus else len(self.submenus);
        self.cursor = toolbelt.coordinates.Cursor(0, nmenus, 0, 0);
        self.keybindings = default_kb(self);
        (width, height) = terminal_size();
        self.windowpanel.resize(
             width-4,
             3,
             2,
             1
        )
        if not self.submenus: return;
        #tabs.append((threading.current_thread(), self));
        #tabpos = (tabpos + 1) % len(tabs);

        i = 0;
        maxlen = self.maxlen();
        for submenu in submenus:
            submenu.windowpanel.resize(
                 submenu.maxlen() + 4,
                 len(submenu.submenus) + 2,
                 4 + i * (self.maxlen()+1),
                 self.windowpanel.coords.yoff + 3
            )
            submenu.windowpanel.window.refresh();
            i = i + 1;




    def draw(self, cmd=None):

        maxlen = self.maxlen();
        keycode = True;

        while keycode:

            i = 0;
            offset = 2;
            self.windowpanel.window.clear();
            for submenu in self.submenus:
                color = (i == self.cursor.xpos) + 1;
                #print self.windowpanel.coords.yoff, self.windowpanel.coords.xoff+offset, color
                self.windowpanel.window.addstr(
                     1,
                     offset, 
                     submenu.title,
                     curses.color_pair(color)
                );
                i = i + 1;
                offset = offset + maxlen + 1;
            
            keycode = self.wait();


global tabs;
tabs = [];
class TabWindow(InteractiveWindow):

      def __init__(self):
          
          InteractiveWindow.__init__(self, "tabs", None);
          self.keybindings = default_kb(self);
          self.cursor = toolbelt.coordinates.Cursor(0, len(tabs), 0, 0);
          (width, height) = terminal_size();
          self.windowpanel.resize(
            width - 4,
            3,
            2,
            height - 3
          )



      def draw(self, cmd=None):

        maxlen = 10;

        while True:

            i = 0;
            offset = 2;
            self.cursor.xmax = len(tabs);
            self.windowpanel.window.clear();
            for tab in tabs:
                color = (i == tabpos) + 1;
                (thread, obj) = tab;
                self.windowpanel.window.addstr(
                     1,
                     offset, 
                     obj.windowpanel.title,
                     curses.color_pair(color)
                );
                i = i + 1;
                offset = offset + maxlen + 1;


            while len(tabs) != self.cursor.xmax:
                  curses.napms(1000);



# I left off at creating the 'Enter' keybinding for delving into submenus.


#t = threading.Thread(target=tabwin.draw);
#t.setDaemon(True);
#t.start();
