#!/usr/bin/env python3

from typing import TYPE_CHECKING

import numpy as np
import opennsfw2 as n2
from keras import Model
from PIL import Image, ImageFilter

_NSFW_ALLOWED_TIERS = {"basic", "plus", "pro", "api"}

if TYPE_CHECKING:
    from modules.processing import StableDiffusionProcessing

_OPEN_NSFW_MODEL: Model | None = None


def _get_open_nsfw_model() -> Model:
    global _OPEN_NSFW_MODEL

    if _OPEN_NSFW_MODEL is None:
        _OPEN_NSFW_MODEL = n2.make_open_nsfw_model()

    return _OPEN_NSFW_MODEL


def _get_nsfw_probability(image: Image.Image) -> float:
    preprocess_image = n2.preprocess_image(image, n2.Preprocessing.YAHOO)
    inputs = np.expand_dims(preprocess_image, axis=0)

    model = _get_open_nsfw_model()
    predictions = model.predict(inputs)
    _, nsfw_probability = predictions[0]

    return nsfw_probability


def nsfw_blur(
    image: Image.Image, p: "StableDiffusionProcessing", threshold: float = 0.75
) -> Image.Image:
    request = p.get_request()
    assert request is not None

    if request.headers["user-tire"].lower() in _NSFW_ALLOWED_TIERS:
        return image

    probability = _get_nsfw_probability(image)
    if probability > threshold:
        image = image.filter(ImageFilter.BoxBlur(10))
        setattr(image, "is_nsfw", True)

    return image
