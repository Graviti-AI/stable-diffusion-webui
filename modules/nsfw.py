#!/usr/bin/env python3


from PIL import Image


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
