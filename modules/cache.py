import json
import threading
import time
import os
import pathlib
import shutil
from concurrent.futures import ThreadPoolExecutor
from functools import wraps

import diskcache
import tqdm

from modules.paths import data_path, script_path
from modules.lru_cache import LruCache

cache_filename = os.environ.get('SD_WEBUI_CACHE_FILE', os.path.join(data_path, "cache.json"))
cache_dir = os.environ.get('SD_WEBUI_CACHE_DIR', os.path.join(data_path, "cache"))
caches = {}
cache_lock = threading.Lock()


def dump_cache():
    """old function for dumping cache to disk; does nothing since diskcache."""

    pass


def make_cache(subsection: str) -> diskcache.Cache:
    return diskcache.Cache(
        os.path.join(cache_dir, subsection),
        size_limit=2**32,  # 4 GB, culling oldest first
        disk_min_file_size=2**18,  # keep up to 256KB in Sqlite
    )


def convert_old_cached_data():
    try:
        with open(cache_filename, "r", encoding="utf8") as file:
            data = json.load(file)
    except FileNotFoundError:
        return
    except Exception:
        os.replace(cache_filename, os.path.join(script_path, "tmp", "cache.json"))
        print('[ERROR] issue occurred while trying to read cache.json; old cache has been moved to tmp/cache.json')
        return

    total_count = sum(len(keyvalues) for keyvalues in data.values())

    with tqdm.tqdm(total=total_count, desc="converting cache") as progress:
        for subsection, keyvalues in data.items():
            cache_obj = caches.get(subsection)
            if cache_obj is None:
                cache_obj = make_cache(subsection)
                caches[subsection] = cache_obj

            for key, value in keyvalues.items():
                cache_obj[key] = value
                progress.update(1)


def cache(subsection):
    """
    Retrieves or initializes a cache for a specific subsection.

    Parameters:
        subsection (str): The subsection identifier for the cache.

    Returns:
        diskcache.Cache: The cache data for the specified subsection.
    """

    cache_obj = caches.get(subsection)
    if not cache_obj:
        with cache_lock:
            if not os.path.exists(cache_dir) and os.path.isfile(cache_filename):
                convert_old_cached_data()

            cache_obj = caches.get(subsection)
            if not cache_obj:
                cache_obj = make_cache(subsection)
                caches[subsection] = cache_obj

    return cache_obj


def cached_data_for_file(subsection, title, filename, func):
    """
    Retrieves or generates data for a specific file, using a caching mechanism.

    Parameters:
        subsection (str): The subsection of the cache to use.
        title (str): The title of the data entry in the subsection of the cache.
        filename (str): The path to the file to be checked for modifications.
        func (callable): A function that generates the data if it is not available in the cache.

    Returns:
        dict or None: The cached or generated data, or None if data generation fails.

    The `cached_data_for_file` function implements a caching mechanism for data stored in files.
    It checks if the data associated with the given `title` is present in the cache and compares the
    modification time of the file with the cached modification time. If the file has been modified,
    the cache is considered invalid and the data is regenerated using the provided `func`.
    Otherwise, the cached data is returned.

    If the data generation fails, None is returned to indicate the failure. Otherwise, the generated
    or cached data is returned as a dictionary.
    """

    existing_cache = cache(subsection)
    ondisk_mtime = os.path.getmtime(filename)

    entry = existing_cache.get(title)
    if entry:
        cached_mtime = entry.get("mtime", 0)
        if ondisk_mtime > cached_mtime:
            entry = None

    if not entry or 'value' not in entry:
        value = func()
        if value is None:
            return None

        entry = {'mtime': ondisk_mtime, 'value': value}
        existing_cache[title] = entry

        dump_cache()

    return entry['value']


def get_cache_filepath(filepath: str, base_dir: str, cache_dir: str) -> tuple:
    filepath = os.path.abspath(filepath)
    base_dir = os.path.abspath(base_dir)
    cache_dir = os.path.abspath(cache_dir)
    relpath = os.path.relpath(filepath, base_dir)

    cached_filepath = os.path.join(cache_dir, relpath)
    return relpath, cached_filepath, f'{cached_filepath}.lock'


def _copy_file_synchronously(src_filepath, dst_filepath):
    # a locker to make copying synchronously
    filepath_locker = pathlib.Path(f'{dst_filepath}.lock')
    if filepath_locker.exists():
        if time.time() - filepath_locker.stat().st_ctime > 6 * 60 * 60:
            # dst file locker exists for more than 6 hours, there should be something wrong of copying file
            # delete it and re-copy
            filepath_locker.unlink()
        else:
            # file locker exists means some one is copying the same file.
            return

    # make sure parent exists before do copy
    dst_parent_dir = os.path.dirname(dst_filepath)
    if not os.path.exists(dst_parent_dir):
        os.makedirs(dst_parent_dir, exist_ok=True)

    # sleep 1s, then check if locker exists again.
    # in case of other one is copying the same file.
    time.sleep(1)
    if filepath_locker.exists():
        return

    # create locker
    filepath_locker.touch()

    # do copy
    shutil.copy2(src_filepath, dst_filepath)
    print(f"Make cache file {src_filepath} -> {dst_filepath}")

    # remove locker
    filepath_locker.unlink()


def _copy_file_to_cache_dir(
        filepath: str,
        base_dir: str,
        cache_dir: str,
        source_file_container: list,
):
    relpath, dstpath, _ = get_cache_filepath(filepath, base_dir, cache_dir)

    copied = False
    missed_file = []
    for src_container in source_file_container:
        if not src_container:
            continue
        src_filepath = os.path.join(src_container, relpath)
        if not os.path.exists(src_filepath):
            missed_file.append((filepath, src_filepath))
            continue
        missed_file.append((src_filepath, dstpath))
        copied = True
        break
    if not copied:
        missed_file.append((filepath, dstpath))

    for (src, dst) in missed_file:
        _copy_file_synchronously(src, dst)
    return dstpath


# check if the cache_dir has enough space to store new file
def check_cache_space(lru_cache: LruCache, new_file_size_gb, cache_size_gb):
    total_space_occupied_gb = 0
    for file_path, file_info in lru_cache:
        total_space_occupied_gb += file_info['file_size']
    return new_file_size_gb + total_space_occupied_gb < cache_size_gb


def copy_file_to_cache_dir_if_space_available(lru_cache: LruCache,
                                              filepath: str,
                                              base_dir: str,
                                              cache_dir: str,
                                              source_file_containers: list,
                                              cache_size_gb: float):
    """
    copy file from source_file_container for cache.
    we do not copy src file from filepath directly, but copy it from source_file_container.
    """
    cache_dir = os.path.abspath(cache_dir)
    filepath = os.path.abspath(filepath)
    current_file_size_gb = os.stat(filepath).st_size / 1e9  # Convert bytes to GB
    while not check_cache_space(lru_cache, current_file_size_gb, cache_size_gb):
        # disk is full, release a file
        cached_filepath, _ = lru_cache.pop()
        if cached_filepath:
            os.unlink(cached_filepath)
        else:
            break

    # in case of cache is empty, but still not get enough disk space
    if check_cache_space(lru_cache, current_file_size_gb, cache_size_gb):
        cached_filepath = _copy_file_to_cache_dir(filepath, base_dir, cache_dir, source_file_containers)
        _cache_file_info(lru_cache, cached_filepath, current_file_size_gb)


def _cache_file_info(lru_cache: LruCache, cached_filepath, cached_file_size_gb):
    lru_cache.touch(cached_filepath, {'file_size': cached_file_size_gb})


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
            file_size = os.stat(item).st_size / 1e9
            _cache_file_info(lru_cache, str(item.absolute()), file_size)


# A function wrapper (Decorator) to help cache big files to a local ssd
def use_sdd_to_cache_remote_file(
        func: callable,
        lru_cache: LruCache,
        base_dir: str,
        cache_dir: str,
        source_file_container: list,
        executor_ppol: ThreadPoolExecutor,
        filepath_arg_index: int = 0,
        cache_size_gb: float = 100.0):
    @wraps(func)
    def weight_loading_wrapper(*args, **kwargs):
        if base_dir and cache_dir and executor_ppol and cache_size_gb > 0:
            filepath = args[filepath_arg_index]
            _, cached_filepath, cached_filepath_locker = get_cache_filepath(filepath, base_dir, cache_dir)
            # cached_filepath_locker exists means cached_file is not available for now
            if os.path.exists(cached_filepath) and not os.path.exists(cached_filepath_locker):
                args = list(args)
                args[filepath_arg_index] = cached_filepath
                lru_cache.touch(cached_filepath)
                print(f"Loading cached model {cached_filepath}.")
            else:
                print(f"Loading original model {filepath}.")
                executor_ppol.submit(
                    copy_file_to_cache_dir_if_space_available,
                    lru_cache, filepath, base_dir, cache_dir, source_file_container, cache_size_gb
                )
        return func(*args, **kwargs)

    return weight_loading_wrapper
