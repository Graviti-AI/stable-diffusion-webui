# represent a user
# each user has a standalone work dir


class User:
    def __init__(self, uid, gid):
        self._uid = uid
        self._gid = gid

    @property
    def uid(self):
        return self._uid
