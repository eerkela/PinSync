from __future__ import annotations
import json
import os
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Optional

from Image import Image
from Pin import Pin

SYSTEMDIRS = ['.git', '__pycache__', 'credentials', 'tokens']
SYSTEMFILES = ['.env', '.gitignore', 'desktop.ini', 'PinSync.py', 'Client.py',
               'Manifest.py', 'manifest.json']
MAX_THREADS = os.cpu_count() * 4
VALID_FILETYPES = [ # determined by cv2.imread()
    # https://docs.opencv.org/4.3.0/d4/da8/group__imgcodecs.html#ga288b8b3da0892bd651fce07b3bbd3a56
    '.bmp', '.dib',
    '.jpeg', '.jpg', '.jpe',
    '.jp2',
    '.png',
    '.webp',
    '.pbm', '.pgm', '.ppm', '.pxm', '.pnm',
    '.pfm',
    '.sr', '.ras',
    '.tiff', '.tif',
    '.exr',
    '.hdr', '.pic',
]


class Container:
    ''' A Container is an object that contains and provides an interface for
    manipulating intelligent Pin and Image objects.  It contains functionality
    to sync the contents of a local repository with its counterpart on
    Pinterest, scan for duplicate images, and react to changes made locally,
    reflecting them in its online counterpart.

    Containers are not to be instantiated directly (note the lack of an
    __init__ function), but come in two forms available to the end user:
    Board and Section, with any one board containing possibly many sections.
    Nearly all end-user interactions should be directed toward these objects.
    '''

    client = None
    name = None
    path = None
    id = None
    pins = []
    images = []
    old = []

    def delete_pin(self, pin_id: str) -> Optional[Pin]:
        index = 0
        for p in self.pins:
            if p.id == pin_id:
                self.client.delete_pin(pin_id=pin_id)
                return self.pins.pop(index)
            index += 1
        return None

    def delete_image(self, image_id: str) -> Optional[Image]:
        index = 0
        for image in self.images:
            if image.id == image_id:
                print('\t- ' + image.path)
                os.remove(image.path)

                # Remove empty parent directories
                (head, tail) = os.path.split(image.path)
                while (len(os.listdir(head)) == 0):
                    os.rmdir(head)
                    (head, tail) = os.path.split(head)
                return self.images.pop(index)
            index += 1
        return None

    def size(self) -> int:
        '''returns number of items in container on Pinterest.'''
        return len(self.pins)

    def get_differences(self) -> Tuple[List[Pin], List[Image]]:
        ''' Compares locally stored images against pins stored on pinterest.
        Returns: Tuple<List<Pin>, List<Image>>, two lists describing [0] the
            pins that are present on Pinterest, but not on storage, and [1]
            the Images that are present on storage, but not on Pinterest,
            respectively.
        '''
        image_ids = [image.id for image in self.images]
        pin_ids = [pin.id for pin in self.pins]
        not_on_disk = [pin for pin in self.pins if pin.id not in image_ids]
        not_on_cloud = [im for im in self.images if im.id not in pin_ids]
        return (not_on_disk, not_on_cloud)

    def sync(self):
        # Reflect local changes:
        self.push_local_changes()

        # Remove local files that have been deleted from Pinterest:
        (not_on_disk, not_on_cloud) = self.get_differences()
        for image in not_on_cloud:
            self.delete_image(image.id)

        # Download images that are missing on local storage:
        for pin in not_on_disk:
            pin.download()

        # Delete duplicates:
        for image in self.remove_duplicates():
            self.delete_pin(image.id)

        # Save manifest:
        self.save_manifest()

    def manually_deleted(self) -> List[str]:
        ''' Returns list of image ids that were deleted by the user between
        the last time manifests were saved (usually during a sync operation)
        and now.
        Out: List[str] of ids
        '''
        deleted = []
        ids = [image.id for image in self.images]
        for json in self.old:
            if json['id'] not in ids:
                deleted.append(json['id'])
        return deleted

    def push_local_changes(self):
        deleted = self.manually_deleted()
        if (len(deleted) > 0):
            msg = '\t> %d local files have been deleted since last sync.' \
                   % len(deleted)
            if (len(deleted) == 1):
                msg = '\t> 1 local file has been deleted since last sync.'
            prompt = '\tDo you want to push these changes to Pinterest? (y/n) '

            print()
            print(msg)
            response = input(prompt)
            affirmative = ['y', 'yes']
            negative = ['n', 'no']
            while (response.lower() not in affirmative + negative):
                response = input(prompt)
            if response.lower() in affirmative:
                for id in deleted:
                    self.delete_pin(id)
            print()

    def duplicate_images(self) -> Dict[int, List[Image]]:
        ''' Collects and returns all images that have at least one collision
        in hash, implying that they are duplicates of one another.
        Out: Dict<int, List<Image>> mapping hash <int> to corresponding
            images <List<Image>>.
        '''
        hashes = {}
        for image in self.images:
            if image.hash not in hashes.keys():
                hashes[image.hash] = []
            hashes[image.hash].append(image)
        duplicates = {}
        for (hash, images) in hashes.items():
            if len(images) > 1:
                duplicates[hash] = images
        return duplicates

    def remove_duplicates(self) -> List[Image]:
        ''' Deletes all duplicate images present in container and returns list
        of deleted values.  Choice of images to keep is based on image size
        (height x width).  Ties are resolved in favor of older pins
        (smaller id).
        Out: List<Image> containing the value of each deleted image.
        '''
        duplicates = self.duplicate_images()
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
        ''' Dumps contents of container to disk.  Data is stored in a
        manifest.json file within the container's directory on local storage.
        '''
        manifest = []
        for image in self.images:
            j = image.to_json()
            manifest.append(j)

        manifest_path = os.path.join(self.path, 'manifest.json')
        with open(manifest_path, 'w') as f:
            json.dump(manifest, f)

    def __str__(self):
        return self.name


class Board(Container):
    ''' A Board is a type of Container that can store Section objects as well
    as pins and images.

    Upon initialization, the Board's fields are populated from the provided
    json_response.  The passed client is used to comb through the board's
    contents on Pinterest and populate it with Pin and Image objects on
    construction.

    If a Board has pins/images of its own, they represent
    only what is contained on the board itself in pinterest, not including the
    contents of its sections.
    '''

    def __init__(self, client: Pinterest, json_response):
        self.client = client
        self.name = json_response['name']
        self.id = json_response['id']
        self.path = self.name
        if not os.path.exists(self.path):
            os.makedirs(self.path)

        # get board sections
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as exec:
            self.sections = exec.map(lambda s: Section(self.client, s, self),
                                     self.client.get_board_sections(
                                        board_id=self.id))

        # get board pins
        self.pins = []
        batch = self.client.board_feed(board_id=self.id)
        while (batch):
            for response in batch:
                try:
                    p = Pin(response)
                except:
                    continue
                self.pins.append(p)
            batch = self.client.board_feed(board_id=self.id)

        # get images
        self.images = []
        for file in os.listdir(self.path):
            file_path = os.path.join(self.path, file)
            if (os.path.isfile(file_path) and file not in SYSTEMFILES):
                extension = file[file.rfind('.'):]
                if extension in VALID_FILETYPES:
                    image = Image(file_path)
                    self.images.append(image)
                else:
                    id = file[:file.rfind('.')]
                    self.delete_pin(id)

        # gather previous contents
        manifest_path = os.path.join(self.path, 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                try:
                    self.old = json.load(f)
                except:
                    self.old = []
        else:
            self.old = []

    def get_sections(self) -> List[Section]:
        ''' returns a list containing each Section object stored within this
        board.'''
        return self.sections


class Section(Container):
    ''' A Section is the most primitive form of Container, with only Pins and
    Images.

    Upon initialization, the Section's fields are populated from the provided
    json_response.  The passed client is used to comb through the section's
    contents on Pinterest and populate the container with Pin and Image
    objects on construction.
    '''

    def __init__(self, client: Pinterest, json_response, parent: Board):
        self.client = client
        self.name = json_response['title']
        self.id = json_response['id']
        self.parent = parent
        self.path = os.path.join(self.parent.name, self.name)
        if not os.path.exists(self.path):
            os.makedirs(self.path)

        # get section pins
        self.pins = []
        batch = self.client.get_section_pins(section_id=self.id)
        while (batch):
            for response in batch:
                try:
                    p = Pin(response, self.name)
                except:
                    continue
                self.pins.append(p)
            batch = self.client.get_section_pins(section_id=self.id)

        # get images
        self.images = []
        for (dirpath, dirnames, filenames) in os.walk(self.path, topdown=True):
            dirnames[:] = [d for d in dirnames if d not in SYSTEMDIRS]
            for file in filenames:
                if file not in SYSTEMFILES:
                    extension = file[file.rfind('.'):]
                    if extension in VALID_FILETYPES:
                        file_path = os.path.join(dirpath, file)
                        image = Image(file_path)
                        self.images.append(image)
                    else:
                        id = file[:file.rfind('.')]
                        self.delete_pin(id)

        # gather previous contents
        manifest_path = os.path.join(self.path, 'manifest.json')
        if os.path.exists(manifest_path):
            with open(manifest_path, 'r') as f:
                try:
                    self.old = json.load(f)
                except:
                    self.old = []
        else:
            self.old = []
