#!/usr/bin/python
import curses, curses.textpad
import sys
import signal
import locale
import time
import math
import mysql.connector
import configparser
import code
import copy

import butterfly.comms
import toolbelt

color_dark  = curses.COLOR_BLACK;
color_med   = curses.COLOR_RED;
color_light = curses.COLOR_YELLOW;
color_odd   = curses.COLOR_MAGENTA;

reload(sys)
locale.setlocale(locale.LC_ALL, 'en_US.UTF-8')
signal.signal(signal.SIGINT, signal.SIG_IGN)



def command():
    cmdpad = curses.textpad.Textbox(linewin);
    x = cmdpad.edit(validate);
    for i in range(0, len(x)):
      cmdpad.do_command(curses.KEY_BACKSPACE);
    return x



def terminal_size():
    import fcntl, termios, struct
    h, w, hp, wp = struct.unpack('HHHH',
        fcntl.ioctl(0, termios.TIOCGWINSZ,
        struct.pack('HHHH', 0, 0, 0, 0)))
    return w, h



def validate(str):
    return str;


def up(k):
    #simpleaudio.playaudio("/home/dominic/move.wav");
    return (k == curses.KEY_UP or k == ord('k'));


def down(k):
    #simpleaudio.playaudio("/home/dominic/move.wav");
    return (k == curses.KEY_DOWN or k == ord('j'));


def left(k):
    #simpleaudio.playaudio("/home/dominic/move.wav");
    return (k == curses.KEY_LEFT or k == ord('h'));


def right(k):
    #simpleaudio.playaudio("/home/dominic/move.wav");
    return (k == curses.KEY_RIGHT or k == ord('l'));

def debug(str):
    cmdwin.addstr(1, 4, str, curses.color_pair(2));


################################################################################
# For dealing with MySQL objects
################################################################################
class MySQLObj:


  data = {};
  types = None;
  table = "";
  temp = False;
  window = None;
  config = None;
  isel = 0;
  db = None;


  # FIXME
  def __init__(self, config, table):

    self.config = config;
    self.table = table;

    # Get the field types
    cursor = self.connect()
    sql = "describe "+table
    cursor.execute(sql);
    types = cursor.fetchall();
    self.types = {}
    for i in range(0, len(types)):
        self.types[types[i]["Field"]] = (types[i]["Type"],);
    
    # Get primary key information
    infodb = mysql.connector.connect(
          user=self.config['main']['user'],
          password=self.config['main']['password'],
          host=self.config['main']['host'],
          database='information_schema'
    );
    cursor = infodb.cursor(dictionary=True)
    cursor.execute("select column_name,referenced_table_name,referenced_column_name from key_column_usage where table_name='%s'" % self.table);
    results = cursor.fetchall();
    for result in results:
        (t,) = self.types[ result["column_name"] ]
        self.types[ result["column_name"] ] = (t, (result['referenced_table_name'], result['referenced_column_name']))

    #code.interact(local=locals());
    self.close();




  def connect(self):
      self.db = mysql.connector.connect(
          user=self.config['main']['user'],
          password=self.config['main']['password'],
          host=self.config['main']['host'],
          database=self.config['main']['database']
      );
      return self.db.cursor(dictionary=True)



  def clear(self):
      for key in self.data:
          self.data[key] = "";
      return;


  def close(self):
      self.db.commit();
      self.db.close();


  def insert(self):
      cursor = self.connect();
      objid = self.data.pop('id', None);
      sql = 'insert into '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in self.data))
      with open('cmd.sql', 'w') as fd: fd.write(sql);
      cursor.execute(sql, self.data.values());
      self.close();



  # FIXME
  def update(self):
      cursor = self.connect();
      sql = 'update '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in self.data))
      sql += " where id='%s'"
      with open('cmd.sql', 'w') as fd: fd.write(sql);
      cursor.execute(sql, self.data.values()+[self.data["id"]]);
      self.close();



  def do_queries(self, sqls):
      with open('cmd.sql', 'w') as fd: fd.write(str(sqls));
      cursor = self.connect();
      for sql in sqls:
        cursor.execute(sql);
      self.close();


  def redraw(self):
      stdscr.redrawwin();
      stdscr.refresh();
      cmdwin.redrawwin();
      cmdwin.refresh();
      self.window.redrawwin();



  def new_window(self):

     # FIXME: re-size if window adjusted
     (width, height) = terminal_size();
     self.window = curses.newwin(height-8, width-6, 4, 2)

     self.window.border('|', '|', '-', '-', '+', '+', '+', '+');
     self.window.keypad(True);
     self.window.refresh();


     # FIXME: should be able to override or carry menus down
     if self.temp == False:
        x = Menu("insert", []).with_callback(
               (self, MySQLObj.insert, [])
        )
     else:
        x = Menu("update", []).with_callback(
               (self, MySQLObj.update, [])
        )

     mini = Menu("option", [
               Menu("clear", []).with_callback (
                 (self, MySQLObj.clear, [])
               ),
               x
            ]);

     opts = {"sideways": True, "dig": None, "autoquit": True};


     if self.temp == False:
        self.data = dict(zip( self.types.keys(), [x[0] for x in self.types.values()] ));


     while True:
 
         i = 0;
         for key in self.data:
            color = (i == self.isel); 
            self.window.addstr(i+2, 5, key, curses.color_pair(2-int(color)));
            if self.data[key]:
                  spaces = '' if len(str(self.data[key])) >= 70 else (70-len(str(self.data[key])))*' '
                  self.window.addstr(i+2, 25, str(self.data[key])[:70]+spaces, curses.color_pair(int(color)));
            else: self.window.addstr(i+2, 25, 80*' ', curses.color_pair(int(color)));
            i += 1;
 
         self.window.refresh();
         k = stdscr.getch()
 

         # FIXME: scrolling for objects whose fields exceed height
         # Thus require imin, imax, kmin, kmax and scroller code in view_window
         if up(k):
            if self.isel > 0:
               self.isel -= 1

         elif down(k):
            if self.isel < len(self.data)-1:
               self.isel += 1


         elif k == ord(' ') or k == curses.KEY_ENTER or k == 10 or k == 13:
            key = self.data.keys()[self.isel];
            if self.types[key][0] == "text":
                dat = self.data[key];
                result = toolbelt.editors.vim(dat);
                self.redraw();
            else:
                fieldwin = curses.newwin(1, 80, self.isel+6, 27)
                notepad = curses.textpad.Textbox(fieldwin);
                result = notepad.edit();
            if self.types[key][0] == "datetime":
                result = commlib.str2dt(result);
                dtstr = str(result)
                cmdwin.addstr(1, 2, dtstr+' '*(76-len(dtstr)), curses.color_pair(2));
                cmdwin.refresh();
            elif self.types[key][0] == "blob":
                with open(result, "rb") as binary_file:
                     result = binary_file.read();
            self.data[key] = result;


         elif k == ord('e'):
            key = self.data.keys()[self.isel];
            if self.types[key][0] == "email":
               address = self.data[key];
               cmdwin.addstr(1, 1, 's>', curses.color_pair(2));
               cmdwin.refresh();
               subject = command();
               body = toolbelt.editors.vim(None);
               self.redraw();
               cmdwin.addstr(1, 1, 'a>', curses.color_pair(2));
               cmdwin.refresh();
               attach = command();
               cmdwin.addstr(1, 1, '  ', curses.color_pair(2));
               cmdwin.refresh();
               commlib.email(address, subject, body, attach);


         elif k == ord('t'):
              key = self.data.keys()[self.isel];
              if self.types[key][0] == "number" or self.types[key][0] == "phone":
                 number = data[self.isel];
                 number = str(number);
                 message = toolbelt.editors.vim(None);
                 #if not self.tx:
                 #   self.tx = commlib.Texter();
                 commlib.text(number, message);
                 self.redraw();


         elif k == ord('\t'):
            dig = command().rstrip().split(" ");
            opts["dig"] = dig;
            mini.show_submenu(opts);
            mini.window.clear();
            mini.window.refresh();

         elif k == ord('m'):
            mini.show_submenu(opts);
            mini.window.clear();
            mini.window.refresh();

         elif k == ord('q'):
            self.window.clear();
            self.window.refresh();
            break;
 


  def view_window(self):
      if self.temp == False:
         res = self.quicksearch_window();
         self.data = res[0];
      self.temp = True;
      self.new_window();
      self.temp = False;
      return;



  # should be called edit window
  def edit_window(self):

      # FIXME: the dig variable should carry to here,
      # to put query in
      res = self.quicksearch_window();
      if not res:
         return;

      self.data = res[0];
      #code.interact(local=locals());

      # FIXME: allow window size adjustment
      (width, height) = terminal_size();
      if not self.window:
          self.window = curses.newwin(height-8, width-6, 4, 2)
          self.window.border('|', '|', '-', '-', '+', '+', '+', '+');
          self.window.keypad(True);
      self.window.refresh();

      # FIXME: better names for these
      self.isel = 0;
      self.ksel = 0;

      keys = self.data.keys()
      data = [list(zip(d.values())) for d in res]

      maxlen = len(max(self.data.keys(), key=len));
      imin = kmin = 0;
      imax = len(data) if len(data) < height-9 else height-9;

      num_keys = len(keys);
      num_showable = int(math.floor((width-6)/(maxlen+2)));
      kmax = num_keys if num_keys < num_showable else num_showable;

      sqls = [];

      while True:

          k = 0;
          for k in range(kmin, kmax):
              key = keys[k];
              krel = k - kmin;
              colorpair = int(k==self.ksel) + 3;
              spaces = ' ' if (len(key) >= maxlen) else (maxlen+1-len(key))*' ';
              self.window.addstr(1, (1+krel*(maxlen+2)), key+spaces, curses.color_pair(colorpair));
          

          i = 0;
          for i in range(imin, imax):
              k = 0;
              irel = i - imin;
              for k in range(kmin, kmax):
                  krel = k - kmin;
                  colorpair = ((i==self.isel) != (k==self.ksel));
                  try:
                    if len(data[i][k]) > 1: colorpair += 5;
                  except:
                    code.interact(local=locals());
                  val = str(data[i][k][0]);
                  spaces = ' ' if (len(val) >= maxlen) else (maxlen+1-len(val))*' ';
                  vallen = len(val) if len(val) < maxlen else maxlen;
                  self.window.addstr(irel+2, (1+krel*(maxlen+2)), val[0:vallen]+spaces, curses.color_pair(colorpair));
              

          k = self.window.getch();


          # FIXME: make a global function
          def scroll(which, imin, kmin, imax, kmax):
              if which == "up":
                   if imin > 0: 
                      imin -= 1;
                      imax -= 1;
              elif which  == "down":
                   if imax < len(res) - 2: 
                      imin += 1;
                      imax += 1;
              elif which  == "right":
                   if kmax < len(res[0]):
                      kmax += 1;
                      kmin += 1;
              elif which == "left":
                   if kmin > 0:
                      kmax -= 1;
                      kmin -= 1;
              return (imin, kmin, imax, kmax);
              

          n = 1;

          if k < 255 and chr(k).isdigit():
             num = ""
             while chr(k).isdigit():
                   num += chr(k);
                   k = self.window.getch();
             n = int(num)
          
          for i in range(0, n):

              if up(k):
                 if self.isel > 0:
                    self.isel -= 1;
                    if self.isel <= imin:
                        (imin, kmin, imax, kmax) = scroll(
                           "up", imin, kmin, imax, kmax
                        );

              elif k == ord('K'):
                        (imin, kmin, imax, kmax) = scroll(
                           "up", imin, kmin, imax, kmax
                        );

              elif down(k):
                 if self.isel < len(res)-1:
                    self.isel += 1;
                    if self.isel >= imax-3:
                           (imin, kmin, imax, kmax) = scroll(
                             "down", imin, kmin, imax, kmax
                           );

              elif k == ord('J'):
                        (imin, kmin, imax, kmax) = scroll(
                           "down", imin, kmin, imax, kmax
                        );

              elif right(k):
                 if self.ksel < len(res[0])-1:
                    self.ksel += 1;
                    if self.ksel >= kmax-1:
                           (imin, kmin, imax, kmax) = scroll(
                             "right", imin, kmin, imax, kmax
                           );

              elif k == ord('L'):
                        (imin, kmin, imax, kmax) = scroll(
                           "right", imin, kmin, imax, kmax
                        );

              elif left(k):
                 if self.ksel > 0:
                    self.ksel -= 1;
                    if self.ksel <= kmin:
                           (imin, kmin, imax, kmax) = scroll(
                             "left", imin, kmin, imax, kmax
                           );

              elif k == ord('H'):
                        (imin, kmin, imax, kmax) = scroll(
                           "left", imin, kmin, imax, kmax
                        );


          if k == ord('v'):
               key = keys[self.ksel];
               val = data[self.isel][self.ksel][0];
               if len(self.types[key]) > 1:
                  (tab, col) = self.types[key][1];
                  sql = "select * from %s where %s='%s'" % (tab, col, val)
                  cursor = self.connect();
                  cursor.execute(sql);
                  results = cursor.fetchall();
                  result = results[0];
                  other = MySQLObj(self.config, tab);
                  other.data = result;
                  other.temp = True;
                  other.view_window();
                  other.temp = False;
               else:
                   row = [x[0] for x in data[self.isel]];
                   self.data = dict(zip(keys, row))
                   self.temp = True;
                   self.view_window();
                   self.temp = False;


          # FIXME: handle non-comparables
          elif k == ord('>'):
               data.sort(key = lambda x:x[self.ksel]);


          elif k == ord('<'):
               data.sort(key = lambda x:x[self.ksel], reverse=True);


          elif k == ord('c'):
               row = copy.copy(data[self.isel]);
               cursor = self.connect();
               cursor.execute("select max(id) from "+self.table);
               result = cursor.fetchall();
               maxid = int(result[0]['max(id)']) + 1;
               idkey = keys.index("id");
               self.close();
               row[idkey] = (maxid,);
               if self.isel==0:
                  data = [row] + data[0:len(data)];
               elif self.isel == len(data)-1:
                  data = data[0:len(data)] + [row];
               else:
                  data = data[0:self.isel] + [row] + data[self.isel:len(data)]
               sqls.append(
                 'insert into '+self.table+' default values'
               );



          elif k == ord('d'):
               if self.isel==0:
                  data = data[1:len(data)];
               elif self.isel == len(data)-1:
                  data = data[0:len(data)-1];
               else:
                  data = data[0:self.isel] + data[self.isel+1:len(data)]
               idkey = keys.index("id");
               sqls.append(
                 "delete from %s where id='%s'" % (self.table, data[self.isel][idkey])
               );



          elif k == ord('e'):
               key = keys[self.ksel];
               if key == "email":
                  address = data[self.isel][self.ksel][0];
                  cmdwin.addstr(1, 1, 's>', curses.color_pair(2));
                  cmdwin.refresh();
                  subject = command();
                  body = toolbelt.editors.vim(None);
                  self.redraw();
                  cmdwin.addstr(1, 1, 'a>', curses.color_pair(2));
                  cmdwin.refresh();
                  attach = command();
                  cmdwin.addstr(1, 1, ' >', curses.color_pair(2));
                  cmdwin.refresh();
                  commlib.email(address, subject, body, attach);


          elif k == ord('t'):
               key = keys[self.ksel];
               if key == "number" or key == "phone":
                  number = data[self.isel][self.ksel][0];
                  number = str(number);
                  message = toolbelt.editors.vim(None);
                  #if 'self.tx' not in vars():
                  #   self.tx = commlib.Texter();
                  commlib.text(number, message);
                  self.redraw();

 
          elif k == ord(' ') or k == curses.KEY_ENTER or k == 10 or k == 13:
               key = self.data.keys()[self.ksel];
               if self.types[key][0] == "text":
                  text = data[self.isel][self.ksel][0];
                  value = toolbelt.editors.vim(text);
                  self.redraw();
               else: value = command();
               if self.types[key][0] == "datetime":
                  value = commlib.str2dt(value);
                  dtstr = str(value)
                  cmdwin.addstr(1, 4, dtstr+' '*(76-len(dtstr)), curses.color_pair(2));
                  cmdwin.refresh();
               elif self.types[key][0].endswith("blob"):
                    with open(value, "rb") as binary_file:
                         value = binary_file.read();
               data[self.isel][self.ksel] = (value,1);
               idkey = keys.index("id");
               sqls.append('update {} set {}="{}" where id={}'.format(
                   self.table, key, value, data[self.isel][idkey]
                 )
               )
                 

          # FIXME: print results
          elif k == ord('s'):
               self.do_queries(sqls);
               for i in range(len(data)):
                   for k in range(len(data[0])):
                       val = data[i][k][0]
                       data[i][k] = (val,)
               sqls = [];


          elif k == ord('q'):
             self.window.clear();
             self.window.refresh();
             self.isel = 0;
             break;
            

      return;


  # Should show a spreadsheet-style window.  Clicking a key should order 
  # dictionary by that key (simple enough function to write).  Clicking a field
  # will allow editing that field.  'e' should open edit menu on object.
  def list_window(self):
      return;



  def quicksearch_window(self):
      clause = command();
      cursor = self.connect();
      sql = "select * from "+self.table+" "+clause;
      cursor.execute(sql);
      res = cursor.fetchall();
      self.db.close();
      with open('search.sql', 'w') as fd: fd.write(str(res));
      return res;



################################################################################
# For dealing with ncurses menus
################################################################################
class Menu:



  selection = 0;
  title = "";
  submenus = [];
  ycoord = 2;
  obj = None;
  opts = {};
  callback = None;
  kwargs = None;
  window = None;



  def with_callback(self, x):
    (obj, callback, kwargs) = x
    self.obj = obj;
    self.callback = callback;
    self.kwargs = kwargs;
    return self;



  def __init__(self, title, submenus):
    self.title = title;
    self.submenus = submenus;
    if self.submenus:
       lastycoord = self.ycoord; 
       for i in range(len(self.submenus)):
           submenus[i].ycoord = lastycoord;
           lastycoord += len(submenus[i].title) + 4;



  def activate(self):
    if self.callback:
       self.callback(self.obj);



  def submenu_str():
    string_list = []
    for submenu in submenus:
        string_list.append(submenu.title);
    return string_list;



  def show_main_menu(self):

    global stdscr, cmdwin, linewin;

    stdscr = curses.initscr()
    stdscr.keypad(True);
    stdscr.border('|', '|', '-', '-', '+', '+', '+', '+');
    self.window = stdscr;

    (width, height) = terminal_size();
    cmdwin = curses.newwin(3, width-6, height-4, 2)
    linewin = curses.newwin(1, width-10, height-3, 6);
    cmdwin.border(0);

    curses.start_color()

    # FIXME: override these
    curses.init_pair(1, 
      curses.COLOR_WHITE,
      color_med
    )

    curses.init_pair(2, 
      color_med,
      curses.COLOR_BLACK
    )

    curses.init_pair(4, 
      curses.COLOR_BLACK,
      color_light
    )

    curses.init_pair(3, 
      color_light,
      curses.COLOR_BLACK
    )

    curses.init_pair(5,
      color_odd,
      curses.COLOR_BLACK
    )

    curses.init_pair(6,
      curses.COLOR_WHITE,
      color_odd
    )

    curses.noecho()
    curses.cbreak()

    # FIXME: window adjustments
    rail = (width-2)*'-'
    stdscr.addstr(1, 1, rail, curses.color_pair(2));
    stdscr.addstr(3, 1, rail, curses.color_pair(2));
    stdscr.refresh();

    cmdwin.border(0);
    cmdwin.addstr(1, 2, ">", curses.color_pair(2));
    cmdwin.refresh();

    opts = {"sideways": True, "dig": None};
    self.show_submenu(opts);



  def show_submenu(self, opts):

    #simpleaudio.playaudio("/home/dominic/open.wav");

    if "dig" in opts:
      dig = opts["dig"];
    else: dig = None;

    if "sideways" in opts:
      sideways = opts["sideways"];
    else: sideways = False;

    if "animate" in opts:
      animate = opts["sideways"];
    else: animate = False;

    if "autoquit" in opts:
      autoquit = opts["sideways"];
    else: autoquit = False;


    if not self.window:
        self.window = curses.newwin(len(self.submenus)+4, 30, 4, self.ycoord)
        self.window.border(0);
        self.window.keypad(True);


    while True:

        cmdwin.border(0);
        cmdwin.addstr(1, 2, ">", curses.color_pair(2));
        cmdwin.refresh();

        if animate:
           i = 0;
           for submenu in self.submenus:
             if sideways:
                self.window.addstr(2, submenu.ycoord, submenu.title, curses.color_pair(2));
             else: self.window.addstr(i+2, 3, submenu.title, curses.color_pair(2));
             i += 1;
             self.window.refresh();
             time.sleep(.1);
           self.window.border(0);
           self.window.refresh();
           time.sleep(.3);


        i = 0;
        for submenu in self.submenus:
            if (dig and dig[0] == submenu.title) or (self.selection == i):
                  self.selection = i;
                  colorpair = 1;
            else: colorpair = 2;
            if sideways:
                  self.window.addstr(2, submenu.ycoord, submenu.title, curses.color_pair(colorpair));
            else: self.window.addstr(i+2, 3, submenu.title, curses.color_pair(colorpair));
            i += 1;


        self.window.border(0);
        self.window.refresh();
        

        if dig:
           if animate: time.sleep(.3);
           submenu = self.submenus[self.selection];
           submenu.activate();
           if submenu.submenus:
              subopts = {
                "sideways":False, 
                "dig":dig[1:], 
                "animate":animate, 
                "autoquit": autoquit
              };
              submenu.show_submenu(subopts);
           elif autoquit:
             self.window.clear();
             self.window.refresh();
             break;
           dig = None;
           self.window.border(0);
           self.window.refresh();


        cmdwin.border(0);
        cmdwin.addstr(1, 2, ">", curses.color_pair(2));
        cmdwin.refresh();


        k = stdscr.getch()

        if (up(k) and not opts["sideways"]) or (left(k) and opts["sideways"]):
          if self.selection > 0:
             self.selection -= 1;

        elif (down(k) and not opts ["sideways"]) or (right(k) and opts["sideways"]):
             if self.selection < len(self.submenus)-1:
                self.selection += 1;

        elif (left(k) and not opts ["sideways"]) or (up(k) and opts["sideways"]) or (right(k) and not opts ["sideways"]):
             if self.title is not "main":
                self.window.clear();
                self.window.refresh();
                curses.ungetch(k);
                break;

        elif k == ord(' ') or k == curses.KEY_ENTER or k == 10 or k == 13 or (down(k) and opts["sideways"]):
             if self.submenus:
                subopts = {"sideways":False, "dig":None};
                submenu = self.submenus[self.selection];
                submenu.activate();
                if submenu.submenus:
                   submenu.show_submenu(subopts);

        elif k == ord('\t') and self.title == "main":
             dig = command().rstrip().split(" ");
             continue;

        elif k == ord('q'):
             self.window.clear();
             self.window.refresh();
             break;


        self.window.border(0);
        self.window.refresh()
        cmdwin.border(0);
        cmdwin.addstr(1, 2, ">", curses.color_pair(2));
        cmdwin.refresh();
 


  def exit(self):

    stdscr.keypad(False);
    curses.nocbreak();
    curses.echo();
    curses.resetty();
    curses.endwin();
    sys.exit();

