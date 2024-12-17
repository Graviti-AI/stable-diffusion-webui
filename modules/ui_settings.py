import gradio as gr

from modules import ui_common, shared, script_callbacks, scripts, sd_models, sysinfo, timer, shared_items
from modules.call_queue import wrap_gradio_call_no_job
from modules.options import options_section
from modules.shared import opts
from modules.ui_components import FormRow
from modules.ui_gradio_extensions import reload_javascript
from concurrent.futures import ThreadPoolExecutor, as_completed
from modules_forge import main_entry

import modules.call_utils


def get_value_for_setting(key, request: gr.Request):
    value = getattr(opts, key)

    info = opts.data_labels[key]
    if callable(info.component_args):
        inputs = modules.call_utils.special_args(info.component_args, [], request)
        if inputs:
            args = info.component_args(*inputs)
        else:
            args = info.component_args()
    else:
        args = info.component_args or {}
    args = {k: v for k, v in args.items() if k not in {'precision'}}
    if "value" not in args:
        args["value"] = value

    return gr.update(**args)


def create_setting_component(key, is_quicksettings=False, visible=True, interactive=True):
    def fun():
        return opts.data[key] if key in opts.data else opts.data_labels[key].default

    info = opts.data_labels[key]
    t = type(info.default)

    args = info.component_args() if callable(info.component_args) else info.component_args
    args = args if args else {}
    args["visible"] = visible
    args["interactive"] = interactive

    if "value" not in args:
        args["value"] = fun()

    if info.component is not None:
        comp = info.component
    elif t == str:
        comp = gr.Textbox
    elif t == int:
        comp = gr.Number
    elif t == bool:
        comp = gr.Checkbox
    else:
        raise Exception(f'bad options item type: {t} for key {key}')

    elem_id = f"setting_{key}"

    if comp == gr.State:
        return gr.State(fun())

    if info.refresh is not None:
        if is_quicksettings:
            res = comp(label=info.label, elem_id=elem_id, elem_classes="quicksettings", **(args or {}))
            ui_common.create_refresh_button(
                res, info.refresh, info.component_args, f"refresh_{key}", visible=visible, interactive=interactive)
        else:
            with FormRow():
                res = comp(label=info.label, elem_id=elem_id, **(args or {}))
                ui_common.create_refresh_button(
                    res, info.refresh, info.component_args, f"refresh_{key}", visible=visible, interactive=interactive)
    else:
        res = comp(label=info.label, elem_id=elem_id, **(args or {}))

    return res


class UiSettings:
    submit = None
    result = None
    interface = None
    components = None
    component_dict = None
    dummy_component = None
    quicksettings_list = None
    quicksettings_names = None
    text_settings = None
    interactive = True
    show_all_pages = None
    show_one_page = None
    search_input = None

    def __init__(self, interactive=True):
        self.interactive = interactive

    def run_settings(self, request: gr.Request, *args):
        import modules.call_utils
        modules.call_utils.check_insecure_calls()

        changed = []

        for key, value, comp in zip(opts.data_labels.keys(), args, self.components):
            assert comp == self.dummy_component or opts.same_type(value, opts.data_labels[key].default), f"Bad value for setting {key}: {value}; expecting {type(opts.data_labels[key].default).__name__}"

        for key, value, comp in zip(opts.data_labels.keys(), args, self.components):
            if comp == self.dummy_component:
                continue

            # don't set (Managed by Forge) options, they revert to defaults
            if key in ["sd_model_checkpoint", "CLIP_stop_at_last_layers", "sd_vae"]:
                continue

            if opts.set(key, value):
                changed.append(key)

        try:
            opts.save(shared.config_filename)
        except RuntimeError:
            return opts.dumpjson(), f'{len(changed)} settings changed without save: {", ".join(changed)}.'
        return opts.dumpjson(), f'{len(changed)} settings changed{": " if changed else ""}{", ".join(changed)}.'

    def run_settings_single(self, request: gr.Request, value, key):
        if not opts.same_type(value, opts.data_labels[key].default):
            return gr.update(visible=True), opts.dumpjson()

        if value is None or not opts.set(key, value):
            # the returned extra two values are used to tell img2img/txt2img current loaded model
            return gr.update(value=getattr(opts, key)), opts.dumpjson(), value, value
            #return gr.update(value=getattr(opts, key)), opts.dumpjson()

        opts.save(shared.config_filename)

        # the returned extra two values are used to tell img2img/txt2img current loaded model
        return get_value_for_setting(key, request), opts.dumpjson(), value, value
        #return get_value_for_setting(key), opts.dumpjson()

    def register_settings(self):
        script_callbacks.ui_settings_callback()

    def create_ui(self, loadsave, dummy_component):
        self.components = []
        self.component_dict = {}
        self.dummy_component = dummy_component

        shared.settings_components = self.component_dict

        # we add this as late as possible so that scripts have already registered their callbacks
        opts.data_labels.update(options_section(('callbacks', "Callbacks", "system"), {
            **shared_items.callbacks_order_settings(),
        }))

        opts.reorder()

        with gr.Blocks(analytics_enabled=False) as settings_interface:
            with gr.Row():
                with gr.Column(scale=6):
                    self.submit = gr.Button(
                        value="Apply settings",
                        variant='primary',
                        elem_id="settings_submit",
                        interactive=self.interactive)
                with gr.Column():
                    restart_gradio = gr.Button(
                        value='Reload UI',
                        variant='primary',
                        elem_id="settings_restart_gradio",
                        interactive=self.interactive)

            self.result = gr.HTML(elem_id="settings_result")

            self.quicksettings_names = opts.quick_setting_list
            self.quicksettings_names = {x: i for i, x in enumerate(self.quicksettings_names) if x != 'quicksettings'}

            self.quicksettings_list = []

            previous_section = None
            current_tab = None
            current_row = None
            with gr.Tabs(elem_id="settings"):
                for i, (k, item) in enumerate(opts.data_labels.items()):
                    section_must_be_skipped = item.section[0] is None

                    if previous_section != item.section and not section_must_be_skipped:
                        elem_id, text = item.section

                        if current_tab is not None:
                            current_row.__exit__()
                            current_tab.__exit__()

                        gr.Group()
                        current_tab = gr.TabItem(elem_id=f"settings_{elem_id}", label=text)
                        current_tab.__enter__()
                        current_row = gr.Column(elem_id=f"column_settings_{elem_id}", variant='compact')
                        current_row.__enter__()

                        previous_section = item.section

                    if k in self.quicksettings_names and not shared.cmd_opts.freeze_settings:
                        self.quicksettings_list.append((i, k, item))
                        self.components.append(dummy_component)
                    elif section_must_be_skipped:
                        self.components.append(dummy_component)
                    else:
                        component = create_setting_component(k, interactive=self.interactive)
                        self.component_dict[k] = component
                        self.components.append(component)

                if current_tab is not None:
                    current_row.__exit__()
                    current_tab.__exit__()

                with gr.TabItem("Defaults", id="defaults", elem_id="settings_tab_defaults"):
                    loadsave.create_ui()

                with gr.TabItem("Sysinfo", id="sysinfo", elem_id="settings_tab_sysinfo"):
                    gr.HTML('<a href="./internal/sysinfo-download" class="sysinfo_big_link" download>Download system info</a><br /><a href="./internal/sysinfo" target="_blank">(or open as text in a new page)</a>', elem_id="sysinfo_download")

                    with gr.Row():
                        with gr.Column(scale=1):
                            sysinfo_check_file = gr.File(
                                label="Check system info for validity", type='binary', interactive=self.interactive)
                        with gr.Column(scale=1):
                            sysinfo_check_output = gr.HTML("", elem_id="sysinfo_validity")
                        with gr.Column(scale=100):
                            pass

                with gr.TabItem("Actions", id="actions", elem_id="settings_tab_actions"):
                    request_notifications = gr.Button(value='Request browser notifications', elem_id="request_notifications", interactive=self.interactive)
                    download_localization = gr.Button(value='Download localization template', elem_id="download_localization", interactive=self.interactive)
                    reload_script_bodies = gr.Button(value='Reload custom script bodies (No ui updates, No restart)', variant='secondary', elem_id="settings_reload_script_bodies", interactive=self.interactive)
                    with gr.Row():
                        unload_sd_model = gr.Button(value='Unload all models', elem_id="sett_unload_sd_model")
#                        reload_sd_model = gr.Button(value='Load SD checkpoint to VRAM from RAM', elem_id="sett_reload_sd_model")
                    with gr.Row():
                        calculate_all_checkpoint_hash = gr.Button(value='Calculate hash for all checkpoint', elem_id="calculate_all_checkpoint_hash", interactive=self.interactive)
                        calculate_all_checkpoint_hash_threads = gr.Number(value=1, label="Number of parallel calculations", elem_id="calculate_all_checkpoint_hash_threads", precision=0, minimum=1, interactive=self.interactive)

                with gr.TabItem("Licenses", id="licenses", elem_id="settings_tab_licenses"):
                    gr.HTML(shared.html("licenses.html"), elem_id="licenses")

                self.show_all_pages = gr.Button(value="Show all pages", elem_id="settings_show_all_pages", interactive=self.interactive)
                self.show_one_page = gr.Button(value="Show only one page", elem_id="settings_show_one_page", visible=False, interactive=self.interactive)
                self.show_one_page.click(lambda: None)

                self.search_input = gr.Textbox(value="", elem_id="settings_search", max_lines=1, placeholder="Search...", show_label=False, interactive=self.interactive)

                self.text_settings = gr.Textbox(elem_id="settings_json", value=lambda: opts.dumpjson(), visible=False, interactive=self.interactive)

            def call_func_and_return_text(func, text):
                def handler():
                    t = timer.Timer()
                    func()
                    t.record(text)

                    return f'{text} in {t.total:.1f}s'

                return handler

            unload_sd_model.click(
                fn=call_func_and_return_text(sd_models.unload_model_weights, 'Unloaded all models'),
                inputs=[],
                outputs=[self.result]
            )

#            reload_sd_model.click(
#                fn=call_func_and_return_text(lambda: sd_models.send_model_to_device(shared.sd_model), 'Loaded the checkpoint'),
#                inputs=[],
#                outputs=[self.result]
#            )

            request_notifications.click(
                fn=lambda: None,
                inputs=[],
                outputs=[],
                _js='function(){}'
            )

            download_localization.click(
                fn=lambda: None,
                inputs=[],
                outputs=[],
                _js='download_localization'
            )

            def reload_scripts():
                scripts.reload_script_body_only()
                reload_javascript()  # need to refresh the html page

            reload_script_bodies.click(
                fn=reload_scripts,
                inputs=[],
                outputs=[]
            )

            restart_gradio.click(
                fn=shared.state.request_restart,
                _js='restart_reload',
                inputs=[],
                outputs=[],
            )

            def check_file(x):
                if x is None:
                    return ''

                if sysinfo.check(x.decode('utf8', errors='ignore')):
                    return 'Valid'

                return 'Invalid'

            sysinfo_check_file.change(
                fn=check_file,
                inputs=[sysinfo_check_file],
                outputs=[sysinfo_check_output],
            )

            def calculate_all_checkpoint_hash_fn(max_thread):
                checkpoints_list = sd_models.checkpoints_list.values()
                with ThreadPoolExecutor(max_workers=max_thread) as executor:
                    futures = [executor.submit(checkpoint.calculate_shorthash) for checkpoint in checkpoints_list]
                    completed = 0
                    for _ in as_completed(futures):
                        completed += 1
                        print(f"{completed} / {len(checkpoints_list)} ")
                    print("Finish calculating hash for all checkpoints")

            calculate_all_checkpoint_hash.click(
                fn=calculate_all_checkpoint_hash_fn,
                inputs=[calculate_all_checkpoint_hash_threads],
            )

        self.interface = settings_interface

    def add_quicksettings(self):
        with gr.Row(elem_id="quicksettings", variant="compact") as quicksettings_row:
            main_entry.make_checkpoint_manager_ui()
            for _i, k, _item in sorted(self.quicksettings_list, key=lambda x: self.quicksettings_names.get(x[1], x[0])):
                component = create_setting_component(k, is_quicksettings=True, interactive=self.interactive)
                self.component_dict[k] = component
        return quicksettings_row

    def add_functionality(self, demo):
        self.submit.click(
            fn=wrap_gradio_call_no_job(lambda *args: self.run_settings(*args), extra_outputs=[gr.update()]),
            inputs=self.components,
            outputs=[self.text_settings, self.result],
        )

        def make_run_settings_single(key):
            def f(request: gr.Request, value, _=None):
                return self.run_settings_single(request, value, key)
            return f

        for _i, k, _item in self.quicksettings_list:
            component = self.component_dict[k]

            if isinstance(component, gr.Textbox):
                methods = [component.submit, component.blur]
            elif hasattr(component, 'release'):
                methods = [component.release]
            else:
                methods = [component.change]

            for method in methods:
                method(
                    fn=make_run_settings_single(k),
                    inputs=[component],
                    outputs=[component, self.text_settings],
                    show_progress=False,
                )

        def button_set_checkpoint_change(model, vae, dummy):
            if 'Built in' in vae:
                vae.remove('Built in')
            model = sd_models.match_checkpoint_to_name(model)
            return model, vae, opts.dumpjson()

        # button_set_checkpoint = gr.Button('Change checkpoint', elem_id='change_checkpoint', visible=False)
        # button_set_checkpoint.click(
        #     fn=button_set_checkpoint_change,
        #     js="function(c, v, n){ var ckpt = desiredCheckpointName; var vae = desiredVAEName; if (ckpt == null) ckpt = c; if (vae == 0) vae = v; desiredCheckpointName = null; desiredVAEName = 0; return [ckpt, vae, null]; }",
        #     inputs=[main_entry.ui_checkpoint, main_entry.ui_vae, self.dummy_component],
        #     outputs=[main_entry.ui_checkpoint, main_entry.ui_vae, self.text_settings],
        # )

        component_keys = [k for k in opts.data_labels.keys() if k in self.component_dict]

        def get_settings_values(request: gr.Request):
            return [get_value_for_setting(key, request) for key in component_keys]

        demo.load(
            fn=get_settings_values,
            inputs=[],
            outputs=[self.component_dict[k] for k in component_keys],
            queue=False,
        )

    def search(self, text):
        print(text)

        return [gr.update(visible=text in (comp.label or "")) for comp in self.components]
