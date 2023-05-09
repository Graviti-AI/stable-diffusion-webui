import os
import pathlib
import shutil
import uuid
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

from modules.lru_cache import LruCache


def get_cache_filepath(filepath: str, base_dir: str, cache_dir: str) -> str:
    filepath = os.path.abspath(filepath)
    base_dir = os.path.abspath(base_dir)
    cache_dir = os.path.abspath(cache_dir)
    return os.path.join(cache_dir, os.path.relpath(filepath, base_dir))


def copy_file_to_cache_dir_atomically(filepath: str, base_dir: str, cache_dir: str):
    destpath = get_cache_filepath(filepath, base_dir, cache_dir)
    dirname = os.path.dirname(destpath)
    tmppath = os.path.join(dirname, str(uuid.uuid4()))
    if not os.path.exists(dirname):
        os.makedirs(dirname, exist_ok=True)
    # This is not atomic, so we first copy to a unique path
    shutil.copy2(filepath, tmppath)
    # This is atomic
    os.rename(tmppath, destpath)
    print(f"Cache model {destpath} created.")
    return destpath


def evaluate_disk_occupation_gb(cache_dir: str) -> float:
    size = 0.0
    cache_path = pathlib.Path(cache_dir)
    if not cache_path.exists():
        return size
    for element in cache_path.iterdir():
        if element.is_dir():
            size += evaluate_disk_occupation_gb(str(element))
        else:
            size += os.stat(element).st_size / 1e9
    return size


# check if the cache_dir has enough space to store new file
def check_cache_space(cache_dir, new_file_size_gb, cache_size_gb):
    total_space_occupied_gb = evaluate_disk_occupation_gb(cache_dir)
    return new_file_size_gb + total_space_occupied_gb < cache_size_gb


def copy_file_to_cache_dir_if_space_available(lru_cache: LruCache,
                                              filepath: str,
                                              base_dir: str,
                                              cache_dir: str,
                                              cache_size_gb: float):
    cache_dir = os.path.abspath(cache_dir)
    filepath = os.path.abspath(filepath)
    current_file_size_gb = os.stat(filepath).st_size / 1e9  # Convert bytes to GB
    while not check_cache_space(cache_dir, current_file_size_gb, cache_size_gb):
        # disk is full, release a file
        cached_filepath = lru_cache.pop()
        if cached_filepath:
            os.unlink(cached_filepath)
        else:
            break

    # in case of cache is empty, but still not get enough disk space
    if check_cache_space(cache_dir, current_file_size_gb, cache_size_gb):
        cached_filepath = copy_file_to_cache_dir_atomically(filepath, base_dir, cache_dir)
        lru_cache.touch(cached_filepath)


# scan cache dir, load all cache model file info to lru_cache at service startup.
# the model files are cached in arbitrary order.
def setup_remote_file_cache(lru_cache: LruCache, cache_dir: str):
    if not cache_dir:
        return
    cache_path = pathlib.Path(cache_dir)
    if not cache_path.exists():
        return
    for item in cache_path.iterdir():
        if item.is_dir():
            setup_remote_file_cache(lru_cache, str(item))
        else:
            lru_cache.touch(str(item.absolute()))


# A function wrapper (Decorator) to help cache big files to a local ssd
def use_sdd_to_cache_remote_file(
        func: callable,
        lru_cache: LruCache,
        base_dir: str,
        cache_dir: str,
        executor_ppol: ThreadPoolExecutor,
        filepath_arg_index: int = 0,
        cache_size_gb: float = 100.0):
    @wraps(func)
    def weight_loading_wrapper(*args, **kwargs):
        if base_dir and cache_dir and executor_ppol and cache_size_gb > 0:
            filepath = args[filepath_arg_index]
            cached_filepath = get_cache_filepath(filepath, base_dir, cache_dir)
            if os.path.exists(cached_filepath):
                args = list(args)
                args[filepath_arg_index] = cached_filepath
                lru_cache.touch(cached_filepath)
                print(f"Loading cached model {cached_filepath}.")
            else:
                print(f"Loading original model {filepath}.")
                executor_ppol.submit(
                    copy_file_to_cache_dir_if_space_available, lru_cache, filepath, base_dir, cache_dir, cache_size_gb)
        return func(*args, **kwargs)
    return weight_loading_wrapper
