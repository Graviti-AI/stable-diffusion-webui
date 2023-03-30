# represent a user
# each user has a standalone work dir

class User:
    def __init__(self, uid, gid):
        self._uid = uid
        self._gid = gid

    @property
    def uid(self):
        return self._uid

    @classmethod
    def current_user(cls, request):
        uid = ''
        if request:
            headers = request.headers
            if 'user-id' in headers:
                uid = headers['user-id']
            elif 'User-Id' in headers:
                uid = headers['User-Id']
        if not uid:
            # consider user as anonymous if User-Id is not present in request headers
            uid = 'anonymous'
        return User(uid, '')
