#!/usr/bin/python

import sys
import json
import MySQLdb
import configparser
import code
import getopt
format_ = format

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

  
  print("""#!/usr/bin/python
  
import squirrel
import configparser
import sys
import smartlog
import code

log = smartlog.Smartlog();

  """);
  
  
  for database in data:
      for table in database["tables"]:
          print("class %s(squirrel.squid.Squid):" % table.capitalize());
          for el in ['list', 'view', 'join']:
              print("  %s_format = [];" % (el));
          print("  def __init__(self, config, table):");
          print("    super().__init__(config, table);\n\n");
  
  
  
  print("""
configs = {};""");
  for database in data:
      configname = database["configname"];
      print("configs['%s'] = configparser.ConfigParser()" % configname);
      print("configs['%s'].read('%s.cfg')" % (configname, configname));
  
  
  print("\nsquids= {}")
  for database in data:
      for table in database["tables"]:
          print("squids['%s'] = %s(configs['%s'], '%s')" % (table, table.capitalize(), database['configname'], table))
    
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

def singular(d):
    if not d:
       log.warn("No result found");
       sys.exit(0);
    if len(d) > 1: 
       log.warn("Multiple results");
    return d[0];


def create(s):
    d = s.create_defaults.copy();
    keys = s.describe();
    d = log.gather(keys, q, d=d);
    s.insert(d);
    log.info("Successfully inserted!");


def fullsearchquery(s, q):
    if not s.format['join']:
       return "select %s from %s where %s" % ("*", s.table, q)
    fs = []; # fields
    cs = []; # conditions
    for x in s.format['join']:
        fs = fs + [x['table'] + "." + y for y in x['fields']]
        cs.append("inner join %s on %s" % (x['table'], s.table + '.' + x['foreignkey'] + '=' + x['table'] + '.' + x['primarykey']));
    sql = "select %s from %s %s where %s" % (", ".join(fs), s.table, " ".join(cs), q);
    return sql;


def search(s, q=None):
    if not q: q = log.prompt("sql");
    s.query(q);
    return s.data;


def quicksearch(s, q=None):
    if not q: q = log.prompt("sql");
    q = "select * from %s where %s" % (s.table, q);
    s.query(q);
    return s.data;


def listing(s, q=None):
    if not q: q = log.prompt("sql");
    q = fullsearchquery(s, q);
    d = search(s, q);
    d = list(d);
    ks = s.describe();
    log.tabulate(s.format['list'], d);
    pass


def view(s, q=None):
    if not q: q = log.prompt("sql");
    q = fullsearchquery(s, q);
    z = singular(search(s, q));
    l = max([len(k) for k in z]);
    for k in z:
        sp = ' ' * (l - len(k));
        log.info("%s%s: %s" % (k, sp, z[k]));


def deleter(s, q=None):
    if not q: q = log.prompt("sql");
    q = fullsearchquery(s, q);
    d = singular(quicksearch(s, q));
    view(s, q);
    if log.yesno("Really remove"):
       q = "delete from %s where %s" % (s.table, q);
       s.query(q);


def edit(s, q=None):
    if not q: q = log.prompt("sql");
    d = singular(quicksearch(s, q));
    view(s, q);
    if not log.yesno("Edit?"):
       return;
    keys = s.describe();
    d = log.gather({
        'keys'       : keys, 
        'dict' : d,
        'opts'       : {
           'overwrite' : True,
        }
    );
    s.update(d);


def ungather(c):
    try:
      s = squids[c['obj']]
    except Exception as e:
      print(e);
      return False;
    q = " ".join(c['xs']);
    return (s, q);


c = { 'obj' : None };
while not c['obj']:

      args = log.gather({
             'keys' : ['cmd'], 
             'xs'   : sys.argv[1:],
          );
      if args['data']['cmd'] == \"quit\":
         sys.exit(0);
      elif args['data']['cmd'] == \"help\":
         sys.exit(0);

      c = log.gather(c)

      try:
         (s, q) = ungather(c['dict']);
      except Exception as e:
         print(e);
         continue;
""");

    counter = 1;
    for menu in menus:
       if counter == 1:
          print("      if c['cmd'] == \"%s\":" % (menu));
       else: print("      elif c['cmd'] == \"%s\":" % (menu));
       print("         %s(s, q);"           % (menu));
       counter += 1;

    print("\n      else: \n");
    print("          log.warn(\"No such command\"); \n");

if __name__ == "__main__":
   main();
