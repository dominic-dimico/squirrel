import configparser
import mysql.connector

# Structured Query User Interface Delegator
class Squid:

    db = None;
    config = None;
    table = None

    __init__(config, table):
      self.config = config;
      self.table  = table;


    def connect(self):
        db = mysql.connector.connect(
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
        if data: cursor.execute(sql, data);
        else:    cursor.execute(sql);
        #with open('cmd.sql', 'w') as fd: fd.write(sql);
        self.close();


    def insert(self, data):
        sql = 'insert into '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in data))
        self.query(sql, data);


    def update(self, data, id):
        sql = 'update '+self.table+' set {}'.format(', '.join('{}=%s'.format(k) for k in data))
        sql += " where id='%s'" % id;
        self.query(sql, data);


    def do_queries(self, queries):
        cursor = self.connect();
        for i in range(0, len(queries)):
           (sql, data) = queries[i];
           cursor.execute(sql, data);
        self.close();


#import mysql.connector
#import threading

# Create thread, which does polling.
# Every n seconds, use easy SQL to poll DATETIME field.
# If results:
#    Send results to handler function.


