import json
import os
import time

import cv2


SYSTEMDIRS = ['.git', '__pycache__', 'credentials', 'tokens']
SYSTEMFILES = ['.env', '.gitignore', 'desktop.ini', 'PinSync.py', 'Client.py',
               'Manifest.py', 'manifest.json']




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


class Container:

    name = None
    path = None
    images = []
    old = []

    def get_name(self):
        return self.name

    def get_path(self):
        return self.path

    def get_images(self):
        return self.images

    def get_size(self):
        return len(self.images)

    def get_deleted_images(self):
        deleted = []
        ids = [image.get_id() for image in self.images]
        for json in self.old:
            if json['id'] not in ids:
                deleted.append(json['id'])
        return deleted

    def get_duplicate_images(self):
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

    def delete_image(self, image_id):
        index = 0
        for image in self.images:
            if image.get_id() == image_id:
                image.delete()
                return self.images.pop(index)
            index += 1
        return None

    def remove_duplicates(self):
        duplicates = self.get_duplicate_images()
        removed = []
        for (hash, images) in duplicates.items():
            images = sorted(images, key=lambda im: im.id)
            choice = max(images, key=lambda im: im.size)
            for image in images:
                if (image.id != choice.id):
                    self.delete_image(image.id)
                    removed.append(image)
        return removed

    def save_manifest(self):
        manifest = []
        for image in self.images:
            json = image.to_json()
            manifest.append(json)

        manifest_path = os.path.join(self.path, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

    def __str__(self):
        return self.name


class Board(Container):

    def __init__(self, board_name):
        self.name = board_name
        self.path = board_name
        if not os.path.exists(self.path):
            os.makedirs(self.path)

        self.sections = []
        self.images = []
        for file in os.listdir(self.path):
            file_path = os.path.join(self.path, file)
            if (os.path.isdir(file_path) and file not in SYSTEMDIRS):
                section = Section(self, file)
                self.sections.append(section)
            elif (os.path.isfile(file_path) and file not in SYSTEMFILES):
                image = Image(file_path)
                self.images.append(image)

        manifest_path = os.path.join(self.path, 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                self.old = json.load(f)
        else:
            self.old = []

    def get_sections(self):
        return self.sections


class Section(Container):

    def __init__(self, board, section_name):
        self.name = section_name
        self.path = os.path.join(board.get_name(), self.name)
        if not os.path.exists(self.path):
            os.makedirs(self.path)

        self.images = []
        for (dirpath, dirnames, filenames) in os.walk(self.path, topdown=True):
            dirnames[:] = [d for d in dirnames if d not in SYSTEMDIRS]
            for file in filenames:
                if (file not in SYSTEMFILES):
                    file_path = os.path.join(dirpath, file)
                    image = Image(file_path)
                    self.images.append(image)

        manifest_path = os.path.join(self.path, 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                self.old = json.load(f)
        else:
            self.old = []


class Image:

    #TODO: Remove image from container upon deletion
    #add a reference to this image's parent to do that

    def __init__(self, path, parent=None):
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

    def get_path(self):
        return self.path

    def get_id(self):
        return self.id

    def get_hash(self):
        return self.hash

    def get_dimensions(self):
        return (self.height, self.width)

    def get_avg_color(self):
        return self.color

    def get_pixel_count(self):
        return self.height * self.width

    def delete(self):
        print('\t- ' + self.path)
        os.remove(self.path)

        # Remove empty directories
        (head, tail) = os.path.split(self.path)
        while (len(os.listdir(head)) == 0):
            os.rmdir(head)
            (head, tail) = os.path.split(head)

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

    def is_similar_to(self, image, threshold=3):
        if abs(self.hash - image.hash) < threshold:
            return True
        return False

    def __str__(self):
        return self.path


class Manifest:

    def __init__(self):
        self.contents = []
        for file in os.listdir(os.getcwd()):
            if os.path.isdir(file) and file not in SYSTEMDIRS:
                b = Board(file)
                self.contents.append(b)

    def get_boards(self):
        return self.contents

    def find(self, board_name, section_name=None, image_id=None):
        def find_board(board):
            for b in self.contents:
                if b.get_name() == board:
                    return b
            raise Exception('Board not found: %s' % board)

        def find_section(b, section):
            for s in b.get_sections():
                if s.get_name() == section:
                    return s
            raise Exception('Section not found: %s/%s' % (board, section))

        def find_image(container, image):
            for i in container.get_images():
                if i.get_id() == image:
                    return i
            raise Exception('Image not found: %s' % image)

        b = find_board(board_name)
        if section_name:
            s = find_section(b, section_name)
            if image_id:
                return find_image(s, image_id)
            return s
        if image_id:
            return find_image(b, image_id)
        return b


if __name__ == '__main__':
    wd = '/home/eerkela/drive/DnD/The Waking World/Images'
    os.chdir(wd)

    m = Manifest()
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
