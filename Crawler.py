"""
    Collect webm from 4chan and broadcast them to FM radio using raspberry pi
    I know, this sounds like a bad idea and it is,
    but at this point there is no way back now
"""
import hashlib
import json
import logging
import pickle
import subprocess
import time
import _thread
import requests
import os
from random import randrange
import argparse
from urllib.request import urlretrieve


# following is the line where you define your searches
search_word = "ygyl"
search_type = ["webm"]
search_board = ["gif", "wsg"]

class Piradio4Chan:
    file_hashes = []
    storage_file = "storage.pkl"

    def __init__(self, keyword, input_file_types, input_boards, input_refresh_rate):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1)\
         AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
        self.keyword = keyword
        self.file_types = input_file_types
        self.playlist = []
        self.index = 0
        self.boards = input_boards
        self.refresh_rate = input_refresh_rate
        self.frequency = "87.9"
        self.shuffle = False
        self.ps = "Piradio"
        self.rt = "Raspberry pi Radio Staion"
        self.pi = "2333"

        if os.path.isfile(self.storage_file):
            self.file_hashes = pickle.load(open(self.storage_file, "rb"))
        logging.basicConfig(level=logging.WARNING,
                            format='%(asctime)s %(levelname)s %(message)s',
                            datefmt='%a, %d %b %Y %H:%M:%S',
                            filename='links.log',
                            filemode='a')

    def start(self):
        _thread.start_new_thread(self.play, ("Downloader", 1))
        while True:
            self.collect()
            time.sleep(self.refresh_rate)

    def play(self, name, thread_num):
        while True:
            if self.playlist:
                if self.shuffle:
                    temp = self.index
                    self.index = randrange(0, len(self.playlist))
                    # if shuffle back to the same place
                    if temp == self.index:
                        if temp == len(self.playlist) - 1:
                            self.index = 0
                        else:
                            self.index += 1
                else:
                    self.index += 1
                    if self.index == len(self.playlist):
                        self.index = 0
                selected = self.playlist[self.index]
                board, thread_id, post_id, file = selected.split("@")
                link = "boards.4chan.org/{}/thread/{}".format(board, thread_id)
                print("~" * 80)
                filename = file.rsplit("/", 1)[-1]
                if (os.path.isfile(filename)):
                    print("skipping ", filename)
                    continue
                print("Downloading:", link, ": No." + post_id + ". ")
                print(file)

                try:
                    time.sleep(2)
                    urlretrieve(file, filename)
                    sha1 = hashlib.sha1()
                    with open(filename, 'rb') as f:
                        while True:
                            data = f.read(65536)
                            if not data:
                                break
                            sha1.update(data)
                    new_hash = sha1.hexdigest()
                    if new_hash in self.file_hashes:
                        print("god damn reposts")
                        os.remove(filename)
                        continue
                    self.file_hashes.append(new_hash)
                    pickle.dump(self.file_hashes, open(self.storage_file, 'wb'))


                except OSError:
                    logging.warning("Unable to download {}".format(str(file)))
                else:
                    logging.info("Downloaded {}".format(str(file)))

    def collect(self):
        for board in self.boards:
            for page_num in range(1, 10):
                page_data = requests.get('https://a.4cdn.org/{}/{}.json'.format(board, page_num), headers=self.headers)
                page_data = json.loads(page_data.content.decode('utf-8'))
                threads = page_data["threads"]
                print('https://a.4cdn.org/{}/{}.json'.format(board, page_num))
                for thread in threads:
                    # boolean checker to see if current post meets qualification
                    qualified = False
                    # original poster
                    op = thread["posts"][0]
                    # op's thread id
                    op_id = op["no"]

                    # check title and op name
                    if self.keyword in (op['semantic_url']):
                        qualified = True

                    if "name" in op:
                        if self.keyword.upper() in op['name'].upper():
                            qualified = True

                    if "sub" in op:
                        if self.keyword.upper() in op['sub'].upper():
                            qualified = True                   

                    # check comment section if there are comments
                    if "com" in op:
                        if self.keyword.upper() in op["com"].upper():
                            qualified = True

                    if qualified:
                        thread_data = requests.get("https://a.4cdn.org/{}/thread/{}.json"
                                                   .format(board, op_id),
                                                   headers=self.headers)
                        thread_response = json.loads(thread_data.content.decode('utf-8'))
                        # posts is a list of post
                        posts = thread_response["posts"]

                        # variable post is a dict with info about each post
                        for post in posts:
                            if "ext" in post and post["ext"][1:] in self.file_types:
                                download_link = "https://i.4cdn.org/{}/{}{}".format(board, post["tim"], post["ext"])
                                pending = board + "@" + str(op_id) + "@" + str(post["no"]) + "@" + download_link
                                if download_link not in self.playlist:
                                    self.playlist.append(pending)
                time.sleep(1)  # sleep for each page
            time.sleep(10)  # sleep for each board
        time.sleep(120)  # sleep for each rescan


parser = argparse.ArgumentParser()
parser.add_argument("-k", help="keyword")
parser.add_argument("-f", "--frequency", help="FM frequency")
parser.add_argument("-b", "--board", nargs='*')
parser.add_argument("-s", "--shuffle", action="store_true")
parser.add_argument("-ps")
parser.add_argument("-rt")
parser.add_argument("-pi")
args = parser.parse_args()


x = Piradio4Chan(search_word , search_type, search_board, 60 * 10)
if args.k:
    x.keyword = args.k
if args.frequency:
    x.frequency = args.frequency
if args.board:
    x.boards = args.board
x.shuffle = args.shuffle
if args.ps:
    x.ps = args.ps
if args.rt:
    x.rt = args.rt
if args.pi:
    x.pi = args.pi

x.start()
