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
import threading
from typing import Optional, BinaryIO, List


_notification = ['echo', 'URL MSG']
notify_lock = threading.Lock()


def log_exit(sig: int, frame) -> None:
    """Notify the user when a signal terminates the process."""
    logging.warning(f"PID={os.getpid()} signal={signal.Signals(sig).name} Exiting.")
    notify('Watcher exiting.')
    sys.exit(0)


def get_md5(f: BinaryIO) -> str:
    """Make an MD5 hash of the page's contents."""
    BLOCKSIZE = 65536
    hasher = hashlib.md5()
    buf = f.read(BLOCKSIZE)
    while len(buf) > 0:
        hasher.update(buf)
        buf = f.read(BLOCKSIZE)
    return hasher.hexdigest()


def notify(msg: str, url: str='') -> str:
    """Send a notification to the user."""
    with notify_lock:
        return run([i.replace('MSG', msg).replace('URL', url) for i in _notification])


def run(command_list: List[str]) -> str:
    """Pass in a linux command, get back the stdout."""
    r = subprocess.run(command_list, stdout=subprocess.PIPE,
                       stderr=subprocess.PIPE, encoding='utf-8')
    logging.debug(f"subprocess.run({command_list}) got {r.returncode}.")
    if r.returncode != 0:
        logging.error(f"subprocess.run({command_list}) failed with code {r.returncode}.")
        return f"Error {r.returncode} trying to run({command_list})"
    return r.stdout


def watch(url: str, delay: float) -> None:
    """Repeatedly make requests to one URL and watch for changes."""
    # Get ETag and/or Last-Modified, if there is one.
    req = Request(url)
    with urlopen(req) as f:
        if f.getcode() != 200:
            logging.error(f"Got {f.getcode()} for {url}. Exiting.")
            notify(f"Got HTTP {f.getcode()}. Exiting.", url)
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

    logging.debug(f"{url}: ETag={etag} last_modified={last_modified}")

    done = False
    send_confirmation_at: Optional[float] = time.time() + 10  # seconds
    while not done:
        time.sleep(delay)
        if send_confirmation_at is not None and send_confirmation_at < time.time():
            logging.info(f"Sending a notification for {url} that we're running.")
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
                if ('Last-Modified' in f.headers and
                    f.headers['Last-Modified'] != last_modified):
                    changed = True
                if not changed and md5 != get_md5(f):
                    changed = True
                if changed:
                    notify("Site changed", url)
                    logging.info(f"Sending notification of change to {url}.")
                    done = True
                last_modified = f.headers['Last-Modified']
        except HTTPError as e:
            if e.code == 304:
                logging.debug(f"{url} not changed.")
            else:
                notify(f"Got HTTP error {e.code}. Continuing.", url)
                logging.error(f"Got {e.code} for {url}. Continuing.")

    logging.info(f"Stopping for {url}.")


if __name__ == '__main__':
    parser = ArgumentParser(description="Notify when a URL changes.")
    parser.add_argument('-d', '--delay', type=float, default=5.0,
                        help='Delay between requests')
    parser.add_argument('-o', '--outfile')
    parser.add_argument('urls', nargs='+', help='URLs to watch')
    parser_args = parser.parse_args()
    if parser_args.outfile is None:
        handler = logging.StreamHandler(sys.stdout)
    else:
        handler = logging.FileHandler(parser_args.outfile)
    logging.basicConfig(handlers=(handler,),
                        format='%(asctime)s %(levelname)s %(thread)d %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S',
                        level=logging.INFO)

    with open(__file__.replace('.py', '.json')) as f:
       _notification = json.load(f)['notification']

    signal.signal(signal.SIGINT, log_exit)
    signal.signal(signal.SIGTERM, log_exit)

    logging.info(f'PID={os.getpid()} Starting with -d '
                 f'{parser_args.delay} {" ".join(parser_args.urls)}')
    if len(parser_args.urls) == 1:
        watch(parser_args.urls[0], parser_args.delay)
    else:
        threads = []
        for url in parser_args.urls:
            t = threading.Thread(target=watch, args=(url, parser_args.delay),
                                 daemon=True)
            t.start()
            threads.append(t)
        for t in threads:
            t.join()
    logging.info(f'PID={os.getpid()} All watchers exited.')
