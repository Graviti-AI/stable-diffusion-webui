import datetime
import logging
import threading
import time

from modules import errors, shared, devices, script_callbacks
from typing import Optional
import gradio as gr

log = logging.getLogger(__name__)


class State:
    skipped = False
    interrupted = False
    job = ""
    _job_no = 0
    _job_count = 0
    processing_has_refined_job_count = False
    job_timestamp = '0'
    _sampling_step = 0
    _sampling_steps = 0
    _current_latent = None
    current_image = None
    current_image_sampling_step = 0
    id_live_preview = 0
    textinfo = None
    time_start = None
    server_start = None
    server_port = 0
    _server_command_signal = threading.Event()
    _server_command: Optional[str] = None
    request = None

    def __init__(self):
        self.server_start = time.time()

    @property
    def current_latent(self):
        return self._current_latent

    @current_latent.setter
    def current_latent(self, value):
        self._current_latent = value
        script_callbacks.state_updated_callback(self)

    @property
    def need_restart(self) -> bool:
        # Compatibility getter for need_restart.
        return self.server_command == "restart"

    @need_restart.setter
    def need_restart(self, value: bool) -> None:
        # Compatibility setter for need_restart.
        if value:
            self.server_command = "restart"

    @property
    def server_command(self):
        return self._server_command

    @server_command.setter
    def server_command(self, value: Optional[str]) -> None:
        """
        Set the server command to `value` and signal that it's been set.
        """
        self._server_command = value
        self._server_command_signal.set()

    @property
    def job_count(self):
        return self._job_count

    @job_count.setter
    def job_count(self, value):
        self._job_count = value
        script_callbacks.state_updated_callback(self)

    @property
    def job_no(self):
        return self._job_no

    @job_no.setter
    def job_no(self, value):
        self._job_no = value
        script_callbacks.state_updated_callback(self)

    @property
    def sampling_steps(self):
        return self._sampling_steps

    @sampling_steps.setter
    def sampling_steps(self, value):
        self._sampling_steps = value
        script_callbacks.state_updated_callback(self)

    @property
    def sampling_step(self):
        return self._sampling_step

    @sampling_step.setter
    def sampling_step(self, value):
        self._sampling_step = value
        script_callbacks.state_updated_callback(self)

    def wait_for_server_command(self, timeout: Optional[float] = None) -> Optional[str]:
        """
        Wait for server command to get set; return and clear the value and signal.
        """
        if self._server_command_signal.wait(timeout):
            self._server_command_signal.clear()
            req = self._server_command
            self._server_command = None
            return req
        return None

    def request_restart(self) -> None:
        import modules.call_utils
        modules.call_utils.check_insecure_calls()
        self.interrupt()
        self.server_command = "restart"
        log.info("Received restart request")

    def skip(self):
        self.skipped = True
        log.info("Received skip request")
        script_callbacks.state_updated_callback(self)

    def interrupt(self):
        self.interrupted = True
        log.info("Received interrupt request")
        script_callbacks.state_updated_callback(self)

    def nextjob(self):
        if shared.opts.live_previews_enable and shared.opts.show_progress_every_n_steps == -1:
            self.do_set_current_image()

        self.job_no += 1
        self.sampling_step = 0
        self.current_image_sampling_step = 0
        script_callbacks.state_updated_callback(self)

    def dict(self):
        obj = {
            "skipped": self.skipped,
            "interrupted": self.interrupted,
            "job": self.job,
            "job_count": self.job_count,
            "job_timestamp": self.job_timestamp,
            "job_no": self.job_no,
            "sampling_step": self.sampling_step,
            "sampling_steps": self.sampling_steps,
        }

        return obj

    def begin(self, job: str = "(unknown)", request: gr.Request = None):
        self.sampling_step = 0
        self.job_count = -1
        self.processing_has_refined_job_count = False
        self.job_no = 0
        self.job_timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self.current_latent = None
        self.current_image = None
        self.current_image_sampling_step = 0
        self.id_live_preview = 0
        self.skipped = False
        self.interrupted = False
        self.textinfo = None
        self.time_start = time.time()
        self.job = job
        self.request = request
        devices.torch_gc()
        log.info("Starting job %s", job)

    def end(self):
        if self.time_start is None:
            raise RuntimeError("State.end() called without State.begin()")
        duration = time.time() - self.time_start
        log.info("Ending job %s (%.2f seconds)", self.job, duration)
        self.job = ""
        self.job_count = 0
        self.request = None

        devices.torch_gc()

    def set_current_image(self):
        """if enough sampling steps have been made after the last call to this, sets self.current_image from self.current_latent, and modifies self.id_live_preview accordingly"""
        if not shared.parallel_processing_allowed:
            return

        if self.sampling_step - self.current_image_sampling_step >= shared.opts.show_progress_every_n_steps and shared.opts.live_previews_enable and shared.opts.show_progress_every_n_steps != -1:
            self.do_set_current_image()

    def do_set_current_image(self):
        if self.current_latent is None:
            return

        import modules.sd_samplers

        try:
            if shared.opts.show_progress_grid:
                self.assign_current_image(modules.sd_samplers.samples_to_image_grid(self.current_latent))
            else:
                self.assign_current_image(modules.sd_samplers.sample_to_image(self.current_latent))

            self.current_image_sampling_step = self.sampling_step

        except Exception:
            # when switching models during genration, VAE would be on CPU, so creating an image will fail.
            # we silently ignore this error
            errors.record_exception()

    def assign_current_image(self, image):
        self.current_image = image
        self.id_live_preview += 1
