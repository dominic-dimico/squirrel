#!/usr/bin/python

import sys
import json
import MySQLdb
import configparser
import code
import getopt

from pprint import pprint as pp


def main():

  cli = False;
  try:
    opts, args = getopt.getopt(
      args=sys.argv[1:],
      shortopts="cf:",
      longopts=["cli","filename="]
    );
  except getopt.GetoptError as err:
    print(str(err))
    usage()
    sys.exit(2)
  for option, value in opts:
    #print(option, value);
    if option in ("-c", "--cli"):
       cli = True
    elif option in ["-f", "--filename"]:
       filename = value
       #print(filename);
    else:
       #assert False, "unhandled option"
       print (option, value);
       pass

  try: 
    with open(filename) as infile:
         data = json.load(infile);
  except:
    print("File could not be opened!")
  
  menus = ["new", "edit", "view", "list", "delete"]

  
  print("""
#!/usr/bin/python
  
import squirrel
import configparser
import sys

  """);
  
  
  for database in data:
      for table in database["tables"]:
          print("class %s(squirrel.squid.Squid):\n  pass\n" % table.capitalize());
  
  
  
  print("""
configs = {};""");
  for database in data:
      configname = database["configname"];
      print("configs['%s'] = configparser.ConfigParser()" % configname);
      print("configs['%s'].read('%s.cfg')" % (configname, configname));
  
  
  print("\nobjects = {}")
  for database in data:
      for table in database["tables"]:
          print("objects['%s'] = %s(configs['%s'], '%s')" % (table, table.capitalize(), database['configname'], table))
    
  if not cli: 

    print("""
    
(cmdwin, notewin, tabwin) = squirrel.squint.startup();
    
x = squirrel.squint.MainMenu(
    
  [
    """);
    
    
    for database in data:
    
        for table in database["tables"]:
            outer = ',' if database["tables"][-1] != table else ''
            print("""
            squirrel.squint.SubMenu('%s', None, [
            """ % table);
            for menu in menus:
                comma = ',' if menu != 'view' else '';
                print("""
                squirrel.squint.%s('%s', None, objects['%s'])%s
                """ % (menu+"Window", menu, table, comma));
            print("""
            ])%s
            """ % outer);
    
    print("""
    ]);
    
    x.draw();
    """);

  else:
  
    print("""
def gather(keys):
    d = {};
    for key in keys:
        print("%s: " % key);
        x = sys.stdin.readline();
        d[key] = x;
    return d;

def create(s):
    d = {};
    keys = s.get_fields();
    d = gather(keys);
    s.insert(d);

def search(s, d):
    print("sql> ");
    query = sys.stdin.readline();
    s.query(query, d);
    return s.data;

def list(s):
    d = {};
    d = search(s, d);
    for x in d:
        for k in x:
            print("%s: %s" % (k, x[k]));

def view(s):
    d = {};
    d = search(s, d);
    for x in d:
        for k in x:
            print("%s: %s" % (k, x[k]));

def delete(s):
    pass

def edit(s):
    pass

def update(s):
    keys = s.get_fields();
    d = gather(keys);
    s.update(d);

""");
    print("command = ['command', 'object']");
    print("while True:\n");
    print("  cmd = sys.stdin.readline().split();\n");
    print("  if cmd[0] == \"quit\":");
    print("     sys.exit(0);");
    for menu in menus:
        print("\n  elif cmd[0] == \"%s\":" % (menu));
        for database in data:
            counter = 1;
            for table in database["tables"]:
                if counter == 1:
                  print("     if cmd[1] == \"%s\":" % (table));
                else:
                  print("     elif cmd[1] == \"%s\":" % (table));
                if   menu=="new":     print("          create(objects['%s'])" % table);
                elif menu=="edit":    print("          edit(objects['%s'])" % table);
                elif menu=="view":    print("          view(objects['%s'])" % table);
                elif menu=="list":    print("          list(objects['%s'])" % table);
                elif menu=="delete":  print("          delete(objects['%s'])" % table);
                counter = counter + 1;

if __name__ == "__main__":
   main();
