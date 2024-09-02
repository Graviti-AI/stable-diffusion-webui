#!/usr/bin/env python3

import base64
import io
from typing import TYPE_CHECKING

import gradio as gr
import numpy as np
import opennsfw2 as n2
from fastapi import FastAPI, Request
from keras import Model
from PIL import Image, ImageFilter
from pydantic import BaseModel

_NSFW_ALLOWED_TIERS = {"basic", "plus", "pro", "api", "ltd s", "appsumo ltd tier 2"}

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


def check_nsfw(image: Image.Image, threshold: float = 0.75) -> bool:
    probability = _get_nsfw_probability(image)
    return probability > threshold


def nsfw_blur(
    image: Image.Image, p: "StableDiffusionProcessing", threshold: float = 0.75
) -> Image.Image:
    request = p.get_request()
    assert request is not None

    if request.headers["user-tire"].lower() in _NSFW_ALLOWED_TIERS:
        return image

    if check_nsfw(image, threshold):
        image = image.filter(ImageFilter.BoxBlur(10))
        setattr(image, "is_nsfw", True)

    return image


class NSFWCheckerRequest(BaseModel):
    image: str


class NSFWCheckerResponse(BaseModel):
    confidence: float


def get_nsfw_probability(_: Request, body: NSFWCheckerRequest) -> NSFWCheckerResponse:
    base64_image = body.image

    if "base64," in base64_image:
        base64_image = base64_image.split("base64,", 1)[1]

    image = Image.open(io.BytesIO(base64.b64decode(base64_image)))
    confidence = _get_nsfw_probability(image)

    return NSFWCheckerResponse(confidence=confidence)


# call "script_callbacks.on_app_started" for this function in style_info.py
# because this module is inited too early before "script_callbacks.clear_callbacks"
def setup_nsfw_checker_api(_: gr.Blocks, app: FastAPI) -> None:
    app.add_api_route(
        "/internal/nsfw_checker",
        get_nsfw_probability,
        methods=["POST"],
        response_model=NSFWCheckerResponse,
    )
