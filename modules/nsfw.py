#!/usr/bin/env python3

from typing import TYPE_CHECKING, Any

import requests
from PIL import Image, ImageFilter

from modules.system_monitor import get_feature_permissions

if TYPE_CHECKING:
    from modules.processing import StableDiffusionProcessing


def _check_nsfw(
    endpoint: str, image: Image.Image, prompt: str | None
) -> dict[str, Any]:
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

    allowed_tiers = get_feature_permissions()["features"]["NSFWContent"][
        "allowed_tiers"
    ]
    if request.headers["user-tire"] in allowed_tiers:
        return image, None

    endpoint = request.headers["x-diffus-api-gateway-endpoint"]

    result = _check_nsfw(endpoint, image, prompt)

    if result["flag"]:
        image = image.filter(ImageFilter.BoxBlur(10))
        setattr(image, "is_nsfw", True)

    return image, result


class BlackImageException(Exception):
    def __init__(self):
        pass

    def __str__(self) -> str:
        return (
            "The generation resulted in a completely black image, indicates a failed task. "
            "Credits have been refunded. Please adjust your parameters and try again. "
            "If the issue persists, feel free to contact us on Discord."
        )


def detect_black_image(image: Image.Image, threshold=2) -> bool:
    extrema = image.getextrema()

    if len(extrema) in {3, 4}:
        return all(ext[1] <= threshold for ext in extrema[:3])

    if len(extrema) == 1:
        return extrema[1] <= threshold

    return False
