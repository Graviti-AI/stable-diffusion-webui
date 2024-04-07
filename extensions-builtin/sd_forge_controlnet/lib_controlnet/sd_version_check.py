from lib_controlnet.enums import StableDiffusionVersion
from lib_controlnet.external_code import ControlNetUnit
from lib_controlnet.global_state import get_sd_version
from lib_controlnet.logging import logger


class SDVersionIncompatibleError(Exception):
    pass


def check_sd_version_compatible(unit: ControlNetUnit) -> None:
    sd_version = get_sd_version()
    assert sd_version != StableDiffusionVersion.UNKNOWN

    if "revision" in unit.module.lower() and sd_version != StableDiffusionVersion.SDXL:
        raise SDVersionIncompatibleError(
            f"Preprocessor 'revision' only supports SDXL. Current SD base model is {sd_version}."
        )

    # No need to check if the ControlModelType does not require model to be present.
    if unit.model is None or unit.model.lower() == "none":
        return

    cnet_sd_version = StableDiffusionVersion.detect_from_model_name(unit.model)

    if cnet_sd_version == StableDiffusionVersion.UNKNOWN:
        logger.warn(f"Unable to determine version for ControlNet model '{unit.model}'.")
        return

    if not sd_version.is_compatible_with(cnet_sd_version):
        raise SDVersionIncompatibleError(
            f"ControlNet model {unit.model}({cnet_sd_version}) is "
            "not compatible with sd model({sd_version})"
        )
