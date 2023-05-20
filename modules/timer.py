import pathlib
import time
import logging
from modules.shared import cmd_opts

_handler = logging.FileHandler(pathlib.Path(cmd_opts.logging_file_dir).joinpath('metrics.log'), mode='a')
_handler.setLevel(logging.DEBUG)
_handler.setFormatter(logging.Formatter("%(asctime)s,%(message)s"))

_logger = logging.getLogger('metrics')
_logger.addHandler(_handler)


class Timer:
    def __init__(self, name, *args):
        self._name = name
        self._args = args
        self.start = time.time()
        self.records = {}
        self.total = 0

    def elapsed(self):
        end = time.time()
        res = end - self.start
        self.start = end
        return res

    def record(self, category, extra_time=0):
        e = self.elapsed()
        if category not in self.records:
            self.records[category] = 0

        self.records[category] += e + extra_time
        self.total += e + extra_time

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

        additions = [x for x in self.records.items() if x[1] >= 0.1]
        if not additions:
            return res

        res += " ("
        res += ", ".join([f"{category}: {time_taken:.1f}s" for category, time_taken in additions])
        res += ")"

        return res

    def reset(self):
        self.__init__()
