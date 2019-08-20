#!/usr/bin/python

import sys
import json
import mysql.connector
import configparser
import code

from pprint import pprint as pp


if len(sys.argv) < 2:
   print "Require filename"
   sys.exit();


try: 
  with open(sys.argv[1]) as infile:
       data = json.load(infile);
except:
  print "File could not be opened!"


menus = ["new", "edit", "view"]


print """
#!/usr/bin/python

import squirrel
import configparser

"""


for database in data:
    for table in database["tables"]:
        print "class %s(squirrel.MySQLObj):\n  pass\n" % table.capitalize();



print """

configs = {};"""
for database in data:
    configname = database["configname"];
    print "configs['%s'] = configparser.ConfigParser()" % configname;
    print "configs['%s'].read('%s.cfg')" % (configname, configname);


print "\nobjects = {}"
for database in data:
    for table in database["tables"]:
        print "objects['%s'] = %s(configs['%s'], '%s')" % (table, table.capitalize(), database['configname'], table)

print """
x = squirrel.Menu(

      'main', [
"""


for database in data:
    for table in database["tables"]:
        outer = ',' if database["tables"][-1] != table else ''
        print """
        squirrel.Menu('%s', [
        """ % table;
        for menu in menus:
            comma = ',' if menu != 'view' else '';
            print """
            squirrel.Menu('%s', []).with_callback(
                    (objects['%s'], %s.%s_window, [])
            )%s
            """ % (menu, table, table.capitalize(), menu, comma);
        print """
        ])%s
        """ % outer;

print """
]);

x.show_main_menu();
"""
