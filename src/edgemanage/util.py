import fcntl

def acquire_lock(lockfile):
    # lockfile should be an opened file in mode w

    try:
        fcntl.lockf(lockfile, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except IOError:
        return False

    return True
