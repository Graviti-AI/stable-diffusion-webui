import os
import uuid
import shutil

from concurrent.futures import ThreadPoolExecutor
from functools import wraps


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


def evaluate_disk_occupation_gb(cache_dir: str) -> float:
    size = 0
    if not os.path.exists(cache_dir):
        return 0
    for element in os.scandir(cache_dir):
        size += os.stat(element).st_size
    return size / 1e9  # Convert bytes to GB


def copy_file_to_cache_dir_if_space_available(filepath: str, base_dir: str, cache_dir: str, cache_size_gb: float):
    cache_dir = os.path.abspath(cache_dir)
    total_space_occupied_gb = evaluate_disk_occupation_gb(cache_dir)
    filepath = os.path.abspath(filepath)
    current_file_size_gb = os.stat(filepath).st_size / 1e9  # Convert bytes to GB
    if current_file_size_gb + total_space_occupied_gb < cache_size_gb:
        copy_file_to_cache_dir_atomically(filepath, base_dir, cache_dir)


# A function wrapper (Decorator) to help cache big files to a local ssd
def use_sdd_to_cache_remote_file(
        func: callable,
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
                print(f"Loading cached model {cached_filepath}.")
            else:
                print(f"Loading original model {filepath}.")
                executor_ppol.submit(
                    copy_file_to_cache_dir_if_space_available, filepath, base_dir, cache_dir, cache_size_gb)
        return func(*args, **kwargs)
    return weight_loading_wrapper
