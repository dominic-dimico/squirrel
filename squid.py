import configparser
import MySQLdb
import smartlog
import traceback
import toolbelt
import code
import re
format_ = format


# Structured Query User Interface Delegator
class Squid(toolbelt.dataserver.DataServer):


    conn   = None;
    config = None;
    table  = None;
    fields = None;
    log    = None;
    data   = {};
    format = {}


    def __init__(self, config=None, table=''):
      self.config = config;
      self.table  = table;
      self.log    = smartlog.Smartlog();



    def describe_table(self, table=None):
        if not table:
           table = self.table;
        cursor = self.connect()
        sql = "describe "+table
        self.log.log(sql);
        cursor.execute(sql);
        types = cursor.fetchall();
        self.log.ok();
        fields = {}
        for i in range(0, len(types)):
            fields[types[i]["Field"]] = types[i]["Type"];
        if not self.fields:
           self.fields = fields;
        return fields;



    def connect(self):
        self.conn = MySQLdb.connect(
          user      = self.config['user'],
          password  = self.config['password'],
          host      = self.config['host'],
          database  = self.config['database']
        );
        return self.conn.cursor(MySQLdb.cursors.DictCursor);


    def close(self):
        self.conn.commit();
        self.conn.close();


    def getmaxid(self):
        save = self.data;
        self.query("select max(id) from "+self.table);
        self.data = self.data[0];
        maxid = self.data['max(id)'];
        self.data = save;
        return maxid;


    def query(self, sql, data=None):
        cursor = self.connect();
        self.log.log(sql);
        try:
            if data: cursor.execute(sql, data.values());
            else:    cursor.execute(sql); 
            self.log.ok();
        except Exception as e:
            self.log.fail();
            self.log.alert(e);
            traceback.print_exc();
        try:    
          self.data = cursor.fetchall();
        except: 
          self.data = None;
        self.close();
        return self.data;


    def quicksearch(self, args):
        args = self.log.argcheck(args, {
           'sql' : {'require':True}
        });
        q = "select * from %s where %s" % (self.table, args['sql']);
        self.query(q);
        return self.data;


    # Can insert one or more rows
    def insert(self, data=None):
        save = self.data;
        if not data: data = self.data;
        if isinstance(data, dict):
            sql = 'insert into '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in data))
            self.query(sql, data);
        elif isinstance(data, list):
             for d in data:
                 if isinstance(d, dict):
                    sql = 'insert into '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in d))
                    self.query(sql, d);
        self.data = save;


    def update(self, data):
        data = self.log.argcheck(data, {
           'id' : {'require':True},
        });
        save = self.data;
        id   = data['id'];
        sql  = 'update '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in data))
        sql += " where id='%s'" % id;
        self.query(sql, data);
        self.data = save;


    def do_queries(self, queries):
        cursor = self.connect();
        for i in range(0, len(queries)):
           (sql, data) = queries[i];
           cursor.execute(sql, data);
           self.data.append(cursor.fetchall());
        self.close();



    def singular(self, args):
        if isinstance(args, dict):
           if 'data' not in args:
              args = {'data' : args};
        elif isinstance(args, tuple):
              args = {'data' : args[0]};
        if isinstance(args['data'], list):
           if args['data']:
                 args['data'] = args['data'][0];
           else: args['data'] = [];
        elif isinstance(args['data'], tuple):
           if args['data']:
                 args['data'] = args['data'][0];
           else: args['data'] = [];
        return args;


    # Sets the pseudonyms for the keys prior to input
    def preprocessfk(self, args={}):
        if 'keys' in args and 'join' in self.format:
           for join in self.format['join']:
               if 'type' in join and join['type'] == "one":
                   if join['foreignkey'] in args['keys']:
                      index = args['keys'].index(join['foreignkey'])
                      args['keys'][index] = join['pseudonym'];
                      args['types'][join['pseudonym']] = 'varchar(256)'
        return args;



    # Finds foreign key by query and corrects pseudonyms
    def postprocessfk(self, args={}):

        args['postkeys'] = [];
        args['postprocess_success'] = True;

        if 'keys' in args and 'join' in self.format:
           for join in self.format['join']:
               if 'type' in join and join['type'] == "one":
                   if 'pseudonym' in join and join['pseudonym'] in args['keys']:

                      # This means we took the raw id
                      if join['pseudonym'] not in args['data']:
                         raise smartlog.QuietException();

                      table = join['table'];
                      if 'squids' in args:
                         if 'aliases' in args:
                            if join['table'] in args['aliases']:
                               table = args['aliases'][join['table']];
                         s = args['squids'][table];
                      else: s = Squid(self.config, join['table']);
                      sargs = s.singular(s.fullsearchquery(args={
                        'sql'   : args['data'][join['pseudonym']],
                        'what'  : [join['table']+'.'+'id'],
                        'table' :  join['table'],
                        'opts'  : {
                          'types' : ['one'],
                        }
                      }));

                      if join['pseudonym'] in args['keys']:
                        i = args['keys'].index(join['pseudonym']);
                        args['keys'][i] = join['foreignkey']
                      if join['pseudonym'] in args['what']:
                        i = args['what'].index(join['pseudonym']);
                        args['what'][i] = join['foreignkey']

                      del args['data'][join['pseudonym']];

                      if 'data' not in sargs or len(sargs['data']) == 0:
                         args['postprocess_success'] = False;
                         args['postkeys'] += [join['table']]
                         return args;
                      else:
                         args['data'][join['foreignkey']] = sargs['data']['id'];

        return args;



    def fullsearchquery(self, args={}):


        # Set SQL
        ords = []; # orderings  
        if 'sql' in args:
            if "search" in self.format:
               args['sql'] = args['sql'].strip();
               if args['sql'] and 'fields' in self.format['search']:
                      if (True not in [x in args['sql'] for x in ['=', '>', '<']]
                          and (not 'order' in args['sql'] or 'where' in args['sql'])):
                         args['sql'] = " or ".join(
                           ["%s='%s'" % (x, args['sql']) for x in self.format["search"]["fields"]]
                         );
                      args['sql'] = args['sql'].strip();
                      if "where" not in args['sql'] and not args['sql'].startswith('order'):
                         args['sql'] = "where " + args['sql'];

               if 'order' not in args['sql']:
                  if 'cmd' in args:
                     if 'order' in self.format[args['cmd']]:
                          args['sql'] = args['sql'] + " " + self.format[args['cmd']]["order"] + " ";
                     elif "order" in self.format["search"]:
                          args['sql'] = args['sql'] + " " + self.format["search"]["order"] + " ";

        else: args['sql'] = "";


        # Set table
        table=self.table;
        if 'table' in args:
           table = args['table'];


        # If no join data, use simple query
        if not 'join' in self.format: 
           args['data'] = self.query(
             "select %s from %s %s" % ("*", table, args['sql'])
           );
           return args;
           

        # Update types
        if not self.fields:
           self.describe_table();

        ttypes = self.fields;
        types = {};
        for index in range(len(self.format['join'])):
            join = self.format['join'][index];
            if join['type'] in args['opts']['types']:

               what = [];

               # Describe that table, add its fields
               if join['type'] == "one":
                    types = self.describe_table(join['table']);
                    what  = join['fields'];

               # Get descriptors for all tables
               elif join['type'] == "many":
                  if args['join_index'] == index:
                    what = join[args['opts']['command']]['fields'];
                    args['what'] = join[args['opts']['command']]['fields'];
                    for c in join['conditions']:
                        types.update(self.describe_table(c['table']));

               # Trim the table name and dot
               for f in what:
                   f = re.sub(r'.*\.', '', f);
                   ttypes[f] = types[f];


        self.fields = ttypes;

            
        try:
           fs = args['what'].copy();
        except: 
           raise smartlog.WarnException("Couldn't copy 'what'. No results?");
           return args;

        for i in range(len(fs)):
            if '.' not in fs[i]:
               fs[i] = table + "." + fs[i];


        cs = []; # conditions
        lims = []; # orderings  
        for index in range(len(self.format['join'])):

            x = self.format['join'][index];

            # Just equate keys
            if x['type'] == "one":
               if "one" in args['opts']['types']:
                   if 'alias' in x: 
                      ali = x['alias'];
                      tab = x['alias'];
                   else:            
                      ali = "";
                      tab = x['table'];
                   cs.append("inner join %s %s on %s" % 
                      (x['table'], ali, table   + '.' + x['foreignkey'] + '=' 
                      +                 tab     + '.' + x['primarykey']));

            # Set join conditions
            elif x['type'] == "many":

               if "many" in args['opts']['types'] and args['join_index'] == index:
                   for c in x['conditions']:

                       t = list();
                       condition = '';
                       if 'condition' in c:
                           condition = c['condition'];

                       # Evaluate variable placeholders in conditions
                       if 'variables' in c:
                          for v in c['variables']:
                              t.append(args['data'][v]);
                          condition = c['condition'] % tuple(t);

                       # If condition takes a variable, add a where clause
                       if 'type' in c and c['type'] == 'where':
                          args['sql'] = condition + " " + args['sql'];
                          condition = '';
                       
                       if 'alias' in c:
                             tabstr = "inner join %s %s" % (c['table'], c['alias']);
                       else: tabstr = "inner join %s " % (c['table']);

                       # Set up join condition
                       if condition != '':
                             tabstr += " on %s" %  (condition);
                       cs.append(tabstr);

                   args['sql'] = args['sql'].strip();
                   if args['sql'] != '': 
                      args['sql']  = " where " + args['sql'];

                   if 'order' in x[args['opts']['command']]:
                       ords.append(x[args['opts']['command']]['order']);

                   if 'number' in x[args['opts']['command']]: 
                      if x[args['opts']['command']]['number'] > 0:
                         lims.append(" limit %s " % x[args['opts']['command']]['number']);


        sql = "select %s from %s %s %s %s %s" % (
              ", ".join(fs), table, " ".join(cs), args['sql'], " ".join(ords), " ".join(lims));


        args['data'] = self.query(sql);
        return args;
