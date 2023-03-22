# represent a user
# each user has a standalone work dir

class User:
    def __init__(self, uid, gid, tire):
        self._uid = uid
        self._gid = gid
        self._tire = tire

    @property
    def uid(self):
        return self._uid

    @property
    def tire(self):
        return self._tire

    @classmethod
    def current_user(cls, request):
        uid = ''
        tire = ''
        if request:
            headers = request.headers
            if 'user-id' in headers:
                uid = headers['user-id']
            elif 'User-Id' in headers:
                uid = headers['User-Id']
            if 'User-Tire' in headers:
                tire = headers['User-Tire']
            elif 'user-tire' in headers:
                tire = headers['user-tire']
        if not uid:
            # consider user as anonymous if User-Id is not present in request headers
            uid = 'anonymous'
        return User(uid, '', tire)
