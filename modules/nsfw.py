#!/usr/bin/env python3

from typing import TYPE_CHECKING, Any

import requests
from PIL import Image, ImageFilter

_NSFW_ALLOWED_TIERS = {"basic", "plus", "pro", "api", "ltd s", "appsumo ltd tier 2"}

if TYPE_CHECKING:
    from modules.processing import StableDiffusionProcessing


def _check_nsfw(endpoint: str, image: Image.Image, prompt: str | None) -> dict[str, Any]:
    from modules.api.api import encode_pil_to_base64

    url = f"{endpoint}/api/v3/internal/moderation/content"

    encoded_image = encode_pil_to_base64(image)

    body = {
        "text": prompt,
        "image": {
            "encoded_image": (
                encoded_image
                if isinstance(encoded_image, str)
                else encoded_image.decode()
            )
        },
    }

    response = requests.post(url, json=body)
    response.raise_for_status()

    result = response.json()

    return result


def nsfw_blur(
    image: Image.Image, prompt: str | None, p: "StableDiffusionProcessing"
) -> tuple[Image.Image, dict[str, Any] | None]:
    request = p.get_request()
    assert request is not None

    if request.headers["user-tire"].lower() in _NSFW_ALLOWED_TIERS:
        return image, None

    endpoint = request.headers["x-diffus-api-gateway-endpoint"]

    result = _check_nsfw(endpoint, image, prompt)

    if result["flag"]:
        image = image.filter(ImageFilter.BoxBlur(10))
        setattr(image, "is_nsfw", True)

    return image, result
