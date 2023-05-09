from threading import RLock


class _Node:
    def __init__(self, key):
        self.key = key
        self.next = None
        self.prev = None


class LruCache:
    def __init__(self):
        self._cache = {}
        self._head = _Node(0)
        self._tail = _Node(0)
        self._head.next = self._tail
        self._tail.prev = self._head
        self._lock = RLock()

    def pop(self):
        """
        remove a key from cache and return the removed key
        Returns:

        """
        with self._lock:
            if len(self._cache) > 0:
                node = self._head.next
                self._link_remove(node)
                del self._cache[node.key]
                return node.key
            return None

    def touch(self, key):
        """
        touche a key.
        if this key is not in cache, it will be added to link tail.
        Args:
            key:

        Returns:

        """
        with self._lock:
            if key not in self._cache:
                node = _Node(key)
                self._cache[node.key] = node
                self._link_add(node)
                return
            current = self._head.next
            while current != self._tail:
                if current.key == key:
                    node = current
                    self._link_remove(node)
                    self._link_add(node)
                    break
                else:
                    current = current.next

    @staticmethod
    def _link_remove(node):
        """
        remove a node from link head
        Args:
            node:

        Returns:

        """
        p = node.prev
        n = node.next
        p.next = n
        n.prev = p

    def _link_add(self, node):
        """
        add a node to link tail
        Args:
            node:

        Returns:

        """
        p = self._tail.prev
        p.next = node
        self._tail.prev = node
        node.prev = p
        node.next = self._tail

    def __iter__(self):
        current = self._tail.prev
        while current != self._head:
            yield current.key
            current = current.prev
