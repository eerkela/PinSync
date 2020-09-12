import os
import requests

from dotenv import load_dotenv
from py3pin.Pinterest import Pinterest


class Pin:
    '''Defines a pin object given its response from the Pinterest API
    (API Reference: https://developers.pinterest.com/docs/api/pins/).

    In: pin_response <dict[str]>, response from Pinterest API describing a
            single pin.
        section_name <str>, name of section (if any) to which the pin belongs.
    '''


    def __init__(self, json_response, section_name=None):
        self.id = json_response['id']
        self.name = json_response['title']
        self.description = json_response['description']

        self.board = json_response['board']['name']
        self.section = section_name

        self.url = json_response['images']['orig']['url']
        self.extension = '.' + self.url.split('.')[-1]
        self.image_height = json_response['images']['orig']['height']
        self.image_width = json_response['images']['orig']['width']

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

        # build board name - id map
        self.boards = {}
        for b in self.client.boards():
            self.boards[b['name']] = b['id']

        # build section name - id map for each board
        self.sections = {}
        for board in self.boards.keys():
            self.sections[board] = {}
            board_id = self.boards[board]
            for s in self.client.get_board_sections(board_id=board_id):
                self.sections[board][s['title']] = s['id']

        # set up pin cache
        self.cache = {}

    def get_boards(self):
        '''Retrieves list of all boards belonging to current user.'''
        return list(self.boards.keys())

    def get_sections(self, board):
        '''Retrieves list of sections within associated board.  Throws KeyError
        if board cannot be found.'''
        if board not in self.get_boards():
            raise KeyError('Board not found: %s' % board)
        return list(self.sections[board].keys())

    def get_pins(self, board, section=None):
        '''Retrieves list of pins within named board/section.

        In: board <str>, name of board to retrieve contents of.
            section <str>, name of section within board to retrieve
                contents of.  None represents the base board, disregarding any
                sections that may be present.
        Out: List[Pin] of pins present within board/section.
        '''
        if board in self.cache.keys():
            if not section:
                return [v for v in self.cache[board].values()
                        if isinstance(v, Pin)]
            elif section in self.cache[board].keys():
                return list(self.cache[board][section].values())


        if section:
            section_id = self.sections[board][section]
            pins = []
            batch = self.client.get_section_pins(section_id=section_id)
            while (batch):
                for response in batch:
                    try:
                        p = Pin(response, section)
                    except:
                        continue
                    pins.append(p)
                batch = self.client.get_section_pins(section_id=section_id)
            if board not in self.cache.keys():
                self.cache[board] = {}
            if section not in self.cache[board].keys():
                self.cache[board][section] = {}
            for pin in pins:
                self.cache[board][section][pin.id] = pin
            return pins

        board_id = self.boards[board]
        pins = []
        batch = self.client.board_feed(board_id=board_id)
        while (batch):
            for response in batch:
                try:
                    p = Pin(response)
                except:
                    continue
                pins.append(p)
            batch = self.client.board_feed(board_id=board_id)
        if board not in self.cache.keys():
            self.cache[board] = {}
        for pin in pins:
            self.cache[board][pin.id] = pin
        return pins

    def delete(self, pin_id, board, section=None):
        ''' Deletes a pin from Pinterest.

        In: pin_id <str>, id of pin to delete.
            board <str>, name of board to delete pin from.
            section <str>, name of section to delete pin from, if any.
        Out: Bool, true if deletion successful.
        Throws: Exception if pin is not present on Pinterest.
        '''
        ids = [p.id for p in self.get_pins(board, section)]
        if pin_id in ids:
            self.client.delete_pin(pin_id=pin_id)
            if section:
                self.cache[board][section].pop(pin_id)
            else:
                self.cache[board].pop(pin_id)
            return True
        return False

    def print(self, board, section=None):
        '''Prints structure and member pins present in Pinterest feed.  If
        board is specified, limits results to given board.

        In: board <str>, name of board, if any, to limit results to.
        Out: void.  Prints results to console.
        '''
        if section:
            print('\t%s' % section)
            for pin in self.get_pins(board, section):
                print('\t\t%s' % pin.id)
        else:
            print('%s' % board)
            for pin in self.get_pins(board):
                print('\t%s' % pin.id)
            for section in self.get_sections(board):
                print('\t%s' % section)
                for pin in self.get_pins(board, section):
                    print('\t\t%s' % pin.id)

    def print_all(self):
        for board in self.get_boards():
            self.print(board)

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




    '''
    simulated_pin_response = {
        'id' : '123456789',
        'title' : 'xyz',
        'description' : None,
        'board' : 'test_board',
        'images' : {
            'orig' : {
                'url' : 'www.notreal.jpg',
                'height' : 44,
                'width' : 200
            }
        }
    }

    p = Pin(simulated_pin_response, 'test_section')
    pins = []
    pins.append(p)
    for temp in pins:
        print(temp.id)
        print(temp.name)
        print(temp.description)
        print(temp.board)
        print(temp.section)
    '''
