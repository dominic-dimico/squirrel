import configparser
import MySQLdb
import smartlog
import traceback
import code


# Structured Query User Interface Delegator
class Squid:


    db = None;
    config = None;
    table = None;
    data = {};
    fields = None;
    log = None;
    form = {}


    def __init__(self, config, table):
      self.config = config;
      self.table  = table;
      self.log    = smartlog.Smartlog();


    def describe(self, table=None):
        if not table:
           table = self.table;
        cursor = self.connect()
        sql = "describe "+table
        cursor.execute(sql);
        types = cursor.fetchall();
        fields = {}
        for i in range(0, len(types)):
            fields[types[i]["Field"]] = types[i]["Type"];
        if not self.fields:
           self.fields = fields;
        return fields;



    def connect(self):
        self.db = MySQLdb.connect(
          user      = self.config['main']['user'],
          password  = self.config['main']['password'],
          host      = self.config['main']['host'],
          database  = self.config['main']['database']
        );
        return self.db.cursor(MySQLdb.cursors.DictCursor);


    def close(self):
        self.db.commit();
        self.db.close();


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
        q = "select * from %s where %s" % (self.table, args['sql']);
        self.query(q);
        return self.data;


    # Can insert one or more rows
    def insert(self, data=None):
        save = self.data;
        if data: self.data = data;
        if isinstance(self.data, dict):
            sql = 'insert into '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in data))
            self.query(sql, data);
        elif isinstance(self.data, list):
             for d in self.data:
                 sql = 'insert into '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in d))
                 self.query(sql, d);
        self.data = save;


    def update(self, data):
        save = self.data;
        id = data.pop('id');
        sql = 'update '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in data))
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
        if not 'data' in args:
           args = { 'data' : args }
        if len(args['data']) > 1: 
           self.log.warn("Multiple results");
        if len(args['data']) == 0:
           self.log.warn("No result found");
           return args;
        args['data'] = args['data'][0];
        return args;


    # Sets the pseudonyms for the keys prior to input
    def preprocess(self, args={}):
        if 'keys' in args and 'join' in self.form:
           for join in self.form['join']:
               if 'type' in join and join ['type'] == "one":
                   if join['foreignkey'] in args['keys']:
                      index = args['keys'].index(join['foreignkey'])
                      args['keys'][index] = join['pseudonym'];
                      args['types'][join['pseudonym']] = 'varchar(256)'
        return args;


    # Finds foreign key by query and corrects pseudonyms
    def postprocess(self, args={}):

        args['postkeys'] = [];
        args['postprocess_success'] = True;

        if 'keys' in args and 'join' in self.form:
           for join in self.form['join']:
               if 'type' in join and join['type'] == "one":
                   if 'pseudonym' in join and join['pseudonym'] in args['keys']:

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
        if 'sql' in args:
            if args['sql'] != '':
                  if "search" in self.form and "defaults" in self.form["search"]:
                      if True not in [x in args['sql'] for x in ['=', '>', '<']]:
                         args['sql'] = " or ".join(
                           ["%s='%s'" % (x, args['sql']) for x in self.form["search"]["defaults"]]
                         );
                      if "where" not in args['sql']:
                         args['sql'] = "where " + args['sql'];
                      if "order" in self.form["search"]:
                         args['sql'] = args['sql'] + " " + self.form["search"]["order"];
        else: args['sql'] = "";


        # Set table
        table=self.table;
        if 'table' in args:
           table = args['table'];


        # If no join data, use simple query
        if not 'join' in self.form: 
           args['data'] = self.query(
             "select %s from %s %s" % ("*", table, args['sql'])
           );
           return args;
           

        # Update types
        import re
        ttypes = self.fields;
        types = {};
        for index in range(len(self.form['join'])):
            join = self.form['join'][index];
            if join['type'] in args['opts']['types']:

               what = [];

               # Describe that table, add its fields
               if join['type'] == "one":
                    types = self.describe(join['table']);
                    what  = join['fields'];

               # Get descriptors for all tables
               elif join['type'] == "many":
                  if args['join_index'] == index:
                    what = join[args['opts']['command']]['fields'];
                    args['what'] = join[args['opts']['command']]['fields'];
                    for c in join['conditions']:
                        types.update(self.describe(c['table']));

               # Trim the table name and dot
               for f in what:
                   f = re.sub(r'.*\.', '', f);
                   ttypes[f] = types[f];

        self.fields = ttypes;

            
        fs = args['what'].copy();
        for i in range(len(fs)):
            if '.' not in fs[i]:
               fs[i] = table + "." + fs[i];


        cs = []; # conditions
        for index in range(len(self.form['join'])):

            x = self.form['join'][index];

            # Just equate keys
            if x['type'] == "one":
               if "one" in args['opts']['types']:
                   cs.append("inner join %s on %s" % 
                      ( x['table'],     table   + '.' + x['foreignkey'] + '=' 
                      +              x['table'] + '.' + x['primarykey']));

            # Set join conditions
            elif x['type'] == "many":
               if "many" in args['opts']['types'] and args['join_index'] == index:
                   for c in x['conditions']:

                       t = list();
                       condition = '';
                       if 'condition' in c:
                           condition = c['condition'];

                       # Evaluate variable placeholders in conditions
                       #self.log.print(args);
                       if 'variables' in c:
                          for v in c['variables']:
                              t.append(args['data'][v]);
                          condition = c['condition'] % tuple(t);

                       # If condition takes a variable, add a where clause
                       if 'type' in c and c['type'] == 'where':
                          args['sql'] += condition;
                          condition = '';
                       
                       # Set up join condition
                       if condition != '':
                             cs.append("inner join %s on %s" %  (c['table'], condition));
                       else: cs.append("inner join %s " %  (c['table']));

                   if args['sql'] != '': 
                      args['sql']  = " where " + args['sql'];
                   if 'order' in x[args['opts']['command']]:
                      args['sql'] += " " + x[args['opts']['command']]['order'] + " ";

                   if 'number' in x[args['opts']['command']]: 
                      if x[args['opts']['command']]['number'] > 0:
                         args['sql'] += " limit %s " % x[args['opts']['command']]['number'];


        sql = "select %s from %s %s %s" % (
              ", ".join(fs), table, " ".join(cs), args['sql']);


        args['data'] = self.query(sql);
        return args;
