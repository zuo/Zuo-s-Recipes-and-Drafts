#!/usr/bin/env python
# Quick'n'dirty multiprocessfilehandler module test run (Unix/Linux only)
# http://code.activestate.com/recipes/577395-multiprocess-safe-logging-file-handler/

from mplogfilehandler import *

import logging
import os
import re
import sys
import threading

from itertools import islice, takewhile
from os.path import abspath
from random import randint

try:
    from itertools import filterfalse  # Py3.x
except ImportError:
    from itertools import ifilterfalse as filterfalse  # Py2.x

try: irange = xrange
except NameError:  # Py2's xrange() is range() in Py3.x
    irange = range

try: inext = next
except NameError:
    inext = lambda i: i.next()  # Py<2.6

#
# constants

PY_VER = sys.version[:3]
DEFAULT_FILENAME = 'test.log'
LOG_FORMAT = '%(asctime)s %(message)s'
REC_BODY_PATTERN = 'proc:%(pid)d thread:%(thread_ident)d rec:%%s'

LOCK_DESCR = 'per-thread', 'thread-shared'
POSSIBLE_RESULTS = 'acquired', 'released', 'not acquired'
FILLER_AFTER_NOACK = 'so nothing to release :)'

RECORD_REGEX = re.compile(
    r'('
        r'\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3} '  # time
        r'|'
        r'-{24}'  # written with stream.write()
    r')'
    r'%(py_ver)s'
    r' proc:\d+ thread:\d+ rec:'
    r'('
        r'\d+'  # record counter
        r'|'
        r'(%(msg_pattern)s)'
        r'|'
        r'%(filler_after_noack)s'
    r')$'
    % dict(
        py_ver=r'[\d\.]{%d}' % len(PY_VER),
        msg_pattern=r') ('.join((
            r'|'.join(map(re.escape, LOCK_DESCR)),
            r'<FLockRLock owner=\w+ count=\d+>',
            r'|'.join(map(re.escape, POSSIBLE_RESULTS)),
        )),
        filler_after_noack=re.escape(FILLER_AFTER_NOACK),
    )
)

#
# functions

def for_subthread(thread_shared_lock, thread_i, proc_i,
                  logrecords, locktests, filename):

    # FLockFileHandler test
    logger = logging.getLogger()
    rec_pattern = ' '.join((PY_VER, REC_BODY_PATTERN
                                    % dict(pid=proc_i,
                                           thread_ident=thread_i)))
    for rec_i in irange(logrecords):
        logger.info(rec_pattern % rec_i)

    # additional per-thread/thread-shared -files-based FLockRLock tests
    per_thread_lockfile = open(abspath(filename), 'a')
    try:
        per_thread_lock = FLockRLock(per_thread_lockfile)
        descr2locks = {'per-thread': per_thread_lock,
                       'thread-shared': thread_shared_lock}
        msg_pattern = rec_pattern % '%s %s %s'
        msg = dict((result,
                    dict((lock, msg_pattern % (descr, lock, result))
                         for descr, lock in descr2locks.items()))
                   for result in POSSIBLE_RESULTS)
        msg_acquired = msg['acquired']
        for lock, m in msg_acquired.items():
            # to be written directly to the file -- to avoid deadlock
            msg_acquired[lock] = ''.join((24 * '-', m, '\n'))
        filler_after_noack = rec_pattern % FILLER_AFTER_NOACK
        locks = list(descr2locks.values())  # Py3's .values() -> a view
        for i in irange(locktests):
            if randint(0, 1):
                iterlocks = iter(locks)
            else:
                iterlocks = reversed(locks)
            for lock in iterlocks:
                if lock.acquire(blocking=randint(0, 1)):
                    try:
                        lock.lockfile.write(msg['acquired'][lock])
                        lock.lockfile.flush()
                    finally:
                        lock.release()
                        logger.info(msg['released'][lock])
                else:
                    logger.info(msg['not acquired'][lock])
                    logger.info(filler_after_noack)
    finally:
        per_thread_lockfile.close()


def for_subprocess(proc_i, subthreads, logrecords, locktests, filename):

    # setting up logging to test FLockFileHandler
    f = logging.Formatter(LOG_FORMAT)
    h = FLockFileHandler(filename)
    h.setFormatter(f)
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.addHandler(h)

    # (standalone FLockRLock instance also to be tested)
    thread_shared_lockfile = open(abspath(filename), 'a')
    try:
        thread_shared_lock = FLockRLock(thread_shared_lockfile)
        threads = [threading.Thread(target=for_subthread,
                                    args=(thread_shared_lock,
                                          thread_i, proc_i,
                                          logrecords, locktests,
                                          filename))
                   for thread_i in irange(subthreads)]
        for t in threads: t.start()
        for t in threads: t.join()  # wait for subthreads
    finally:
        thread_shared_lockfile.close()


def check_types():
    isinstance(FLockRLock, MultiprocessRLock)
    isinstance(LockedFileHandler, MultiprocessFileHandler)
    isinstance(FLockFileHandler, LockedFileHandler)


def check_records_only(filename):
    logfile = open(abspath(filename))
    try:
        try:
            badline = inext(filterfalse(RECORD_REGEX.match, logfile))
        except StopIteration:
            return "OK"
        else:
            sys.exit('Invalid record found: %s' % badline)
    finally:
        logfile.close()


def check_records_and_len(filename, expected_len):
    logfile = open(abspath(filename))
    try:
        # Py2.4-compatibile fast way to check file content and length
        file_ending = islice(takewhile(RECORD_REGEX.match, logfile),
                             expected_len - 1, expected_len + 1)
        try:
            inext(file_ending)
        except StopIteration:
            sys.exit('Too few valid lines found (%d expected)'
                     % expected_len)
        # at this point the file content should have been read entirely
        try:
            inext(file_ending)
        except StopIteration:
            return "OK"
        else:
            sys.exit('Too many valid (?) lines found (%d expected)'
                     % expected_len)
    finally:
        logfile.close()

#
# the script function

def main(subprocs=3, subthreads=3, logrecords=5000,
         locktests=500, firstdelete=1, filename=DEFAULT_FILENAME):

    # args may origin from command line, so we map it to int
    (subprocs, subthreads, logrecords, firstdelete, locktests
    ) = map(int, (subprocs, subthreads, logrecords, firstdelete, locktests))

    # expected number of generated log records
    expected_len = subprocs * subthreads * (logrecords + (4 * locktests))

    if firstdelete:
        try:
            os.remove(abspath(filename))
        except OSError:
            pass

    for proc_i in irange(subprocs):
        if not os.fork():
            # we are in a subprocess
            for_subprocess(proc_i, subthreads, logrecords,
                           locktests, filename)
            break
    else:
        # we are in the parent process
        for i in irange(subprocs):
            os.wait()  # wait for subprocesses

        # finally, check the resulting log file content
        if firstdelete:
            print(check_records_and_len(filename, expected_len))
        else:
            print(check_records_only(filename))

# * try running the script simultaneously using different Python versions :) *
if __name__ == '__main__':
    main(*sys.argv[1:])
