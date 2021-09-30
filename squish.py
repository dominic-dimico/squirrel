#!/usr/bin/python
  
import squirrel
import configparser
import sys
import smartlog
import code
import copy;
import toolbelt
format_ = format

quickdate = toolbelt.quickdate.quickdate;
_list = list

class Squish(squirrel.squid.Squid):
    """ Squid for CLI usage with smartlog
    """

    def __init__(self, config=None, table=''):
        super().__init__(config, table);


    def gatherdata(self, args, s=None):
        if not s: s = self;
        args = self.log.argcheck(args, {
            "method"    :           {'overwrite': 'linear'},
            "overwrite" :           {'overwrite': True},
            "postprocess_success" : {'overwrite': False}
        });
        while not args["postprocess_success"]:
            args = s.preprocessfk(args);
            args = self.log.gather(args)
            self.log.info('after gather');
            args = s.postprocessfk(args);
            self.log.info('after postprocfk');
            for key in args["postkeys"]:
                self.log.warn("%s not found" % key)
                if self.log.yesno("create"):
                   cc = copy.copy(self);
                   # TODO
                   cc.create(cc.preprocess( { 
                     'data': { 'cmd':'new',
                               'obj': key,
                   }}));
            self.log.info('before return');
        return self.log.argcheck(args, {
            'delete' : ["postprocess_success", "postkeys"]
        });



    # TODO: handle aliases
    # Make aliases a list in the class?
    def alias_of(self, table):
        if table in self.db.aliases:
           return self.db.aliases[table];
        else: return table;


    def check_condition(self, args, format):
        if not 'condition' in format: return True;
        condition = format['condition'].split('=');
        v1 = condition[0];
        v2 = condition[1];
        if v2 in args['data']:
              return args['data'][v1] == args['data'][v2];
        else: return args['data'][v1] == v2;



    def create_with_format(self, args, format):
       if not self.check_condition(args, format):
          return args;
       ar   = self.load_format(args, format);
       ar   = self.load_presets(ar, format);
       sq   = self.db.squids[ar['alias']];
       ar   = self.log.argcheck(ar, { # Prep to gather data
           'overwrite'  : {'overwrite' : True},
       });
       number = 1;
       if 'number' in format:
           number = format['number']; 
       while number != 0:
           try:
              if 'preprocessor' in args['format']:
                  ar = args['format']['preprocessor'](ar);
              ar = self.gatherdata(ar, sq);
              if 'midprocessor' in args['format']:
                  ar = args['format']['midprocessor'](ar);
              for k in ar['data']:
                 if (k in ar['types'] and "datetime" == ar['types'][k]):
                     ar['data'][k] = quickdate(ar['data'][k]);
              sq.insert(ar['data']);
              if 'postprocessor' in args['format']:
                 self.log.info("calling postprocessor");
                 ar = args['format']['postprocessor'](ar);
              if number>0:
                 number = number - 1;
           except Exception as e:
              print(e);
       return args;



    def join_new(self, args):
        if not 'join' in self.format:
           return args;
        for join in self.format['join']:
            if 'new' in join:
               format = join['new'];
               self.create_with_format(args, format);
        args['format'] = self.format;
        return args;




    def create(self, args={'return': False}):
        args = self.log.argcheck(args, {
          'format' : {'default' : self.format['new']}, 
          'opts' : {'default' : {}},
        });
        args = self.log.argcheck(args, {
          'keys' : {'default' : args['format']['fields']},
          'what' : {'default' : args['format']['fields']},
        });
        args['opts'] = self.log.argcheck(args['opts'], {
          'types'   : {'default'   : ["one"]},
          'command' : {'overwrite' :  'new' },
        });
        if 'prepreprocessor' in args['format']:
            args = args['format']['prepreprocessor'](args);
        args = self.create_with_format(args, args['format']);
        if 'data' not in args: args['data'] = {};
        args['data']['id'] = self.getmaxid();
        args = self.join_new(args);
        if 'postpostprocessor' in args['format']:
            args = args['format']['postpostprocessor'](args);
        if 'return' in args and not args['return']: 
            self.log.argcheck(args, {
              'delete' : ['keys', 'data', 'sql', 'opts', 'what', 'format'],
            });
            return;
        return args;



    def describe(self, args):
        self.log.logdata({'data': self.describe_table()}); 


    def search(self, args):
        args = self.log.argcheck(args, {
          'require' : ['sql'],
        })
        self.query(args['sql']);
        return self.data;


    def listdata(self, args):
        args = self.log.argcheck(args, {
           'require' : ['data'],
        });
        d = args['data'];
        if d and len(d) > 0:
           ks = d[0].keys();
        else: return args;
        d = _list(d);
        self.log.tabulate(ks, d);
        return args;


    def list(self, args={'return':False}):
        if not 'format' in args:
           args = self.log.argcheck(args, {
              'format' : {'default' : self.format['list']},
              'sql'  : {'default' : '', 'gather': 'always'},
           });
        self.log.print(args);
        args = self.log.argcheck(args, {
            'backup' : ['opts', 'what'],
            'opts'   : {'overwrite' : {"types":["one"], "command":"view"}},
            'what'   : {'default' : args['format']['fields']},
        });
        args = self.fullsearchquery(args);
        args = self.listdata(args);
        if 'return' in args and not args['return']: 
            self.log.argcheck(args, {
              'delete' : ['keys', 'data', 'sql', 'opts', 'what', 'format'],
            });
            return;
        return self.log.argcheck(args, {
             'restore' : ['opts', 'what']
        });


    def searchsingle(self, args):
        args = self.singular(
               self.fullsearchquery(args)
        );
        return args;


    def viewjoin(self, args):
        args = self.log.argcheck(args, {
           'clear'  : ['sql'],
           'opts'   : {'overwrite':  {'types':['many'],'command':'view'},},
        });
        for index in range(len(self.format['join'])):
            join = self.format['join'][index];
            if join['type'] == "many":
               args['join_index'] = index;
               args = self.fullsearchquery(args);
               args = self.listdata(args);
        return args;


    def view(self, args={'return': False}):
        args = self.log.argcheck(args, {
            'format' : {'default' : self.format['view']},
        });
        #self.log.print(args);
        args = self.log.argcheck(args, {
            'keys' : {'default': args['format']['fields']},
            'what' : {'default': args['format']['fields']},
            'join' : {'default': True},
            'sql'  : {'require': True, 'gather': 'maybe'},
            'opts' : {'default': {'types': ['one'], 'command': 'view'}},
        });
        args = self.searchsingle(args)
        if args['data']:
              self.log.logdata(args);
              if args['join']:
                 args = self.log.copyback( args,
                        ['keys', 'data', 'what', 'opts', 'sql'],
                        self.viewjoin
                 );
        else:  self.log.warn("Not found");
        if 'return' in args and not args['return']:
            self.log.argcheck(args, {
              'delete' : ['keys', 'data', 'sql', 'opts', 'what', 'format'],
            });
            return;
        return self.log.argcheck(args, {
               'join' : {'delete'   : True},
        });


    def deleter(self, args={'return': False}):
        args = self.log.argcheck(args, {
           'data' : {'overwrite' : self.quicksearch(args)},
           'format' : {'overwrite' : self.format['list']},
           'sql'  : {'require'   : True},
        });
        args = self.load_format(args, args['format']);
        args = self.purify(args);
        args = self.listdata(args);
        if self.log.yesno("Really remove"):
           q = "delete from %s where %s" % (self.table, args['sql']);
           self.query(q);
        if 'return' in args and not args['return']: 
            self.log.argcheck(args, {
              'delete' : ['keys', 'data', 'sql', 'opts', 'what', 'format'],
            });
            return;
        return args;


    def purify(self, args):
        args = self.log.argcheck(args, {
           'require' : ['data', 'keys'],
        });
        nd = [];
        fs = [];
        single=False;
        if isinstance(args['data'], dict):
           args['data'] = [args['data']];
           single=True;
        for i in range(len(args['data'])):
            nd.append({});
            for field in args['data'][i].keys():
                if field in args['keys']:
                   nd[i][field] = args['data'][i][field];
        args['data'] = nd;
        if single: 
           args = self.singular(args); 
        return self.log.argcheck(args, {
           'require' : ['data', 'keys'],
        });



    def __edit_keys(self, args):
        if 'argspec' not in args: return;
        # We don't have to dropna
        df = args['argspec'].dropna(subset=['data']);
        for i in range(len(df)):
          if df.loc[i, 'key'] == 'field':
             if df.loc[i, 'data'] and df.loc[i, 'object']:
                if df.loc[i, 'object'] == args['obj']:
                   df.loc[i, 'data'];
        


    def edit(self, args={'return': False}):
        args = self.log.argcheck(args, {
            'format' : {'default' : self.format['edit']}
        });
        args = self.log.argcheck(args, {
            'keys' : {'default': args['format']['fields']},
            'what' : {'default': args['format']['fields']},
            'join' : {'default': False},
            'sql'  : {'require': True, 'gather': 'maybe'},
        });
        self.log.copyback(args, ['keys'], self.list);
        if len(args['data'])==1:
           self.log.logdata({'data':args['data'][0]})
        if args['data'] and self.log.yesno("Edit?"):
            try:
                searchargs = copy.copy(args);
                searchargs = self.fullsearchquery(
                    self.log.argcheck(searchargs, {
                         'keys' : {'overwrite': ['id']},
                         'what' : {'overwrite': ['id']}
                    })
                );
                print(searchargs);
                args = self.log.argcheck(args, {
                  'backup': ['keys', 'data', 'sql', 'opts', 'what'],
                });
                #args = self.gatherdata(args);
                if len(args['data']) == 1:
                    xs = self.log.selector(args['data'][0]);
                    data = [xs.edit()]; 
                else:
                    xs = self.log.xselector(args['data']);
                    data = list(xs.edit());
                for i in range(len(data)):
                      sargs = self.purify({
                           'keys' : args['keys'],
                           'data' : data[i], 
                      });
                      sargs['data']['id'] = searchargs['data'][i]['id'];
                      self.update(sargs['data']);
                      if 'postprocessor' in args['format']:
                         args = args['format']['postprocessor'](args);
                args = self.log.argcheck(args, {
                  'restore': ['keys', 'data', 'sql', 'opts', 'what'],
                  'join'   : {'default': False},
                });
                self.list(args);
                if len(args['data'])==1:
                   self.log.logdata({'data':args['data'][0]})
            except Exception as e:
               import traceback; 
               traceback.print_exc();
        if 'return' in args and not args['return']: 
            self.log.argcheck(args, {
              'delete' : ['keys', 'data', 'sql', 'opts', 'what', 'format'],
            });
            return;
        return args;


    def load_format(self, args, format):
        format = self.log.argcheck(format,{
            'table'  : {'default':self.table},
            'fields' : {'require':True},
        });
        alias = self.alias_of(format['table']);
        return self.log.argcheck(args, {
           'table' : {'overwrite': format['table']},
           'keys'  : {'overwrite': format['fields']},
           'types' : {'overwrite': self.db.squids[alias].describe_table()},
           'alias' : {'overwrite': alias},
        });


    def load_presets(self, args, format):
        new_data = {};
        if 'preset' in format:
            args = self.log.argcheck(args, {
               'data'      : {'default': {}}, 
               'overwrite' : {'default': False},
               'dates'     : {'default': False},
            });
            preset = format["preset"];
            for k in preset:
                if preset[k] in args['data']: 
                      new_data[k] = args['data'][preset[k]];
                else: new_data[k] = preset[k];
                if args['dates'] and (k in args['types'] and "datetime" == args['types'][k]):
                   new_data[k] = toolbelt.quickdate.quickdate(new_data[k]);
        args['data'] = new_data;
        return args;



class SquishInterpreter(toolbelt.interpreter.Interpreter):


    def __init__(self):
        if not self.commands:
           self.commands = {};
        self.commands.update({
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
           'query' : { 
             'func' : self.query, 
             'args' :  {'obj' : None, 'sql' : ""},
             'opts' : {
                'log'  : 'Querying object',
                'help' : 'query [object] [sql]',
                'fail' : 'Failed to query object',
             }
           },
        });
        super().__init__();


    def initialize_autocomplete(self):

        import re
        objects          = self.objects;
        commands         = [key for key in self.commands];

        self.auto.words   = [];
        self.auto.words  += commands;
        self.auto.words  += objects;
        self.auto.words  += ['where', 'order', 'by'];

        cmdpat     = "|".join(commands);
        objectpat  = "|".join(objects);
        sqlpat     = ".*"
        orderpat   = "order.*"

        if not hasattr(self,'argspec'):
           self.argspec = [];
        self.argspec += [
            {
              'key'      : 'cmd',
              'pattern'  : re.compile(cmdpat), 
              'optional' : False,
              'consume'  : True,
            }, {
              'key'      : 'obj',
              'pattern'  : re.compile(objectpat), 
              'optional' : True,
              'consume'  : True,
            }, {
              'key'      : 'sql',
              'pattern'  : re.compile(sqlpat), 
              'optional' : True,
              'exclude'  : re.compile(cmdpat+"|"+objectpat),
            }, {
              'key'      : 'order',
              'pattern'  : re.compile(orderpat), 
              'optional' : True,
            }
        ];


        # All field names of all tables
        words = [];
        for alias in objects:
            ts      = self.squids[alias].describe_table();
            words   = ts.keys();
            pattern = "|".join(words);
            self.auto.words += list(set(words)-set(self.auto.words));
            self.argspec    += [{
              'key'      : 'field',
              'pattern'  : re.compile(pattern),
              'optional' : True,
              'object'   : alias,
            }];


        for t in self.ts:
            words = [];
            self.squids[t].query(
               'select %s from %s' % (",".join(self.ts[t]), self.squids[t].table)
            );
            import pandas;
            df = pandas.DataFrame(self.squids[t].data);
            df.fillna("",inplace=True)
            for c in df.columns:
                ws = df[c].to_list();
                words += ws;
                try:     pat = "|".join(ws);
                except:  pat = '';
                self.argspec += [{
                  'key'      : c,
                  'pattern'  : re.compile(pat),
                  'optional' : True,
                  'object'   : t,
                }];
                self.auto.words += words;



    def create(self, args):
        return self.squid.create(args);

    def edit(self, args):
        return self.squid.edit(args);

    def view(self, args):
        return self.squid.view(args);

    def listing(self, args):
        return self.squid.list(args);

    def describe(self, args):
        return self.squid.describe(args);

    def deleter(self, args):
        return self.squid.deleter(args);

    def query(self, args):
        return self.squid.query(args['sql']);


    def preprocess(self, args):
        for k in args['data']: 
            args[k] = args['data'][k];
        if not 'obj' in args: return args;
        if args['obj'] not in self.squids:
           raise smartlog.AlertException('not a valid object');
        self.squid = self.squids[args['obj']];
        format = None;
        if args['cmd'] in self.squid.format:
           format = self.squid.format[args['cmd']];
           args = self.squid.load_format(args, format);
           args = self.squid.load_presets(args, format);
        if not 'sql' in args: args['sql']='';
        return self.log.argcheck(args, {
           'clear'   : ['data'],
           'sql'     : {'default'   : args['sql']+" ".join(args['xs']).rstrip().lstrip()},
           'opts'    : {'overwrite' : {'command':args['cmd'],'types':['one']}},
           'squids'  : {'default'   : self.squids},
           'format'    : {'overwrite' : format},
           'cli'     : {'overwrite' : self},
        });


