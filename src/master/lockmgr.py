#!/usr/bin/python3

'''
This module is the manager of threadings locks.
A LockMgr manages multiple threadings locks.
'''

import threading


class LockMgr:

    def __init__(self):
        # self.locks will store multiple locks by their names.
        self.locks = {}
        # the lock of self.locks, is to ensure that only one thread can update it at the same time
        self.locks_lock = threading.Lock()

    # acquire a lock by its name
    def acquire(self, lock_name):
        self.locks_lock.acquire()
        if lock_name not in self.locks.keys():
            self.locks[lock_name] = threading.Lock()
        self.locks_lock.release()
        self.locks[lock_name].acquire()
        return

    # release a lock by its name
    def release(self, lock_name):
        if lock_name not in self.locks.keys():
            return
        self.locks[lock_name].release()
        return
