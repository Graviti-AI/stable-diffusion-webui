import json
import os.path
import sys
import time
import traceback

import git

import gradio as gr
import html
import shutil
import errno

import gradio.routes

from modules import extensions, shared, paths
from modules.call_queue import wrap_gradio_gpu_call

available_extensions = {"extensions": []}


def check_access():
    assert not shared.cmd_opts.disable_extension_access, "extension access disabled because of command line flags"
    assert shared.cmd_opts.enable_insecure_calls, "forbidden"


def apply_and_restart(disable_list, update_list, disable_all):
    check_access()

    disabled = json.loads(disable_list)
    assert type(disabled) == list, f"wrong disable_list data for apply_and_restart: {disable_list}"

    update = json.loads(update_list)
    assert type(update) == list, f"wrong update_list data for apply_and_restart: {update_list}"

    update = set(update)

    for ext in extensions.extensions:
        if ext.name not in update:
            continue

        try:
            ext.fetch_and_reset_hard()
        except Exception:
            print(f"Error getting updates for {ext.name}:", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)

    shared.opts.disabled_extensions = disabled
    shared.opts.disable_all_extensions = disable_all
    shared.opts.save(shared.config_filename)

    shared.state.interrupt()
    shared.state.need_restart = True


def check_updates(request: gradio.routes.Request, id_task, disable_list):
    check_access()

    disabled = json.loads(disable_list)
    assert type(disabled) == list, f"wrong disable_list data for apply_and_restart: {disable_list}"

    exts = [ext for ext in extensions.extensions if ext.remote is not None and ext.name not in disabled]
    shared.state.job_count = len(exts)

    for ext in exts:
        shared.state.textinfo = ext.name

        try:
            ext.check_updates()
        except FileNotFoundError as e:
            if 'FETCH_HEAD' not in str(e):
                raise
        except Exception:
            print(f"Error checking updates for {ext.name}:", file=sys.stderr)
            print(traceback.format_exc(), file=sys.stderr)

        shared.state.nextjob()

    return extension_table(), ""


def extension_table():
    code = f"""<!-- {time.time()} -->
    <table id="extensions">
        <thead>
            <tr>
                <th><abbr title="Use checkbox to enable the extension; it will be enabled or disabled when you click apply button">Extension</abbr></th>
                <th>URL</th>
                <th><abbr title="Extension version">Version</abbr></th>
                <th><abbr title="Use checkbox to mark the extension for update; it will be updated when you click apply button">Update</abbr></th>
            </tr>
        </thead>
        <tbody>
    """

    for ext in extensions.extensions:
        ext.read_info_from_repo()

        remote = f"""<a href="{html.escape(ext.remote or '')}" target="_blank">{html.escape("built-in" if ext.is_builtin else ext.remote or '')}</a>"""

        if ext.can_update:
            ext_status = f"""<label><input class="gr-check-radio gr-checkbox" name="update_{html.escape(ext.name)}" checked="checked" type="checkbox">{html.escape(ext.status)}</label>"""
        else:
            ext_status = ext.status

        style = ""
        if shared.opts.disable_all_extensions == "extra" and not ext.is_builtin or shared.opts.disable_all_extensions == "all":
            style = ' style="color: var(--primary-400)"'

        code += f"""
            <tr>
                <td><label{style}><input class="gr-check-radio gr-checkbox" name="enable_{html.escape(ext.name)}" type="checkbox" {'checked="checked"' if ext.enabled else ''}>{html.escape(ext.name)}</label></td>
                <td>{remote}</td>
                <td>{ext.version}</td>
                <td{' class="extension_status"' if ext.remote is not None else ''}>{ext_status}</td>
            </tr>
    """

    code += """
        </tbody>
    </table>
    """

    return code


def normalize_git_url(url):
    if url is None:
        return ""

    url = url.replace(".git", "")
    return url


def install_extension_from_url(request: gradio.routes.Request, dirname, url):
    check_access()

    assert url, 'No URL specified'

    if dirname is None or dirname == "":
        *parts, last_part = url.split('/')
        last_part = normalize_git_url(last_part)

        dirname = last_part

    target_dir = os.path.join(extensions.extensions_dir, dirname)
    assert not os.path.exists(target_dir), f'Extension directory already exists: {target_dir}'

    normalized_url = normalize_git_url(url)
    assert len([x for x in extensions.extensions if normalize_git_url(x.remote) == normalized_url]) == 0, 'Extension with this URL is already installed'

    tmpdir = os.path.join(paths.data_path, "tmp", dirname)

    try:
        shutil.rmtree(tmpdir, True)
        with git.Repo.clone_from(url, tmpdir) as repo:
            repo.remote().fetch()
            for submodule in repo.submodules:
                submodule.update()
        try:
            os.rename(tmpdir, target_dir)
        except OSError as err:
            if err.errno == errno.EXDEV:
                # Cross device link, typical in docker or when tmp/ and extensions/ are on different file systems
                # Since we can't use a rename, do the slower but more versitile shutil.move()
                shutil.move(tmpdir, target_dir)
            else:
                # Something else, not enough free space, permissions, etc.  rethrow it so that it gets handled.
                raise err

        import launch
        launch.run_extension_installer(target_dir)

        extensions.list_extensions()
        return [extension_table(), html.escape(f"Installed into {target_dir}. Use Installed tab to restart.")]
    finally:
        shutil.rmtree(tmpdir, True)


def install_extension_from_index(request: gr.Request, url, hide_tags, sort_column, filter_text):
    ext_table, message = install_extension_from_url(request, url)

    code, _ = refresh_available_extensions_from_data(hide_tags, sort_column, filter_text)

    return code, ext_table, message, ''


def refresh_available_extensions(request: gradio.routes.Request, url, hide_tags, sort_column):
    global available_extensions

    import urllib.request
    with urllib.request.urlopen(url) as response:
        text = response.read()

    available_extensions = json.loads(text)

    code, tags = refresh_available_extensions_from_data(hide_tags, sort_column)

    return url, code, gr.CheckboxGroup.update(choices=tags), '', ''


def refresh_available_extensions_for_tags(request: gradio.routes.Request, hide_tags, sort_column, filter_text):
    code, _ = refresh_available_extensions_from_data(hide_tags, sort_column, filter_text)

    return code, ''


def search_extensions(filter_text, hide_tags, sort_column):
    code, _ = refresh_available_extensions_from_data(hide_tags, sort_column, filter_text)

    return code, ''


sort_ordering = [
    # (reverse, order_by_function)
    (True, lambda x: x.get('added', 'z')),
    (False, lambda x: x.get('added', 'z')),
    (False, lambda x: x.get('name', 'z')),
    (True, lambda x: x.get('name', 'z')),
    (False, lambda x: 'z'),
]


def refresh_available_extensions_from_data(hide_tags, sort_column, filter_text=""):
    extlist = available_extensions["extensions"]
    installed_extension_urls = {normalize_git_url(extension.remote): extension.name for extension in extensions.extensions}

    tags = available_extensions.get("tags", {})
    tags_to_hide = set(hide_tags)
    hidden = 0

    code = f"""<!-- {time.time()} -->
    <table id="available_extensions">
        <thead>
            <tr>
                <th>Extension</th>
                <th>Description</th>
                <th>Action</th>
            </tr>
        </thead>
        <tbody>
    """

    sort_reverse, sort_function = sort_ordering[sort_column if 0 <= sort_column < len(sort_ordering) else 0]

    for ext in sorted(extlist, key=sort_function, reverse=sort_reverse):
        name = ext.get("name", "noname")
        added = ext.get('added', 'unknown')
        url = ext.get("url", None)
        description = ext.get("description", "")
        extension_tags = ext.get("tags", [])

        if url is None:
            continue

        existing = installed_extension_urls.get(normalize_git_url(url), None)
        extension_tags = extension_tags + ["installed"] if existing else extension_tags

        if len([x for x in extension_tags if x in tags_to_hide]) > 0:
            hidden += 1
            continue

        if filter_text and filter_text.strip():
            if filter_text.lower() not in html.escape(name).lower() and filter_text.lower() not in html.escape(description).lower():
                hidden += 1
                continue

        install_code = f"""<button onclick="install_extension_from_index(this, '{html.escape(url)}')" {"disabled=disabled" if existing else ""} class="lg secondary gradio-button custom-button">{"Install" if not existing else "Installed"}</button>"""

        tags_text = ", ".join([f"<span class='extension-tag' title='{tags.get(x, '')}'>{x}</span>" for x in extension_tags])

        code += f"""
            <tr>
                <td><a href="{html.escape(url)}" target="_blank">{html.escape(name)}</a><br />{tags_text}</td>
                <td>{html.escape(description)}<p class="info"><span class="date_added">Added: {html.escape(added)}</span></p></td>
                <td>{install_code}</td>
            </tr>

        """

        for tag in [x for x in extension_tags if x not in tags]:
            tags[tag] = tag

    code += """
        </tbody>
    </table>
    """

    if hidden > 0:
        code += f"<p>Extension hidden: {hidden}</p>"

    return code, list(tags)


def create_ui():
    import modules.ui

    with gr.Blocks(analytics_enabled=False) as ui:
        with gr.Tabs(elem_id="tabs_extensions") as tabs:
            with gr.TabItem("Installed"):

                with gr.Row(elem_id="extensions_installed_top"):
                    apply = gr.Button(value="Apply and restart UI", variant="primary")
                    check = gr.Button(value="Check for updates")
                    extensions_disable_all = gr.Radio(label="Disable all extensions", choices=["none", "extra", "all"], value=shared.opts.disable_all_extensions, elem_id="extensions_disable_all")
                    extensions_disabled_list = gr.Text(elem_id="extensions_disabled_list", visible=False).style(container=False)
                    extensions_update_list = gr.Text(elem_id="extensions_update_list", visible=False).style(container=False)

                html = ""
                if shared.opts.disable_all_extensions != "none":
                    html = """
<span style="color: var(--primary-400);">
    "Disable all extensions" was set, change it to "none" to load all extensions again
</span>
                    """
                info = gr.HTML(html)
                extensions_table = gr.HTML(lambda: extension_table())

                apply.click(
                    fn=apply_and_restart,
                    _js="extensions_apply",
                    inputs=[extensions_disabled_list, extensions_update_list, extensions_disable_all],
                    outputs=[],
                )

                check.click(
                    fn=wrap_gradio_gpu_call(check_updates, extra_outputs=[gr.update()]),
                    _js="extensions_check",
                    inputs=[info, extensions_disabled_list],
                    outputs=[extensions_table, info],
                )

            with gr.TabItem("Available"):
                with gr.Row():
                    refresh_available_extensions_button = gr.Button(value="Load from:", variant="primary")
                    available_extensions_index = gr.Text(value="https://raw.githubusercontent.com/AUTOMATIC1111/stable-diffusion-webui-extensions/master/index.json", label="Extension index URL").style(container=False)
                    extension_to_install = gr.Text(elem_id="extension_to_install", visible=False)
                    install_extension_button = gr.Button(elem_id="install_extension_button", visible=False)

                with gr.Row():
                    hide_tags = gr.CheckboxGroup(value=["ads", "localization", "installed"], label="Hide extensions with tags", choices=["script", "ads", "localization", "installed"])
                    sort_column = gr.Radio(value="newest first", label="Order", choices=["newest first", "oldest first", "a-z", "z-a", "internal order", ], type="index")

                with gr.Row():
                    search_extensions_text = gr.Text(label="Search").style(container=False)

                install_result = gr.HTML()
                available_extensions_table = gr.HTML()

                refresh_available_extensions_button.click(
                    fn=modules.ui.wrap_gradio_call(refresh_available_extensions, extra_outputs=[gr.update(), gr.update(), gr.update()]),
                    inputs=[available_extensions_index, hide_tags, sort_column],
                    outputs=[available_extensions_index, available_extensions_table, hide_tags, install_result, search_extensions_text],
                )

                install_extension_button.click(
                    fn=modules.ui.wrap_gradio_call(install_extension_from_index, extra_outputs=[gr.update(), gr.update()]),
                    inputs=[extension_to_install, hide_tags, sort_column, search_extensions_text],
                    outputs=[available_extensions_table, extensions_table, install_result],
                )

                search_extensions_text.change(
                    fn=modules.ui.wrap_gradio_call(search_extensions, extra_outputs=[gr.update()]),
                    inputs=[search_extensions_text, hide_tags, sort_column],
                    outputs=[available_extensions_table, install_result],
                )

                hide_tags.change(
                    fn=modules.ui.wrap_gradio_call(refresh_available_extensions_for_tags, extra_outputs=[gr.update()]),
                    inputs=[hide_tags, sort_column, search_extensions_text],
                    outputs=[available_extensions_table, install_result]
                )

                sort_column.change(
                    fn=modules.ui.wrap_gradio_call(refresh_available_extensions_for_tags, extra_outputs=[gr.update()]),
                    inputs=[hide_tags, sort_column, search_extensions_text],
                    outputs=[available_extensions_table, install_result]
                )

            with gr.TabItem("Install from URL"):
                install_url = gr.Text(label="URL for extension's git repository")
                install_dirname = gr.Text(label="Local directory name", placeholder="Leave empty for auto")
                install_button = gr.Button(value="Install", variant="primary")
                install_result = gr.HTML(elem_id="extension_install_result")

                install_button.click(
                    fn=modules.ui.wrap_gradio_call(install_extension_from_url, extra_outputs=[gr.update()]),
                    inputs=[install_dirname, install_url],
                    outputs=[extensions_table, install_result],
                )

    return ui
