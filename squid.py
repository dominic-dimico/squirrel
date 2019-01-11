import configparser
import mysql.connector
import threading
import time
import toolbelt
import smartlog




# Structured Query User Interface Delegator
class Squid:


    db = None;
    config = None;
    table = None
    data = None;


    def __init__(self, config, table):
      self.config = config;
      self.table  = table;


    def connect(self):
        self.db = mysql.connector.connect(
          user      = self.config['main']['user'],
          password  = self.config['main']['password'],
          host      = self.config['main']['host'],
          database  = self.config['main']['database']
        );
        return self.db.cursor(dictionary=True)


    def close(self):
        self.db.commit();
        self.db.close();


    def query(self, sql, data=None):
        cursor = self.connect();
        #smartlog.log(sql); smartlog.ok();
        #smartlog.log(data); smartlog.ok();
        if data: cursor.execute(sql, data.values());
        else:    cursor.execute(sql); "This one!";
        try:    self.data = cursor.fetchall();
        except: self.data = None;
        self.close();


    def insert(self, data):
        sql = 'insert into '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in data))
        self.query(sql, data);


    def update(self, data):
        id = data.pop('id');
        sql = 'update '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in data))
        sql += " where id='%s'" % id;
        self.query(sql, data);


    def do_queries(self, queries):
        cursor = self.connect();
        for i in range(0, len(queries)):
           (sql, data) = queries[i];
           cursor.execute(sql, data);
           self.data.append(cursor.fetchall());
        self.close();


    def poll(self, polldatum):
        (interval, field, start, end, handler) = polldatum
        while True:
              startdt = toolbelt.converters.date(start);
              enddt = toolbelt.converters.date(end);
              sql = "select * from %s where %s between '%s' and '%s'" % (
                    self.table, field, str(startdt), str(enddt)
              )
              smartlog.log(sql); smartlog.ok();
              cursor = self.query(sql);
              if self.data:
                 handler(self.data);
              time.sleep(interval);

        
    def polls(self, polldata):
        threads = []
        for i in range(0, len(polldata)):
            t = threading.Thread(target=self.poll, args=( (polldata[i]), ));
            threads.append(t);
            t.start();
        return threads

