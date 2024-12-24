import gradio as gr


def _list_forge_modules() -> list[str]:
    from modules_forge import main_entry

    _, modules = main_entry.refresh_models()
    return modules


def _list_forge_unet_storage_dtype_options() -> list[str]:
    from modules_forge import main_entry

    return list(main_entry.forge_unet_storage_dtype_options.keys())


def register(options_templates, options_section, OptionInfo):
    options_templates.update(options_section((None, "Forge Hidden options"), {
        # "forge_unet_storage_dtype": OptionInfo('Automatic'),
        "forge_inference_memory": OptionInfo(1024),
        "forge_async_loading": OptionInfo('Queue'),
        "forge_pin_shared_memory": OptionInfo('CPU'),
        "forge_preset": OptionInfo('sd'),
        # "forge_additional_modules": OptionInfo([]),

        "forge_additional_modules": OptionInfo([], "VAE / Text Encoder", gr.Dropdown, lambda: {"choices": _list_forge_modules(), "multiselect": True}, refresh=_list_forge_modules, infotext='VAE / Text Encoder').info("choose VAE / Text Encoder"),
        "forge_unet_storage_dtype": OptionInfo("Automatic", "Diffusion in Low Bits", gr.Dropdown, lambda: {"choices": _list_forge_unet_storage_dtype_options()}).info("choose UNet Storage Dtype"),
    }))
