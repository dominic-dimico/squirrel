#!/usr/bin/python
  
import squirrel
import configparser
import sys
import smartlog
import code
import copy;
import toolbelt


class SquishInterpreter(toolbelt.interpreter.Interpreter):


    def __init__(self):
        self.commands = {
           'describe' : { 
             'func' : self.describe, 
             'args' :  {'obj' : None},
             'opts' : {
                'log'  : 'Describing table',
                'help' : 'describe [object]',
                'fail' : 'Failed to describe object',
             }
           },
           'new' : { 
             'func' : self.create , 
             'args' :  {'obj' : None },
             'opts' : {
                'log'  : 'Creating new object',
                'help' : 'create [object]',
                'fail' : 'Failed to create object',
             }
           }, 
           'edit' : {
             'func' : self.edit, 
             'args' :  {'obj' : None, 'sql' : ""},
             'opts' : {
                'log'  : 'Editing object',
                'help' : 'edit   [object] [sql]',
                'fail' : 'Failed to create object',
             }
           }, 'view' : { 
             'func' : self.view, 
             'args' :  {'obj' : None, 'sql' : ""},
             'opts' : {
                'log'  : 'Viewing object',
                'help' : 'view   [object] [sql]',
                'fail' : 'Failed to view object',
             }
           }, 
           'list': { 
             'func' : self.listing, 
             'args' :  {'obj' : None, 'sql' : ""},
             'opts' : {
                'log'  : 'Listing objects',
                'help' : 'list   [object] [sql]',
                'fail' : 'Failed to list objects',
             }
           }, 
           'delete' : { 
             'func' : self.deleter, 
             'args' :  {'obj' : None, 'sql' : ""},
             'opts' : {
                'log'  : 'Deleting object',
                'help' : 'delete [object] [sql]',
                'fail' : 'Failed to delete object',
             }
           },
        }
        super().__init__();


    def gatherdata(self, args, s=None):
        if not s: s = self.squid;
        args["overwrite"] = True;
        args["postprocess_success"] = False;
        while not args["postprocess_success"]:
            args = s.preprocess(args);
            args = self.log.gather(args)
            args = s.postprocess(args);
            for key in args["postkeys"]:
                self.log.warn("%s not found" % key)
                if self.log.yesno("create"):
                   cc = copy.copy(self);
                   rarg = cc.preprocess( {
                    'data': {
                     'cmd':'new',
                     'obj': key,
                     }
                   });
                   rarg = cc.create(rarg);
        return args;


    # Allow user to specify foreign keys by field of the other table
    # Allow user to use quickdate for dates
    def create(self, args):

        args['keys'] = self.squid.form['new']['fields'];
        args['what'] = self.squid.form['new']['fields'];

        args['opts'] = {
            "types"   :  ["one"],
            "command" :  "new",
        }
        args = self.gatherdata(args);

        self.squid.insert(args['data']);
        data = args['data'];
        data['id'] = self.squid.getmaxid();

        if 'postprocessor' in self.squid.form['new']:
            args = self.squid.form['new']['postprocessor'](args);

        cargs = copy.copy(args);
        if not 'join' in self.squid.form:
           return args;

        # Load the preset data and evaluate it using previous data
        s = None;

        for join in self.squid.form['join']:

            if "new" in join:

               newdata = {}
               table = join["new"]["table"];
               if join["new"]["table"] in self.aliases:
                  table = self.aliases[join["new"]["table"]];
               s = self.squids[table];
               if "preset" in join["new"]:
                  for k in join["new"]["preset"]:
                      if join["new"]["preset"][k] in data:
                            newdata[k] = data[join["new"]["preset"][k]];
                      else: newdata[k] =      join["new"]["preset"][k];
               args["keys"] = join["new"]["gather"]; 
               if not s: return args;
               args['types']      = s.describe();
               args['data']       = newdata;
               args['overwrite']  = True;
               qd = toolbelt.quickdate.QuickDate();
               while True:
                   try:
                      args = self.gatherdata(args, s);
                      for k in args['data']:
                          if k in args['types'] and args['types'][k] == "datetime":
                             qd.set(args['data'][k]);
                             value = qd.lex;
                             args['data'][k] = value;
                      s.insert(args['data']);
                   except smartlog.QuietException:
                      break;

        if 'postpostprocessor' in self.squid.form['new']:
            args = self.squid.form['new']['postpostprocessor'](cargs);

        return args;


    def describe(self, args):
        self.log.logdata({'data': self.squid.describe()}); 


    def search(self, args):
        self.squid.query(args['sql']);
        return self.squid.data;


    def listdata(self, args):
        d = args['data'];
        if d and len(d) > 0:
           ks = d[0].keys();
        else: return args;
        d = list(d);
        self.log.tabulate(ks, d);
        return args;


    def listing(self, args):
        args['opts'] = {
            "types"   :  ["one"],
            "command" :  "view",
        }
        args['what'] = self.squid.form['list']['fields'];
        args = self.squid.fullsearchquery(args);
        return self.listdata(args);


    def searchsingle(self, args):
        args = self.squid.singular(
               self.squid.fullsearchquery(args)
        );
        return args;


    def view(self, args):
        args['what'] = self.squid.form['view']['fields'];
        self.log.logdata(
          self.searchsingle(args)
        );
        args['opts']["types"]   = ["many"];
        args['opts']["command"] = "view";
        args['sql'] = "";
        for index in range(len(self.squid.form['join'])):
            join = self.squid.form['join'][index];
            if join['type'] == "many":
               args['join_index'] = index;
               save = args['data'];
               args = self.squid.fullsearchquery(args);
               args = self.listdata(args);
               args['sql']  = ''
               args['data'] = save;
        return args;


    def deleter(self, args):
        data = self.squid.quicksearch(args)
        self.listdata(data);
        if self.log.yesno("Really remove"):
           q = "delete from %s where %s" % (self.squid.table, args['sql']);
           self.squid.query(q);
        return args;


    def edit(self, args):
        self.view(args);
        args['keys'] = self.squid.form['edit']['fields'];
        args['what'] = self.squid.form['edit']['fields'];
        if self.log.yesno("Edit?"):
            args = self.gatherdata(args);
            if 'id' not in args['what']:
                args['what'] = ['id'] + args['what'];
                args = self.searchsingle(args);
            self.squid.update(args['data']);
        self.view(args);
        return args;



    def preprocess(self, args):
        try:
          for k in args['data']:
              args[k] = args['data'][k];
          args['data'] = {};
          if 'sql' in args:
             args['sql'] += " " + " ".join(args['xs']);
             args['sql'] = args['sql'].rstrip().lstrip();
          args['xs'] = [];
          if 'obj' not in args:
             return args;
          o = args['obj']
          self.squid = self.squids[o];
          self.squid.describe();
          args['keys']  = list(self.squid.fields.keys());
          args['types'] = self.squid.fields;
          if 'opts' not in args:
              args['opts'] = {};
          args['opts']["types"] = ["one"];
          if 'squids' not in args:
             args['squids'] = self.squids;
          if 'aliases' not in args:
             args['aliases'] = self.aliases;
          return args;
        except Exception as e:
          print(e);
          return None;

