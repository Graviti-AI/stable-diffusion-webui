import logging

from modules import scripts
from modules.gallery_input_images import IMG2IMG_CANVASES, set_img2img_refs
from modules_forge.forge_canvas.canvas import gallery_input_canvases

logger = logging.getLogger(__name__)


class ScriptGalleryInputImages(scripts.ScriptBuiltinUI):
    """Pass the gallery references of the img2img canvases to img2img(), which reads the init image: an
    error of a script would not fail the generation."""

    create_group = False
    sorting_priority = 1000

    def title(self):
        return "Gallery input images"

    def show(self, is_img2img):
        return scripts.AlwaysVisible if is_img2img else False

    def ui(self, is_img2img):
        # By position in IMG2IMG_CANVASES: none without all of them.
        refs = [getattr(gallery_input_canvases.get(elem_id), "gallery_ref", None) for elem_id in IMG2IMG_CANVASES]
        if None in refs:
            logger.warning("The gallery input canvases %s are not all created before their script", IMG2IMG_CANVASES)
            return []

        return refs

    def setup(self, p, *refs):
        set_img2img_refs(p, refs)
