from json import dumps

class Debugger(object):
    def __init__(self, path):
        self.path = path
        self._items = {}

    def write(self):
        with open(self.path, 'w') as f:
            f.write(dumps(self.items))
    
    @property
    def items(self):
        return self._items

    @items.setter
    def items(self, items):
        if type(items) != list:
            items = [items]

        for item in items:
            for key, thing in item.iteritems():
                self._items[key] = thing
