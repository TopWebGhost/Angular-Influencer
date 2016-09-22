import json
import os.path


class JSONDataLoader(object):

    def __init__(self, dir):
        self.dir = dir
        self._cache = {}

    def clear_cache(self):
        self._cache.clear()

    def __getitem__(self, base_filename):
        return self.load(base_filename + '.json')

    def load(self, filename):
        base_filename = os.path.splitext(filename)[0]
        if base_filename in self._cache:
            return self._cache[base_filename]
        with open(os.path.join(self.dir, filename)) as f:
            contents = f.read().decode('utf-8').strip()
            self._cache[base_filename] = json.loads(contents)
        return self._cache[base_filename]

    def load_to_js_string(self, filename):
        return json.dumps(json.dumps(self.load(filename), ensure_ascii=False).encode('utf-8'))

