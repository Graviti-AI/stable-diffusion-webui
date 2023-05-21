import json
import logging
import os
import pickle

from fastapi import Request


def _get_redis_address(redis_address: str = ''):
    if not redis_address:
        redis_address = os.getenv('REDIS_ADDRESS', '')
    return redis_address


def _get_redis_client(redis_address):
    import redis
    return redis.Redis.from_url(url=redis_address)


class _RedisBasedSessionStateHolder:
    """
    Hold app session state in redis, then every node can get same state with session_hash
    """
    SESSION_HASH_KEY = 'GRADIO-SESSION'
    SESSION_HASH_TTL = 3 * 24 * 60 * 60

    def __init__(self, key_type, redis_client, default_factory=None):
        self._redis_client = redis_client
        self._state_cache = {}
        self._default_factory = default_factory
        self._key_type = key_type

    def _key_name(self, session_hash):
        return f'{self.SESSION_HASH_KEY}-{session_hash}-{self._key_type}'

    def _load_state_from_redis(self, session_hash):
        try:
            buff = self._redis_client.getex(self._key_name(session_hash), ex=self.SESSION_HASH_TTL)
            if not buff:
                logging.warning(f'not found session state from redis, session_has: {session_hash}')
                return None
            return pickle.loads(buff)
        except Exception as e:
            logging.error(f'load state from redis failed, session_hash: {session_hash}, err: {e.__str__()}')
            return None

    def persistent_state(self, session_hash):
        if session_hash not in self._state_cache:
            logging.warning(f'try to persistent non existing session state to redis: {session_hash}')
            return

        try:
            buff = self._dump_session_state(self[session_hash])
            if buff:
                self._redis_client.setex(self._key_name(session_hash), self.SESSION_HASH_TTL, buff)
        except Exception as e:
            logging.error(f'failed to persistent session state to redis: {e.__str__()}')
        del self._state_cache[session_hash]

    @staticmethod
    def _dump_session_state(state):
        try:
            buff = pickle.dumps(state, fix_imports=False)
        except Exception as e:
            print(e.__str__())
            buff = None
        return buff

    def __getitem__(self, session_hash):
        # refresh cache
        if session_hash not in self._state_cache:
            state = self._load_state_from_redis(session_hash)
            if state is not None:
                self._state_cache[session_hash] = state

        # get value from cache
        if session_hash not in self._state_cache and self._default_factory:
            self._state_cache[session_hash] = self._default_factory()
        return self._state_cache[session_hash]

    def __setitem__(self, session_hash, state):
        self._state_cache[session_hash] = state

    def __contains__(self, session_hash):
        return self._redis_client.expire(self._key_name(session_hash), self.SESSION_HASH_TTL) > 0

    def __delitem__(self, session_hash):
        del self._state_cache[session_hash]


class _StateSerializer:
    """
    a context manager for state holder
    """

    def __init__(self, state_caches: list[_RedisBasedSessionStateHolder], session_hash):
        self._session_hash = session_hash
        self._state_holders = state_caches

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        for state_holder in self._state_holders:
            state_holder.persistent_state(self._session_hash)


def _make_persistent_state_middleware(state_holders: list):
    async def set_body(request: Request, body: bytes):
        """
        this is a workaround to fix fastapi issue "Awaiting request body in middleware blocks the application",
        see https://github.com/tiangolo/fastapi/issues/394 for more information
        """

        async def receive():
            return {"type": "http.request", "body": body}

        request._receive = receive

    async def get_body(request: Request) -> bytes:
        """
        this is a workaround to fix fastapi issue "Awaiting request body in middleware blocks the application",
        see https://github.com/tiangolo/fastapi/issues/394 for more information
        """
        body = await request.body()
        await set_body(request, body)
        return body

    async def persistent_state(request, call_next):
        path = request.url.path
        if path in ('/run/predict', '/run/predict/', '/reset/', '/reset'):
            session_hash = request.headers.get('X-Session-Hash', None)
            if not session_hash:
                await set_body(request, await request.body())
                request_body = await get_body(request)
                request_json = json.loads(request_body)
                session_hash = request_json['session_hash']
            with _StateSerializer(state_holders, session_hash):
                return await call_next(request)
        else:
            return await call_next(request)

    return persistent_state


def make_state_holder(app):
    from starlette.middleware.base import BaseHTTPMiddleware
    # if we can get an available redis client, then use _RedisBasedSessionStateHolder to
    # manage session state, otherwise keep it as default
    redis_address = _get_redis_address()
    if not redis_address:
        return
    _redis_client = _get_redis_client(redis_address)
    if _redis_client:
        state_holder = _RedisBasedSessionStateHolder('STATE', _redis_client)
        iterators = _RedisBasedSessionStateHolder('ITERATORS', _redis_client, dict)
        app.state_holder = state_holder
        app.iterators = iterators
        app.middleware_stack = None  # reset current middleware to allow modifying user provided list
        app.add_middleware(BaseHTTPMiddleware,
                           dispatch=_make_persistent_state_middleware([state_holder, iterators]))
        app.build_middleware_stack()  # rebuild middleware stack on-the-fly
