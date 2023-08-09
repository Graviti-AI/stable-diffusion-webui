import gradio as gr

from modules import ui_common, shared, script_callbacks, scripts, sd_models, sysinfo
from modules.call_queue import wrap_gradio_call
import modules.call_utils
from modules.shared import opts
from modules.ui_components import FormRow
from modules.ui_gradio_extensions import reload_javascript


def get_value_for_setting(key, request: gr.Request = None):
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

    return gr.update(value=value, **args)


def create_setting_component(key, is_quicksettings=False, visible=True, interactive=True):
    def fun():
        return opts.data[key] if key in opts.data else opts.data_labels[key].default

    info = opts.data_labels[key]
    t = type(info.default)

    args = info.component_args() if callable(info.component_args) else info.component_args
    args = args if args else {}
    args["visible"] = visible
    args["interactive"] = interactive

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

    if info.refresh is not None:
        if is_quicksettings:
            res = comp(label=info.label, value=fun(), elem_id=elem_id, elem_classes="quicksettings", **(args or {}))
            ui_common.create_refresh_button(
                res, info.refresh, info.component_args, f"refresh_{key}", visible=visible, interactive=interactive)
        else:
            with FormRow():
                res = comp(label=info.label, value=fun(), elem_id=elem_id, **(args or {}))
                ui_common.create_refresh_button(
                    res, info.refresh, info.component_args, f"refresh_{key}", visible=visible, interactive=interactive)
    else:
        res = comp(label=info.label, value=fun(), elem_id=elem_id, **(args or {}))

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

        if not opts.set(key, value):
            # the returned extra two values are used to tell img2img/txt2img current loaded model
            return gr.update(value=getattr(opts, key)), opts.dumpjson(), value, value
            #return gr.update(value=getattr(opts, key)), opts.dumpjson()

        opts.save(shared.config_filename)

        # the returned extra two values are used to tell img2img/txt2img current loaded model
        return get_value_for_setting(key, request), opts.dumpjson(), value, value
        #return get_value_for_setting(key), opts.dumpjson()

    def create_ui(self, loadsave, dummy_component):
        self.components = []
        self.component_dict = {}
        self.dummy_component = dummy_component

        shared.settings_components = self.component_dict

        script_callbacks.ui_settings_callback()
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

            self.quicksettings_names = opts.quicksettings_list
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
                        current_row = gr.Column(variant='compact')
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
                    gr.HTML('<a href="./internal/sysinfo-download" class="sysinfo_big_link" download>Download system info</a><br /><a href="./internal/sysinfo">(or open as text in a new page)</a>', elem_id="sysinfo_download")

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
                        unload_sd_model = gr.Button(value='Unload SD checkpoint to free VRAM', elem_id="sett_unload_sd_model", interactive=self.interactive)
                        reload_sd_model = gr.Button(value='Reload the last SD checkpoint back into VRAM', elem_id="sett_reload_sd_model", interactive=self.interactive)

                with gr.TabItem("Licenses", id="licenses", elem_id="settings_tab_licenses"):
                    gr.HTML(shared.html("licenses.html"), elem_id="licenses")

                gr.Button(value="Show all pages", elem_id="settings_show_all_pages", interactive=self.interactive)

                self.text_settings = gr.Textbox(elem_id="settings_json", value=lambda: opts.dumpjson(), visible=False)

            unload_sd_model.click(
                fn=sd_models.unload_model_weights,
                inputs=[],
                outputs=[]
            )

            reload_sd_model.click(
                fn=sd_models.reload_model_weights,
                inputs=[],
                outputs=[]
            )

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

        self.interface = settings_interface

    def add_quicksettings(self):
        with gr.Row(elem_id="quicksettings", variant="compact"):
            for _i, k, _item in sorted(self.quicksettings_list, key=lambda x: self.quicksettings_names.get(x[1], x[0])):
                component = create_setting_component(k, is_quicksettings=True, interactive=self.interactive)
                self.component_dict[k] = component

    def add_functionality(self, demo, sd_model_selection):
        self.submit.click(
            fn=wrap_gradio_call(lambda *args: self.run_settings(*args), extra_outputs=[gr.update()]),
            inputs=self.components,
            outputs=[self.text_settings, self.result],
        )

        def make_run_settings_single(key):
            def f(request: gr.Request, value, _=None):
                return self.run_settings_single(request, value, key)
            return f

        for _i, k, _item in self.quicksettings_list:
            component = self.component_dict[k]
            info = opts.data_labels[k]
            outputs = [component, self.text_settings]

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
                    outputs=outputs,
                    show_progress=info.refresh is not None,
                )

        button_set_checkpoint = gr.Button('Change checkpoint', elem_id='change_checkpoint', visible=False)

        def set_checkpoint_when_click_on_card(request: gr.Request, checkpoint_id, current_checkpoint):
            ckpt_info = sd_models.get_closet_checkpoint_match(checkpoint_id)

            if ckpt_info is not None:
                return ckpt_info.title
            return current_checkpoint

        button_set_checkpoint.click(
            fn=set_checkpoint_when_click_on_card,
            _js="function(current, dummy){ var res = desiredCheckpointName; desiredCheckpointName = ''; return [res || current, current]; }",
            inputs=[sd_model_selection, self.dummy_component],
            outputs=[sd_model_selection],
        )

        component_keys = [k for k in opts.data_labels.keys() if k in self.component_dict]

        def get_settings_values(request: gr.Request):
            return [get_value_for_setting(key, request) for key in component_keys]

        demo.load(
            fn=get_settings_values,
            inputs=[],
            outputs=[self.component_dict[k] for k in component_keys],
            queue=False,
        )
