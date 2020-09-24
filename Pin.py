from __future__ import annotations
import os
import requests
from typing import Dict, List, Tuple, Optional

from Image import Image


class Pin:
    ''' A Pin is an object that describes a pin present on Pinterest, but not
    necessarily on local storage.
    '''

    def __init__(self, json_response, section_name: str = None):
        self.name = json_response['title']
        self.id = json_response['id']
        self.description = json_response['description']

        self.board_name = json_response['board']['name']
        self.section_name = section_name

        self.url = json_response['images']['orig']['url']
        self.extension = '.' + self.url.split('.')[-1]
        self.image_height = json_response['images']['orig']['height']
        self.image_width = json_response['images']['orig']['width']

        self.download_dir = self.board_name
        if self.section_name:
            self.download_dir = os.path.join(self.download_dir,
                                             self.section_name)
        self.image_path = os.path.join(self.download_dir,
                                       '%s%s' % (self.id, self.extension))

    def download(self) -> Image:
        ''' Downloads pin to local storage and returns the resulting Image.
        Out: Image corresponding to the just-downloaded image.
        Raises: KeyboardInterrupt if download is manually interrupted.
        '''
        if not os.path.exists(self.download_dir):
            os.makedirs(self.download_dir)

        print('\t+ ' + self.image_path)
        try:
            r = requests.get(url=self.url, stream=True)
            if r.status_code == 200:
                with open(self.image_path, 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
        except KeyboardInterrupt:
            os.remove(self.image_path)
            raise

        return Image(self.image_path)

    def to_json(self):
        pass

    def __str__(self):
        return self.id
