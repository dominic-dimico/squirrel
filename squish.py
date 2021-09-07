#!/usr/bin/python
  
import squirrel
import configparser
import sys
import smartlog
import code
import toolbelt


class SquishInterpreter(toolbelt.interpreter.Interpreter):


    def __init__(self):
        super().__init__();
        self.commands.update({
           'new' : { 
             'func' : self.create , 
             'args' :  {'obj' : None, 'sql' : ""},
             'opts' : {
                'log'  : 'Creating new object',
                'help' : 'create object',
                'fail' : 'Failed to create object',
             }
           }, 
           'edit' : {
             'func' : self.edit, 
             'args' :  {'obj' : None, 'sql' : ""},
             'opts' : {
                'log'  : 'Editing object',
                'help' : 'edit object',
                'fail' : 'Failed to create object',
             }
           }, 'view' : { 
             'func' : self.view, 
             'args' :  {'obj' : None, 'sql' : ""},
             'opts' : {
                'log'  : 'Viewing object',
                'help' : 'view object',
                'fail' : 'Failed to view object',
             }
           }, 
           'list': { 
             'func' : self.listing, 
             'args' :  {'obj' : None, 'sql' : ""},
             'opts' : {
                'log'  : 'Listing objects',
                'help' : 'list object',
                'fail' : 'Failed to list objects',
             }
           }, 
           'delete' : { 
             'func' : self.deleter, 
             'args' :  {'obj' : None, 'sql' : ""},
             'opts' : {
                'log'  : 'Deleting object',
                'help' : 'delete object',
                'fail' : 'Failed to delete object',
             }
           },
        })


    def singular(self, data):
        if not data:
           self.log.warn("No result found");
           sys.exit(1);
        if len(data) > 1: 
           self.log.warn("Multiple results");
        return data[0];


    def create(self, args):
        d = self.squid.create_defaults.copy();
        keys = self.squid.get_fields();
        d = self.log.gather(keys, q, d=d);
        self.squid.insert(d);
        self.log.info("Successfully inserted!");


    def fullsearchquery(self, args):
        if not self.squid.join_formatting:
           return "select %s from %s where %s" % ("*", self.squid.table, args['sql'])
        fs = []; # fields
        cs = []; # conditions
        for x in self.squid.list_formatting:
            fs.append(self.squid.table + '.' + x);
        for x in self.squid.join_formatting:
            fs = fs + [x['table'] + "." + y for y in x['fields']]
            cs.append("inner join %s on %s" % (x['table'], self.squid.table + '.' + x['foreignkey'] + '=' + x['table'] + '.' + x['primarykey']));
        sql = "select %s from %s %s where %s" % (", ".join(fs), self.squid.table, " ".join(cs), args['sql']);
        return sql;


    def search(self, args):
        self.squid.query(args['sql']);
        return self.squid.data;


    def quicksearch(self, args):
        q = "select * from %s where %s" % (self.squid.table, args['sql']);
        self.squid.query(q);
        return self.squid.data;


    def listing(self, args):
        if not self.prep(args): return False;
        q = self.fullsearchquery(args);
        d = self.search({'sql':q});
        d = list(d);
        ks = self.squid.get_fields();
        self.log.tabulate(self.squid.list_formatting, d);


    def view(self, args):
        if not self.prep(args): return False;
        q = self.fullsearchquery(args);
        z = self.singular(self.search({'sql':q}));
        l = max([len(k) for k in z]);
        for k in z:
            sp = ' ' * (l - len(k));
            self.log.info("%s%s: %s" % (k, sp, z[k]));


    def deleter(self, args):
        if not self.prep(args): return False;
        q = self.fullsearchquery(args);
        self.view({'sql':q});
        if self.log.yesno("Really remove"):
           q = "delete from %s where %s" % (self.squid.table, args['sql']);
           self.squid.query(q);


    def edit(self, args):
        if not self.prep(args): return False;
        d = self.singular(self.quicksearch(args));
        self.view(args);
        if self.log.yesno("Edit?"):
            keys = self.squid.get_fields();
            d = self.log.gather(keys=keys, d=d);
            self.squid.update(d);


    def prep(self, args):
        o = args['obj'];
        try:
          self.squid = self.squids[o];
          return True;
        except Exception as e:
          print(e);
          return False;

