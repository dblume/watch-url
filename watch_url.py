#!/usr/bin/env python3
import os
import sys
import json
import subprocess
from argparse import ArgumentParser
import logging
import time
import signal
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import hashlib


_notification = ['echo', 'URL MSG']


def log_exit(sig, frame):
    """Notify the user when a signal terminates the process."""
    logging.warning(f"PID={os.getpid()} signal={signal.Signals(sig).name} Exiting.")
    notify('Watcher exiting.')
    sys.exit(0)


def get_md5(f):
    """Make an MD5 hash of the page's contents."""
    BLOCKSIZE = 65536
    hasher = hashlib.md5()
    buf = f.read(BLOCKSIZE)
    while len(buf) > 0:
        hasher.update(buf)
        buf = f.read(BLOCKSIZE)
    return hasher.hexdigest()


def notify(msg, url=''):
    """Send a notification to the user."""
    return run([i.replace('MSG', msg).replace('URL', url) for i in _notification])


def run(command_list):
    """Pass in a linux command, get back the stdout."""
    r = subprocess.run(command_list, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, encoding='utf-8')
    logging.debug(f"subprocess.run({command_list}) got {r.returncode}.")
    if r.returncode != 0:
        logging.error(f"subprocess.run({command_list}) failed with code {r.returncode}.")
        return f"Error {r.returncode} trying to run({command_list})"
    return r.stdout


def main(urls):
    """The main function, does the whole thing."""
    global _notification
    start_time = time.time()
    with open(__file__.replace('.py', '.json')) as f:
       _notification = json.load(f)['notification']

    signal.signal(signal.SIGINT, log_exit)
    signal.signal(signal.SIGTERM, log_exit)

    logging.info(f'PID={os.getpid()} Started.')

    url = urls[0]  # Just for now.
    if len(urls) > 1:
        logging.error(f"I haven't implemented support for multiple URLs yet.")
        return

    # Get ETag and/or Last-Modified, if there is one.
    req = Request(url)
    with urlopen(req) as f:
        if f.getcode() != 200:
            logging.error(f"Got {f.getcode()} for {url}. Exiting.")
            notify(f"Got {f.getcode()} for {url}. Exiting.")
            return
        if 'ETag' in f.headers:
            req.add_header('If-None-Match', f.headers['ETag'])
            etag = f.headers['ETag']
        else:
            etag = None
        if 'Last-Modified' in f.headers:
            req.add_header('If-Modified-Since', f.headers['Last-Modified'])
            last_modified = f.headers['Last-Modified']
        else:
            last_modified = None
        md5 = get_md5(f)

    logging.debug(f"ETag={etag} last_modified={last_modified}")

    done = False
    send_confirmation_at = time.time() + 10  # seconds
    while not done:
        time.sleep(5)
        if send_confirmation_at is not None and send_confirmation_at < time.time():
            logging.info(f"Sending a notification that we're running.")
            notify("Watching", url)
            send_confirmation_at = None
        try:
            with urlopen(req) as f:
                if f.getcode() != 200:
                    # Maybe these are all covered by exceptions?
                    logging.error(f"Got {f.getcode()} for {url}. Continuing.")
                    continue
                changed = False
                if 'ETag' in f.headers and f.headers['ETag'] != etag:
                    changed = True
                if 'Last-Modified' in f.headers and f.headers['Last-Modified'] != last_modified:
                    changed = True
                if not changed and md5 != get_md5(f):
                    changed = True
                if changed:
                    notify("Site changed", url)
                    logging.info(f"Sending notification of site change.")
                    done = True
                last_modified = f.headers['Last-Modified']
        except HTTPError as e:
            if e.code == 304:
                logging.debug(f"Url not changed.")
            else:
                notify(f"Got HTTP error {e.code()}. Continuing.", url)
                logging.error(f"Got {e.code()} for {url}. Continuing.")

    logging.info(f"Exiting. Duration = {time.time() - start_time:2.0f}s.")
    notify(f"Exiting.")


if __name__ == '__main__':
    parser = ArgumentParser(description="Notify when a URL changes.")
    parser.add_argument('-o', '--outfile')
    parser.add_argument('urls', nargs='+', help='URLs to watch')
    args = parser.parse_args()
    if args.outfile is None:
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.FileHandler(args.outfile)
    logging.basicConfig(handlers=(handler,),
                        format='%(asctime)s %(levelname)s %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)
    main(args.urls)
