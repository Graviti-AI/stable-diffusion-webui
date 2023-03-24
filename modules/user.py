# represent a user
# each user has a standalone work dir
import starlette.requests


class User:
    def __init__(self, uid, gid):
        self._uid = uid
        self._gid = gid

    @property
    def uid(self):
        return self._uid

    @classmethod
    def current_user(cls, request: starlette.requests.Request):
        if request:
            uid = request.headers.get('User-Id', '')
        else:
            uid = ''
        if not uid:
            # consider user as anonymous if User-Id is not present in request headers
            uid = 'anonymous'
        return User(uid, '')
