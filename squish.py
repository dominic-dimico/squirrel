import parse
import sys



# A command.  If it has subcommands they are listed.
# If it requires no subcommands, it has a callback.
class Command():

      # Parts is a dict with left, right, middle.
      parts    = None;
      grammar  = None
      commands = []
      callback = None
      args     = None

      def __init__(self, grammar, callback, args, commands):
          self.grammar  = grammar;
          self.callback = callback;
          self.args     = args;
          self.commands = commands;

      def __init__(self, grammar, commands):
          self.grammar  = grammar;
          self.commands = commands;

      def execute(self):
          self.callback(self.args);




def delegator(self):
  if 'clause' in self.args.keys():
       clause = self.args['clause'];
  else: clause = None;
  actions = ('new', 'edit', 'view');
  if any(action in self.args['action'] for action in actions):
     keys = keys_of(args['object']);
  if 'new' == args['action']:
     new_object(keys);
  elif 'edit' == args['action']:
       if not clause:
          edit_object(keys);



# Gets input from stdin
def gather(keys):
    data = {};
    maxlen = max(map(len, keys));
    for key in keys:
        val = raw_input("{:maxlen}> ".format(key));
        data[key] = val;
    return data;

