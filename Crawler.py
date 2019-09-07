"""
    Collect webm from 4chan and broadcast them to FM radio using raspberry pi
    I know, this sounds like a bad idea and it is,
    but at this point there is no way back now
"""
import hashlib
import html
import json
import logging
import pickle
import re
import time
import _thread
import requests
import os
import argparse
from urllib.request import urlretrieve

# following is the line where you define your searches
search_word = "ygyl"
search_type = ["webm"]
search_board = ["wsg", "gif"]


class Piradio4Chan:
    file_hashes = []
    storage_file = "storage.pkl"


    def __init__(self, keyword, input_file_types, input_boards, input_folder=None):
        self.headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_10_1)\
         AppleWebKit/537.36 (KHTML, like Gecko) Chrome/39.0.2171.95 Safari/537.36'}
        self.keyword = keyword
        self.file_types = input_file_types
        self.boards = input_boards
        self.playlist = []
        self.index = 0
        self.refresh_rate = 600
        self.base_dir = os.getcwd()
        self.folder = input_folder
        self.sleep_max = 7
        self.sleep_count = 0

        logging.basicConfig(level=logging.WARNING,
                            format='%(asctime)s %(levelname)s %(message)s',
                            datefmt='%a, %d %b %Y %H:%M:%S',
                            filename='links.log',
                            filemode='a')

    def start(self):
        if not self.folder:
            # remove special letters and then make camel case
            folder = ''.join(x for x in self.keyword.title() if not x.isspace())
            self.folder = re.sub(r'[\W_]+', '', folder)[:15]

        self.folder_dir = os.path.join(self.base_dir, self.folder)
        self.storage_file = self.folder_dir+"/"+self.storage_file

        if os.path.isfile(self.storage_file):
            self.file_hashes = pickle.load(open(self.storage_file, "rb"))

        print("Searching for {} in board {} with file type {}".format(self.keyword, self.boards, self.file_types))
        if not os.path.exists(self.folder_dir):
            print("Creating folder: {}".format(self.folder_dir))
            os.mkdir(self.folder_dir)


        # start the downloader
        _thread.start_new_thread(self.download, ("Downloader", 1))
        # start the collector
        while True:
            self.collect()

    def download(self, name, thread_num):
        index = 0
        while True:
            if index < len(self.playlist):
                self.sleep_count = 0
                selected = self.playlist[index]
                index += 1
                board, thread_id, post_id, file = selected.split("@")
                link = "boards.4chan.org/{}/thread/{}".format(board, thread_id)
                filename = file.rsplit("/", 1)[-1]
                local_filename = self.folder_dir+"/"+filename
                if os.path.isfile(self.folder_dir+"/"+filename):
                    print("Skipping {} for duplicate file name.".format(filename))
                    continue
                print("Downloading:{} : No.{}. ,Downloaded {} files.".format(link, post_id,index))
                try:
                    time.sleep(2)
                    urlretrieve(file, local_filename)
                    sha1 = hashlib.sha1()
                    with open(local_filename, 'rb') as f:
                        while True:
                            data = f.read(65536)
                            if not data:
                                break
                            sha1.update(data)
                    new_hash = sha1.hexdigest()
                    if new_hash in self.file_hashes:
                        print("{} is a repost REEEEE!!", filename)
                        os.remove(filename)
                        continue
                    self.file_hashes.append(new_hash)
                    pickle.dump(self.file_hashes, open(self.storage_file, 'wb'))

                except OSError:
                    logging.warning("Unable to download {}.".format(str(file)))
                else:
                    logging.info("Downloaded {}.".format(str(file)))

            # if playlist tasks finished increase sleep time
            else:
                sleep_time = pow(2, self.sleep_count)
                print("Empty job list, retrying after {} seconds...".format(sleep_time))
                time.sleep(sleep_time)
                if self.sleep_count < self.sleep_max:
                    self.sleep_count += 1

    # adding new match to the list
    def collect(self):
        for board in self.boards:
            for page_num in range(1, 11):
                page_data = requests.get('https://a.4cdn.org/{}/{}.json'.format(board, page_num), headers=self.headers)
                page_data = json.loads(page_data.content.decode('utf-8'))
                threads = page_data["threads"]
                print('>>Searching https://a.4cdn.org/{}/{}.json'.format(board, page_num))
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
                        if self.keyword.upper() in  html.unescape(op['name']).upper():
                            qualified = True

                    if "sub" in op:
                        if self.keyword.upper() in html.unescape(op['sub']).upper():
                            qualified = True

                    # check comment section if there are comments
                    if "com" in op:
                        if self.keyword.upper() in html.unescape(op["com"]).upper():
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
        time.sleep(300)  # sleep for each rescan


parser = argparse.ArgumentParser()
parser.add_argument("-k", help="keywords")
parser.add_argument("-b", "--board", nargs='*', help="boards to crawl files from")
parser.add_argument("-t", "--type", nargs="*", help="file types to crawl")
parser.add_argument("-f", help="target folder")

args = parser.parse_args()

x = Piradio4Chan(search_word, search_type, search_board)
if args.k:
    x.keyword = args.k
if args.board:
    x.boards = args.board
if args.type:
    x.file_types = args.type
if args.f:
    x.folder = args.f

x.start()
