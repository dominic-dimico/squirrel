import configparser
import MySQLdb
import threading
import time
import toolbelt
import smartlog
import code


# Structured Query User Interface Delegator
class Squid:


    db = None;
    config = None;
    table = None;
    data = {};
    fields = None;
    log = None;


    def __init__(self, config, table):
      self.config = config;
      self.table  = table;
      self.log    = smartlog.Smartlog();


    def get_fields(self):
        if self.fields == None:
           cursor = self.connect()
           sql = "describe "+self.table
           cursor.execute(sql);
           types = cursor.fetchall();
           self.fields = {}
           for i in range(0, len(types)):
               self.fields[types[i]["Field"]] = types[i]["Type"];
        #code.interact(local=locals());
        return list(self.fields.keys());


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
        try:    
          self.data = cursor.fetchall();
        except: 
          self.data = None;
        self.close();


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
        #print(type(data));
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


    def poll(self, polldatum):
        handler  = polldatum['handler']
        args     = polldatum['args']
        naptime  = toolbelt.dates.secondsof(polldatum['interval']);
        while True:
              startdt = toolbelt.dates.datestr2dt(toolbelt.dates.dateof(polldatum['start']));
              enddt   = toolbelt.dates.datestr2dt(toolbelt.dates.dateof(polldatum['end']));
              sql = "select * from %s where %s between '%s' and '%s'" % (
                    self.table, polldatum['field'], str(startdt), str(enddt)
              )
              cursor = self.query(sql);
              args["data"] = self.data;
              if self.data:
                 handler(args);
              time.sleep(naptime);

        
    # polldata is list of dictionaries
    def polls(self, polldata):
        threads = []
        for i in range(0, len(polldata)):
            t = threading.Thread(target=self.poll, args=( (polldata[i]), ));
            threads.append(t);
            t.start();
        return threads

