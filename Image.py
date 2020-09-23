from __future__ import annotations
import os

import cv2


def dhash(image, hash_size: int = 8):
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
    ''' An Image is an object that describes an image present locally, but not
    necessarily on Pinterest.
    '''

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

    def to_json(self):
        ''' Translates object into json format.  Used for manifest
        interactions.
        '''
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

    def is_similar_to(self, image: Image, threshold: int = 3):
        ''' Tests whether the absolute difference between this image's hash
        and the one supplied as an argument falls within threshold.  If it
        does, the images are considered similar and this returns True.
        '''
        if abs(self.hash - image.hash) < threshold:
            return True
        return False

    def __str__(self):
        return self.path
