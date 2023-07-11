import pathlib
import time
import logging
from modules.shared import cmd_opts

_handler = logging.FileHandler(pathlib.Path(cmd_opts.logging_file_dir).joinpath('metrics.log'), mode='a')
_handler.setLevel(logging.DEBUG)
_handler.setFormatter(logging.Formatter("%(asctime)s,%(message)s"))

_logger = logging.getLogger('metrics')
_logger.addHandler(_handler)


class TimerSubcategory:
    def __init__(self, timer, category):
        self.timer = timer
        self.category = category
        self.start = None
        self.original_base_category = timer.base_category

    def __enter__(self):
        self.start = time.time()
        self.timer.base_category = self.original_base_category + self.category + "/"

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed_for_subcategroy = time.time() - self.start
        self.timer.base_category = self.original_base_category
        self.timer.add_time_to_record(self.original_base_category + self.category, elapsed_for_subcategroy)
        self.timer.record(self.category)


class Timer:
    def __init__(self, name, *args):
        self._name = name
        self._args = args
        self.start = time.time()
        self.records = {}
        self.total = 0
        self.base_category = ''

    def elapsed(self):
        end = time.time()
        res = end - self.start
        self.start = end
        return res

    def add_time_to_record(self, category, amount):
        if category not in self.records:
            self.records[category] = 0

        self.records[category] += amount

    def record(self, category, extra_time=0):
        e = self.elapsed()

        self.add_time_to_record(self.base_category + category, e + extra_time)

        self.total += e + extra_time

    def subcategory(self, name):
        self.elapsed()

        subcat = TimerSubcategory(self, name)
        return subcat

    def _save_to_logger(self):
        # sort key
        keys = list(self.records.keys())
        keys.sort()

        # make log record
        values = [self._name, *self._args, f'{self.total:.2f}']
        values.extend([f'{self.records[x]:.2f}' for x in keys])

        # save records to log file
        _logger.info(','.join(values))

    def summary(self):
        self._save_to_logger()
        res = f"{self.total:.1f}s"

        additions = [(category, time_taken) for category, time_taken in self.records.items() if time_taken >= 0.1 and '/' not in category]
        if not additions:
            return res

        res += " ("
        res += ", ".join([f"{category}: {time_taken:.1f}s" for category, time_taken in additions])
        res += ")"

        return res

    def dump(self):
        return {'total': self.total, 'records': self.records}

    def reset(self):
        self.__init__(self._name, *self._args)


startup_timer = Timer('main')

startup_record = None
