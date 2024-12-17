from enum import Enum

from lib_controlnet.external_code import ControlNetUnit
from lib_controlnet.logging import logger

import modules.shared as shared
from modules.processing import StableDiffusionProcessing
from modules.system_monitor import (
    MonitorTierMismatchedException,
    get_feature_permissions,
)
from modules.user import User


class SDVersionIncompatibleError(Exception):
    pass


class StableDiffusionVersion(Enum):
    """The version family of stable diffusion model."""

    UNKNOWN = 0
    SD1x = 1
    SD2x = 2
    SDXL = 3

    @staticmethod
    def detect_from_model_name(model_name: str) -> "StableDiffusionVersion":
        """Based on the model name provided, guess what stable diffusion version it is.
        This might not be accurate without actually inspect the file content.
        """
        if any(f"sd{v}" in model_name.lower() for v in ("14", "15", "16")):
            return StableDiffusionVersion.SD1x

        if "sd21" in model_name or "2.1" in model_name:
            return StableDiffusionVersion.SD2x

        if "xl" in model_name.lower():
            return StableDiffusionVersion.SDXL

        return StableDiffusionVersion.UNKNOWN

    def encoder_block_num(self) -> int:
        if self in (
            StableDiffusionVersion.SD1x,
            StableDiffusionVersion.SD2x,
            StableDiffusionVersion.UNKNOWN,
        ):
            return 12
        else:
            return 9  # SDXL

    def controlnet_layer_num(self) -> int:
        return self.encoder_block_num() + 1

    def is_compatible_with(self, other: "StableDiffusionVersion") -> bool:
        """Incompatible only when one of version is SDXL and other is not."""
        return (
            any(v == StableDiffusionVersion.UNKNOWN for v in [self, other])
            or sum(v == StableDiffusionVersion.SDXL for v in [self, other]) != 1
        )


def _get_sd_version() -> StableDiffusionVersion:
    if not shared.sd_model:
        return StableDiffusionVersion.UNKNOWN
    if shared.sd_model.is_sdxl:
        return StableDiffusionVersion.SDXL
    elif shared.sd_model.is_sd2:
        return StableDiffusionVersion.SD2x
    elif shared.sd_model.is_sd1:
        return StableDiffusionVersion.SD1x
    else:
        return StableDiffusionVersion.UNKNOWN


def check_sd_version_compatible(unit: ControlNetUnit) -> None:
    sd_version = _get_sd_version()
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
            f"not compatible with sd model({sd_version})"
        )


def check_tier_permission(
    p: StableDiffusionProcessing, enabled_units: list[ControlNetUnit]
) -> None:
    request = p.get_request()
    tier = User.current_user(request).tire
    allowed_tiers = get_feature_permissions()["generate"]["ControlNetXL"][
        "allowed_tiers"
    ]

    if tier in allowed_tiers:
        return

    for unit in enabled_units:
        if "revision" in unit.module.lower():
            raise MonitorTierMismatchedException(
                (
                    "Preprocessor 'revision' only supports SDXL. SDXL ControlNet is available for "
                    f"{allowed_tiers} only. The current user tier is {tier}."
                ),
                tier,
                allowed_tiers,
            )

        cnet_sd_version = StableDiffusionVersion.detect_from_model_name(unit.model)
        if cnet_sd_version == StableDiffusionVersion.SDXL:
            raise MonitorTierMismatchedException(
                (
                    "SDXL ControlNet is available for "
                    f"{allowed_tiers} only. The current user tier is {tier}."
                ),
                tier,
                allowed_tiers,
            )
