from __future__ import annotations
import os
import requests
from concurrent.futures import ThreadPoolExecutor
from typing import Dict, List, Tuple, Optional

from dotenv import load_dotenv
from py3pin.Pinterest import Pinterest
#from tqdm import tqdm

from Container import Board, Section


MAX_THREADS = os.cpu_count() * 4


class Client:

    def __init__(self, credentials):
        print('Connecting to Pinterest...')
        self.client = Pinterest(email=credentials['email'],
                                password=credentials['password'],
                                username=credentials['username'],
                                cred_root=credentials['cred_root'])
        self.client.login()

        # get contents
        print('Collecting data...')
        with ThreadPoolExecutor(max_workers=MAX_THREADS) as exec:
            self.contents = exec.map(lambda b: Board(self.client, b),
                                     self.client.boards())

        '''
        self.contents = []
        for board in tqdm(self.client.boards(), desc='Collecting data'):
            b = Board(self.client, board)
            self.contents.append(b)
        '''

    def get_boards(self):
        return self.contents

    def find(self, board_name, section_name=None, pin_id=None):
        def find_board(board):
            for b in self.contents:
                if b.name == board:
                    return b
            raise Exception('Board not found: %s' % board)

        def find_section(b, section):
            for s in b.get_sections():
                if s.name == section:
                    return s
            raise Exception('Section not found: %s/%s' % (b.name, section))

        def find_pin(container, pin):
            for p in container.get_pins():
                if p.id == pin:
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
        self.client.logout()


if __name__ == '__main__':
    load_dotenv()
    CREDENTIALS = {
        'email' : os.getenv('PINTEREST_EMAIL'),
        'password' : os.getenv('PINTEREST_PASSWORD'),
        'username' : os.getenv('PINTEREST_USERNAME'),
        'cred_root' : os.getenv('CREDENTIALS_ROOT_DIR')
    }
    DOWNLOAD_DIR = os.getenv('DOWNLOAD_DIR')
    os.chdir(DOWNLOAD_DIR)

    c = Client(CREDENTIALS)
    for board in c.get_boards():
        print(board.name)
        board.sync()
        for section in board.get_sections():
            print('%s/%s' % (board.name, section.name))
            section.sync()
    c.logout()
