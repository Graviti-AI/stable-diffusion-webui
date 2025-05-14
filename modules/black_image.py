#!/usr/bin/env python3

import logging
from typing import TYPE_CHECKING

from PIL import Image

if TYPE_CHECKING:
    from modules.shared_state import State

logger = logging.getLogger(__name__)

CHECK_BLACK_EVERY_N = 2
RESTART_AFTER_N_BLACK_IMAGES = 3


def set_current_latent_callback(state: State) -> None:
    if state.sampling_step == 0 or state.sampling_step % CHECK_BLACK_EVERY_N != 0:
        return

    if state.current_latent is None:
        return

    if state.black_image_count is None:
        return

    import modules.progress
    import modules.sd_samplers

    image = modules.sd_samplers.samples_to_image_grid(state.current_latent)
    result = detect_black_image(image)
    if not result:
        state.black_image_count = None
        return

    state.black_image_count += 1
    logger.warning(
        f"Detected black image for {state.job}: "
        f"step({state.sampling_step}/{state.sampling_steps}), count({state.black_image_count})."
    )

    if state.black_image_count >= RESTART_AFTER_N_BLACK_IMAGES:
        logger.error(
            f"Detected {RESTART_AFTER_N_BLACK_IMAGES} black images for {state.job}, "
            "set force restart"
        )
        modules.progress.set_force_restart(True)


def detect_black_image(image: Image.Image, threshold=5) -> bool:
    extrema = image.getextrema()

    if len(extrema) in {3, 4}:
        return all(ext[1] <= threshold for ext in extrema[:3])

    if len(extrema) == 1:
        return extrema[1] <= threshold

    return False
