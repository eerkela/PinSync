import json
import os
import time

import cv2


'''
# deprecated, but a useful code snippet to keep around

def flatten(self, dict1):
    def generator(dict2):
        for (k, v) in dict2.items():
            if isinstance(v, dict):
                yield from generator(v)
            else:
                yield (k, v)

    flattened_dict = {}
    for (key, value) in generator(dict1):
        flattened_dict[key] = value
    return flattened_dict
'''

def dhash(image, hash_size=8):
    # convert image to grayscale and resize, adding single column (width)
    # to compute the horizontal gradient
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    resized = cv2.resize(gray, (hash_size + 1, hash_size))

    # compute relative horizontal gradiant between adjacent column pixels
    diff = resized[:, 1:] > resized[:, :-1]

    # convert difference image to a hash and return it
    hash = sum([2 ** i for (i, v) in enumerate(diff.flatten()) if v])
    return hash


class Image:

    def __init__(self, path):
        if not os.path.exists(path):
            raise Exception('Image not found: %s' % path)
        self.path = path

        components = path.split(os.sep)
        self.board = components[0]
        self.section = components[1]
        self.id = ''.join(components[-1].split('.')[:-1])

        image = cv2.imread(path)
        self.hash = dhash(image)

        (height, width, _) = image.shape
        self.height = height
        self.width = width
        self.size = height * width
        self.color = tuple(image.mean(axis=0).mean(axis=0))

    def delete(self, cache=None):
        print('\t- ' + self.path)
        os.remove(self.path)

        # Remove empty directories
        (head, tail) = os.path.split(self.path)
        while (len(os.listdir(head)) == 0):
            os.rmdir(head)
            (head, tail) = os.path.split(head)

        # Remove from cache if supplied
        if cache:
            if self.board in cache.keys():
                if self.section:
                    if self.section in cache[self.board].keys():
                        cache[self.board][self.section].pop(self.id)
                else:
                    cache[self.board].pop(self.id)

    def to_json(self):
        result = {
            'id' : self.id,
            'board' : self.board,
            'section' : self.section,
            'path' : self.path,
            'hash' : self.hash,
            'height' : self.height,
            'width' : self.width,
            'size' : self.size,
            'color' : self.color
        }
        return result

    def __str__(self):
        return self.path


class Manifest:

    def __init__(self, root_dir):
        self.root = root_dir
        self.systemdirs = ['.git', '__pycache__', 'credentials', 'tokens']
        self.systemfiles = ['.env', '.gitignore', 'desktop.ini',
                            'PinSync.py', 'Client.py', 'Manifest.py',
                            'Comparator.py', 'manifest.json']

        print('Loading previous manifest...')
        manifest_path = os.path.join(self.root, 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                self.old = json.load(f)
        else:
            self.old = {}

        self.cache = {}

    def get_boards(self):
        boards = []
        for dir in os.listdir(self.root):
            dir_path = os.path.join(self.root, dir)
            if (os.path.isdir(dir_path) and dir not in self.systemdirs):
                boards.append(dir)
        return boards

    def get_sections(self, board):
        if board not in self.get_boards():
            raise KeyError('Board not found: %s' % board)

        board_path = os.path.join(self.root, board)
        sections = []
        for sec in os.listdir(board_path):
            sec_path = os.path.join(board_path, sec)
            if (os.path.isdir(sec_path) and sec not in self.systemdirs):
                sections.append(sec)
        return sections

    def get_contents(self, board, section=None):
        if board not in self.get_boards():
            raise KeyError('Board not found: %s' % board)
        if (section and section not in self.get_sections(board)):
            raise KeyError('Section not found: %s/%s' % (board, section))

        # retrieve cached contents if available
        if board in self.cache.keys():
            if not section:
                return [v for v in self.cache[board].values()
                        if isinstance(v, Image)]
            elif section in self.cache[board].keys():
                return list(self.cache[board][section].values())


        # If result is not already cached, compute and cache it
        board_path = os.path.join(self.root, board)
        if section:
            contents = []
            sec_path = os.path.join(board_path, section)
            for (dirpath, dirnames, filenames) in os.walk(sec_path):
                for file in filenames:
                    if (file not in self.systemfiles):
                        file_path = os.path.join(sec_path, dirpath, file)
                        image = Image(file_path)
                        contents.append(image)
            # Cache contents
            if board not in self.cache.keys():
                self.cache[board] = {}
            if section not in self.cache[board].keys():
                self.cache[board][section] = {}
            for image in contents:
                self.cache[board][section][image.id] = image
            return contents

        contents = []
        for file in os.listdir(board_path):
            file_path = os.path.join(board_path, file)
            if (os.path.isfile(file_path) and file not in self.systemfiles):
                image = Image(file_path)
                contents.append(image)
        if board not in self.cache.keys():
            self.cache[board] = {}
        for image in contents:
            self.cache[board][image.id] = image
        return contents

    def get_deleted_images(self, board, section=None):
        if board not in self.get_boards():
            raise KeyError('Board not found: %s' % board)
        if (section and section not in self.get_sections(board)):
            raise KeyError('Section not found: %s/%s' % (board, section))

        if board not in self.old.keys():
            return []
        if section and section not in self.old[board].keys():
            return []

        if section:
            new = [i.id for i in self.get_contents(board, section)]
            old = [j for j in self.old[board][section].keys()]
            return [id for id in old if id not in new]

        new = [i.id for i in self.get_contents(board)]
        old = []
        for (id, json) in self.old[board].items():
            if 'id' in json.keys():
                old.append(id)
        return [id for id in old if id not in new]

    def get_duplicate_images(self, board, section=None):
        contents = self.get_contents(board, section)
        hashes = {}
        for image in contents:
            if image.hash not in hashes.keys():
                hashes[image.hash] = []
            hashes[image.hash].append(image)
        duplicates = {}
        for (hash, images) in hashes.items():
            if len(images) > 1:
                duplicates[hash] = images
        return duplicates

    def remove_duplicates(self, board, section=None):
        duplicates = self.get_duplicate_images(board, section)
        removed = []
        for (hash, images) in duplicates.items():
            images = sorted(images, key=lambda im: im.id)
            choice = max(images, key=lambda im: im.size)
            for image in images:
                if (image.id != choice.id):
                    image.delete(self.cache)
                    removed.append(image)
        return removed

    def save(self):
        print('Saving manifest...')
        manifest = {}
        for board in self.get_boards():
            manifest[board] = {}
            for image in self.get_contents(board):
                manifest[board][image.id] = image.to_json()
            for section in self.get_sections(board):
                manifest[board][section] = {}
                for image in self.get_contents(board, section):
                    manifest[board][section][image.id] = image.to_json()
        manifest_path = os.path.join(self.root, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)


if __name__ == '__main__':
    wd = '/home/eerkela/drive/DnD/The Waking World/Images'
    m = Manifest(wd)
    print(len(m.get_contents('The Waking World')))

    #m.save()


    '''
    print(m.get_boards())
    print(m.get_sections('The Waking World'))
    print('Crown of the World')
    for entry in m.get_contents('The Waking World', 'Crown of the World'):
        simplified_path = entry['path'].split(os.sep)
        i = simplified_path.index('The Waking World')
        simplified_path = os.sep.join(simplified_path[i:])

        print('\t%s: %s' % (entry['id'], simplified_path))

    print()
    print('The Waking World')
    for entry in m.get_contents('The Waking World'):
        simplified_path = entry['path'].split(os.sep)
        i = simplified_path.index('The Waking World')
        simplified_path = os.sep.join(simplified_path[i:])

        print('\t%s: %s' % (entry['id'], simplified_path))
    '''

    #print(json.dumps(m.get_contents('The Waking World'), indent=4))
