import modules.script_callbacks
from modules.script_callbacks import ImageSaveParams


def on_image_saved(params: ImageSaveParams):
    """
    save generated images to user output dir
    """
    from modules.paths import Paths
    paths = Paths(request=params.p.get_request())
    paths.save_image(params.filename)
    pass


modules.script_callbacks.on_image_saved(on_image_saved)
