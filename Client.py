import os
import requests

from dotenv import load_dotenv
from py3pin.Pinterest import Pinterest


class Container:

    client = None
    name = None
    id = None
    pins = []

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id

    def get_pins(self):
        return self.pins

    def download(self):
        for pin in self.pins:
            pin.download()

    def delete(self, pin_id):
        index = 0
        for p in self.pins:
            if p.get_id() == pin_id:
                self.client.delete_pin(pin_id=pin_id)
                return self.pins.pop(index)
            index += 1
        return None

    def __str__(self):
        return self.name


class Board(Container):

    def __init__(self, client, json_response):
        self.client = client
        self.name = json_response['name']
        self.id = json_response['id']

        # get board sections
        self.sections = []
        for section in self.client.get_board_sections(board_id=self.id):
            s = Section(self.client, section)
            self.sections.append(s)

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

    def get_sections(self):
        return self.sections


class Section(Container):

    def __init__(self, client, json_response):
        self.client = client
        self.name = json_response['title']
        self.id = json_response['id']

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


class Pin:
    '''Defines a pin object given its response from the Pinterest API
    (API Reference: https://developers.pinterest.com/docs/api/pins/).

    In: pin_response <dict[str]>, response from Pinterest API describing a
            single pin.
        section_name <str>, name of section (if any) to which the pin belongs.
    '''

    def __init__(self, json_response, section_name=None):
        self.name = json_response['title']
        self.id = json_response['id']
        self.description = json_response['description']

        self.board = json_response['board']['name']
        self.section = section_name

        self.url = json_response['images']['orig']['url']
        self.extension = '.' + self.url.split('.')[-1]
        self.image_height = json_response['images']['orig']['height']
        self.image_width = json_response['images']['orig']['width']

    def get_name(self):
        return self.name

    def get_id(self):
        return self.id

    def get_description(self):
        return self.description

    def get_board(self):
        return self.board

    def get_section(self):
        return self.section

    def get_url(self):
        return self.url

    def get_extension(self):
        return self.extension

    def get_dimensions(self):
        return (self.image_height, self.image_width)

    def download(self, root_dir):
        ''' Downloads a given pin to local storage.

        In: pin <Pin>, Pin object describing a Pinterest pin.
            root_dir <str>, path to parent directory on local_storage.  This
                is not a path to a particular board/section, but rather to the
                top-level parent of the local repository.
        Out: void.
        Throws: Exception if root_dir is not present on local storage.
        '''
        path = os.path.join(root_dir, self.board)
        if self.section:
            path = os.path.join(path, self.section)
        if not os.path.exists(path):
            os.makedirs(path)

        path = os.path.join(path, self.id + self.extension)
        print('\t+ ' + path)
        try:
            r = requests.get(url=self.url, stream=True)
            if r.status_code == 200:
                with open(path, 'wb') as f:
                    for chunk in r.iter_content(1024):
                        f.write(chunk)
        except KeyboardInterrupt:
            os.remove(path)
            raise

    def __str__(self):
        return self.id


class Client:
    '''Wrapper for Pinterest API interactions.

    In: email <str>, email on record for associated Pinterest account.
        password <str>, password for associated Pinterest account.
        username <str>, username of associated Pinterest accound.
        cred_root <str>, path to local credentials directory.
    '''

    def __init__(self, credentials):
        print('Connecting to Pinterest...')
        self.client = Pinterest(email=credentials['email'],
                                password=credentials['password'],
                                username=credentials['username'],
                                cred_root=credentials['cred_root'])
        self.client.login()

        # get contents
        self.contents = []
        for board in self.client.boards():
            b = Board(self.client, board)
            self.contents.append(b)

    def get_boards(self):
        '''Retrieves list of all boards belonging to current user.'''
        return self.contents

    def get_sections(self, board):
        '''Retrieves list of sections within associated board.  Throws KeyError
        if board cannot be found.'''
        b = self.find(board)
        return b.get_sections()

    def get_pins(self, board, section=None):
        '''Retrieves list of pins within named board/section.

        In: board <str>, name of board to retrieve contents of.
            section <str>, name of section within board to retrieve
                contents of.  None represents the base board, disregarding any
                sections that may be present.
        Out: List[Pin] of pins present within board/section.
        '''
        container = self.find(board, section)
        return container.get_pins()

    def find(self, board_name, section_name=None, pin_id=None):
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

        def find_pin(container, pin):
            for p in container.get_pins():
                if p.get_id() == pin:
                    return p
            raise Exception('Pin not found: %s' % pin)

        b = find_board(board_name)
        if section_name:
            s = find_section(b, section_name)
            if pin_id:
                return find_pin(s, pin_id)
            return s
        if pin_id:
            return find_pin(b, pin_id)
        return b


    def logout(self):
        '''Log out of current Pinterest session.'''
        self.client.logout()


if __name__ == '__main__':
    load_dotenv()
    credentials = {
        'email' : os.getenv('PINTEREST_EMAIL'),
        'password' : os.getenv('PINTEREST_PASSWORD'),
        'username' : os.getenv('PINTEREST_USERNAME'),
        'cred_root' : os.getenv('CREDENTIALS_ROOT_DIR')
    }

    c = Client(credentials)
    for b in c.get_boards():
        print('%s' % b.get_name())
        for p in b.get_pins():
            print('\t%s' % p.get_id())
        for s in b.get_sections():
            print('\t%s' % s.get_name())
            for p in s.get_pins():
                print('\t\t%s' % p.get_id())
