import importlib
import logging
import sys
import warnings
from threading import Thread
from concurrent.futures import ThreadPoolExecutor

from modules.launch_utils import startup_timer


def imports():
    logging.getLogger("torch.distributed.nn").setLevel(logging.ERROR)  # sshh...
    logging.getLogger("xformers").addFilter(lambda record: 'A matching Triton is not available' not in record.getMessage())

    import torch  # noqa: F401
    startup_timer.record("import torch")
    import pytorch_lightning  # noqa: F401
    startup_timer.record("import torch")
    warnings.filterwarnings(action="ignore", category=DeprecationWarning, module="pytorch_lightning")
    warnings.filterwarnings(action="ignore", category=UserWarning, module="torchvision")

    import gradio  # noqa: F401
    startup_timer.record("import gradio")

    from modules import paths, timer, import_hook, errors  # noqa: F401
    startup_timer.record("setup paths")

    import ldm.modules.encoders.modules  # noqa: F401
    startup_timer.record("import ldm")

    import sgm.modules.encoders.modules  # noqa: F401
    startup_timer.record("import sgm")

    from modules import shared_init
    shared_init.initialize()
    startup_timer.record("initialize shared")

    from modules import processing, gradio_extensons, ui  # noqa: F401
    startup_timer.record("other imports")


def check_versions():
    from modules.shared_cmd_options import cmd_opts

    if not cmd_opts.skip_version_check:
        from modules import errors
        errors.check_versions()


def initialize():
    import tempfile
    from modules import shared
    if shared.opts is None:
        raise ValueError("shared.opts is None. Shared has not been initialized.")
    # hijack tempdir to our temp_dir, to share tmp files between clusters
    tempfile.tempdir = shared.opts.temp_dir

    import torch
    import safetensors.torch
    from modules import call_queue
    from modules.lru_cache import LruCache
    from modules.cache import use_sdd_to_cache_remote_file, setup_remote_file_cache
    from modules.shared_cmd_options import cmd_opts
    from modules.paths_internal import models_path

    call_queue.gpu_worker_pool = ThreadPoolExecutor(max_workers=1, thread_name_prefix="gpu_worker_")
    file_mover_worker_pool = ThreadPoolExecutor(thread_name_prefix="file_mover_threads_")
    lru_cache = LruCache()
    setup_remote_file_cache(lru_cache, cmd_opts.model_cache_dir)
    torch.load = use_sdd_to_cache_remote_file(
        torch.load,
        lru_cache,
        models_path,
        cmd_opts.model_cache_dir,
        cmd_opts.model_cache_src.split(','),
        file_mover_worker_pool,
        cache_size_gb=cmd_opts.model_cache_max_size)
    safetensors.torch.load_file = use_sdd_to_cache_remote_file(
        safetensors.torch.load_file,
        lru_cache,
        models_path,
        cmd_opts.model_cache_dir,
        cmd_opts.model_cache_src.split(','),
        file_mover_worker_pool,
        cache_size_gb=cmd_opts.model_cache_max_size)

    from modules import initialize_util
    initialize_util.fix_torch_version()
    initialize_util.fix_asyncio_event_loop_policy()
    initialize_util.validate_tls_options()
    initialize_util.configure_sigint_handler()
    initialize_util.configure_opts_onchange()

    from modules import modelloader
    modelloader.cleanup_models()

    from modules import sd_models
    sd_models.setup_model()
    startup_timer.record("setup SD model")

    from modules import codeformer_model
    warnings.filterwarnings(action="ignore", category=UserWarning, module="torchvision.transforms.functional_tensor")
    codeformer_model.setup_model(cmd_opts.codeformer_models_path)
    startup_timer.record("setup codeformer")

    from modules import gfpgan_model
    gfpgan_model.setup_model(cmd_opts.gfpgan_models_path)
    startup_timer.record("setup gfpgan")

    initialize_rest(reload_script_modules=False)


def initialize_rest(*, reload_script_modules=False):
    """
    Called both from initialize() and when reloading the webui.
    """
    from modules.shared_cmd_options import cmd_opts

    from modules import sd_samplers
    sd_samplers.set_samplers()
    startup_timer.record("set samplers")

    from modules import extensions
    extensions.list_extensions()
    startup_timer.record("list extensions")

    from modules import initialize_util
    initialize_util.restore_config_state_file()
    startup_timer.record("restore config state file")

    from modules import shared, upscaler, scripts
    if cmd_opts.ui_debug_mode:
        shared.sd_upscalers = upscaler.UpscalerLanczos().scalers
        scripts.load_scripts()
        return

    from modules import sd_models
    sd_models.list_models()
    startup_timer.record("list SD models")

    from modules import localization
    localization.list_localizations(cmd_opts.localizations_dir)
    startup_timer.record("list localizations")

    with startup_timer.subcategory("load scripts"):
        scripts.load_scripts()

    if reload_script_modules:
        for module in [module for name, module in sys.modules.items() if name.startswith("modules.ui")]:
            importlib.reload(module)
        startup_timer.record("reload script modules")

    from modules import modelloader
    modelloader.load_upscalers()
    startup_timer.record("load upscalers")

    from modules import sd_vae
    sd_vae.refresh_vae_list()
    startup_timer.record("refresh VAE")

    import modules.textual_inversion.textual_inversion as textual_inversion
    textual_inversion.list_textual_inversion_templates()
    startup_timer.record("refresh textual inversion templates")

    from modules import script_callbacks, sd_hijack_optimizations, sd_hijack
    script_callbacks.on_list_optimizers(sd_hijack_optimizations.list_optimizers)
    sd_hijack.list_optimizers()
    startup_timer.record("scripts list_optimizers")

    from modules import sd_unet
    sd_unet.list_unets()
    startup_timer.record("scripts list_unets")


    if not cmd_opts.skip_load_default_model:
        from modules import shared_items
        shared_items.reload_hypernetworks()
        startup_timer.record("reload hypernetworks")
        def load_model():
            """
            Accesses shared.sd_model property to load model.
            After it's available, if it has been loaded before this access by some extension,
            its optimization may be None because the list of optimizaers has neet been filled
            by that time, so we apply optimization again.
            """

            shared.sd_model  # noqa: B018

            if sd_hijack.current_optimizer is None:
                sd_hijack.apply_optimizations()

            from modules import devices
            devices.first_time_calculation()

        Thread(target=load_model).start()

    from modules import ui_extra_networks
    ui_extra_networks.initialize()
    ui_extra_networks.register_default_pages()

    from modules import extra_networks
    extra_networks.initialize()
    extra_networks.register_default_extra_networks()
    startup_timer.record("initialize extra networks")
