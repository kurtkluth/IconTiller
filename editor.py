"""Lossless local draft operations; no device communication."""
from copy import deepcopy
from device import Snapshot

def is_folder(item):
    return (isinstance(item, dict) and isinstance(item.get('iconLists'), list)
            and item.get('iconType') != 'app' and 'bundleIdentifier' not in item)

def title(item):
    return str(item.get('displayName') or item.get('bundleIdentifier') or 'Special item') if isinstance(item, dict) else 'Reserved slot'

class Draft:
    def __init__(self, snapshot):
        self.original = deepcopy(snapshot)
        self.layout = deepcopy(snapshot.layout)
        self.past, self.future = [], []

    @property
    def dirty(self): return self.layout != self.original.layout

    def snapshot(self):
        return Snapshot(self.original.name, self.original.version, deepcopy(self.layout), self.original.device_id,
                        deepcopy(self.original.baseline))

    def saved_snapshot(self):
        snapshot = self.snapshot()
        if snapshot.baseline is None and snapshot.device_id:
            snapshot.baseline = deepcopy(self.original.layout)
        return snapshot

    def container(self, path):
        if len(path) == 1: result = self.layout[path[0]]
        elif len(path) == 3: result = self.layout[path[0]][path[1]]['iconLists'][path[2]]
        else: raise ValueError('Unsupported destination.')
        if not isinstance(result, list): raise ValueError('This group cannot be edited.')
        return result

    def checkpoint(self):
        self.past.append(deepcopy(self.layout))
        self.past = self.past[-100:]
        self.future.clear()

    def move(self, source, index, target, position=None):
        src, dst = self.container(source), self.container(target)
        item = src[index]
        if not isinstance(item, dict): raise ValueError('Reserved slots cannot be moved.')
        if len(target) == 3 and is_folder(item): raise ValueError('Folders cannot be nested.')
        if len(source) == 1 and len(target) == 3 and source[0] == target[0] and index == target[1]:
            raise ValueError('An item cannot be moved into itself.')
        if target == (0,) and dst is not src and len(dst) >= 4:
            raise ValueError('The dock has four items. Move one out first.')
        position = len(dst) if position is None else position
        if not 0 <= position <= len(dst): raise ValueError('Invalid destination slot.')
        if dst is src and position in (index, index + 1): return
        self.checkpoint()
        src.pop(index)
        if dst is src and position > index: position -= 1
        dst.insert(position, item)

    def folder(self, path, index, name):
        name = name.strip()
        if not name: raise ValueError('Enter a folder name.')
        item = self.container(path)[index]
        if is_folder(item):
            self.checkpoint()
            item['displayName'] = name
        else:
            if len(path) != 1 or not isinstance(item, dict): raise ValueError('Choose an app on a Home Screen page.')
            self.checkpoint()
            self.container(path)[index] = {'displayName': name, 'listType': 'folder', 'iconLists': [[item]]}

    def swap(self, source, index, target, position):
        if source[0] == 0 or target[0] == 0:
            raise ValueError('Dock swaps have not been enabled.')
        src, dst = self.container(source), self.container(target)
        if not 0 <= index < len(src) or not 0 <= position < len(dst):
            raise ValueError('Choose two existing app tiles.')
        for item in (src[index], dst[position]):
            if not isinstance(item, dict) or is_folder(item) or not item.get('bundleIdentifier'):
                raise ValueError('Choose two apps; folders and special items cannot be swapped.')
        if src is dst and index == position: return
        self.checkpoint()
        src[index], dst[position] = dst[position], src[index]

    def add_page(self):
        self.checkpoint()
        self.layout.append([])

    def insert_across_pages(self, source, index, target, position):
        """Reorder the page stream, preserving each page's existing slot count."""
        if len(source) != 1 or len(target) != 1 or min(source[0], target[0]) < 1:
            raise ValueError('Automatic shifting works between Home Screen pages, not the dock or inside folders.')
        src, dst = self.container(source), self.container(target)
        if not 0 <= index < len(src) or not 0 <= position <= len(dst):
            raise ValueError('Choose an existing app and insertion position.')
        item = src[index]
        if not isinstance(item, dict) or is_folder(item) or not item.get('bundleIdentifier'):
            raise ValueError('Drag an app to insert it between icons.')
        sizes = [len(page) for page in self.layout[1:]]
        entries = [entry for page in self.layout[1:] for entry in page]
        if source[0] > target[0] and position == len(dst) and dst:
            # The end-of-page drop occupies its last slot, spilling that icon right.
            position -= 1
        start = sum(sizes[:source[0]-1]) + index
        end = sum(sizes[:target[0]-1]) + position
        if end in (start, start+1): return
        # Unknown slots/widgets cannot be shifted by this operation.
        for entry in entries[min(start,end):max(start,end)+1]:
            if not isinstance(entry, dict) or not (is_folder(entry) or entry.get('bundleIdentifier') or entry.get('webClipURL')):
                raise ValueError('This move would shift an unsupported item.')
        self.checkpoint()
        entries.pop(start)
        entries.insert(end - (end > start), item)
        offset = 0
        for page, count in enumerate(sizes, 1):
            self.layout[page] = entries[offset:offset+count]
            offset += count

    def find(self, query):
        """Return matching entries and their editable locations, including folders."""
        query = query.strip().casefold()
        results = []
        def visit(items, path, location):
            for index, item in enumerate(items):
                if not isinstance(item, dict): continue
                name = title(item)
                if query in (name + ' ' + str(item.get('bundleIdentifier', ''))).casefold():
                    results.append((name, location, path, index))
                if is_folder(item) and len(path) == 1:
                    for page, children in enumerate(item['iconLists']):
                        visit(children, (path[0], index, page), f'{location} / {name} / Folder page {page+1}')
        for page, items in enumerate(self.layout):
            visit(items, (page,), 'Dock' if page == 0 else f'Page {page}')
        return results

    def undo(self):
        if self.past:
            self.future.append(self.layout)
            self.layout = self.past.pop()

    def redo(self):
        if self.future:
            self.past.append(self.layout)
            self.layout = self.future.pop()
