import json
import os

from dotenv import load_dotenv

from Manifest import Manifest
from Client import Client


''' Basic sync algorithm:
1) Check for local files which have been deleted since last sync.
    a) Search for files which appear in old manifest, but are not observed in
       filesystem.  This implies that they must have been deleted in the time
       between the last sync (when the manifest was saved) and now.
2) Remove files which have been deleted from Pinterest.
    a) Gather lists of local and Pinterest files.  Remove any local file which
       is not observed in the Pinterest list.
3) Download files which have been added to Pinterest.
    a) Using the lists of local/Pinterest contents, download any file that is
       contained in the Pinterest list, but not in the local one.
4) Remove duplicate images:
    a) Update local list, then hash contents.  Any hashes that describe more
       than 1 file refer to duplicates.
    b) Keep local file that is highest in resolution (img_height x img_width).
       If a tie is encountered, keep the older file (lowest id).
'''

'''
More OOP:
- Board object.  Sections/pins/id/etc
- Section object.
- metadata stored within each board/section
'''


load_dotenv()
CREDENTIALS = {
    'email' : os.getenv('PINTEREST_EMAIL'),
    'password' : os.getenv('PINTEREST_PASSWORD'),
    'username' : os.getenv('PINTEREST_USERNAME'),
    'cred_root' : os.getenv('CREDENTIALS_ROOT_DIR')
}
DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR')


class Manager:
    '''Central control structure.  Performs syncing operations to clone
    Pinterest boards/sections to local storage.

    In: pinterest_credentials <dict[str]>, a dictionary containing login
            credentials for a particular Pinterest account.
        download_dir <str>, path to local download directory.
    '''

    def __init__(self, pinterest_credentials):
        self.client = Client(pinterest_credentials)
        self.manifest = Manifest()

    def sync(self, board, section=None):
        '''Sync a board/section on Pinterest to local storage.

        In: board <str>, name of board (on pinterest) to sync.
            section <str>, name of section (on pinterest) to sync.  None
                represents the base board, disregarding any sections that may
                be present.
        '''
        # Reflect local changes:
        self.push_local_changes(board, section)

        # Remove local files that have been deleted from Pinterest:
        local = self.manifest.find(board, section)
        cloud = self.client.find(board, section)
        local_ids = [image.get_id() for image in local.get_images()]
        cloud_ids = [pin.get_id() for pin in cloud.get_pins()]
        for image in local.get_images():
            if image.get_id() not in cloud_ids:
                image.delete()

        # Download images that are missing on local storage:
        for pin in cloud.get_pins():
            if pin.get_id() not in local_ids:
                pin.download()

        # Delete duplicates:
        for image in local.remove_duplicates(board, section):
            try:
                cloud.delete(image.get_id())
            except:
                pass

    def push_local_changes(self, board, section=None):
        container = self.manifest.find(board, section)
        deleted = container.get_deleted_images()
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
                    try:
                        cloud_container = self.client.find(board, section)
                        cloud_container.delete(id)
                    except:
                        pass
            print()

    def sync_all(self):
        '''Syncs all boards of current user to local storage.'''
        for board in self.client.get_boards():
            print('%s' % board)
            self.sync(board.get_name())
            for section in board.get_sections():
                print('%s/%s' % (board, section))
                self.sync(board.get_name(), section.get_name())
        self.manifest.save()


if __name__ == '__main__':
    os.chdir(DOWNLOAD_DIR)

    p = Manager(CREDENTIALS)
    p.sync('test')
    p.client.logout()
