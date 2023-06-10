import glob
import os.path
import urllib.parse
from pathlib import Path
from PIL import PngImagePlugin
import time

from copy import deepcopy
from modules import shared
from modules.images import read_info_from_image
from modules.paths import Paths
from modules.paths_internal import script_path
import gradio as gr
from fastapi import Request
import json
import html
from threading import Lock

from modules.generation_parameters_copypaste import image_from_url_text
from modules.ui_common import create_upload_button
import modules.user

extra_pages = []
allowed_dirs = set()
preview_search_dir = dict()
model_list_refresh_lock = Lock()


def register_page(page):
    """registers extra networks page for the UI; recommend doing it in on_before_ui() callback for extensions"""

    extra_pages.append(page)
    allowed_dirs.clear()
    allowed_dirs.update(set(sum([x.allowed_directories_for_previews() for x in extra_pages], [])))


def fetch_file(request: Request, filename: str = "", model_type: str = ""):
    from starlette.responses import FileResponse

    no_preview_background_path = os.path.join(script_path, "static/icons/card-no-preview.png")

    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".png", ".jpg", ".webp"):
        return FileResponse(no_preview_background_path, headers={"Accept-Ranges": "bytes"})

    paths = Paths(request)
    private_preview_path = os.path.join(paths.model_previews_dir(), model_type, filename)
    if os.path.exists(private_preview_path):
        return FileResponse(private_preview_path, headers={"Accept-Ranges": "bytes"})

    if model_type not in preview_search_dir:
        return FileResponse(no_preview_background_path, headers={"Accept-Ranges": "bytes"})

    for dirpath in preview_search_dir[model_type]:
        filepath = os.path.join(dirpath, filename)
        if os.path.exists(filepath):
            # would profit from returning 304
            return FileResponse(filepath, headers={"Accept-Ranges": "bytes"})
    return FileResponse(no_preview_background_path, headers={"Accept-Ranges": "bytes"})


def make_html_metadata(metadata):
    from starlette.responses import HTMLResponse
    if not metadata:
        return HTMLResponse("<h1>404, could not find metadata</h1>")

    try:
        metadata["trigger_word"] = "".join(
            [f"<div class='model-metadata-trigger-word'>{word.strip()}</div>"
             for item in metadata["trigger_word"]
             for word in item.split(",") if word.strip()])
        metadata["tags"] = "".join(
            [f"<div class='model-metadata-tag'>{item}</div>" for item in metadata["tags"]])
        metadata["metadata"] = "".join(
            [f"""<tr class='model-metadata-metadata-table-row'>
                <td class='model-metadata-metadata-table-key'>{key}:</td>
                <td class='model-metadata-metadata-table-value'>{metadata['metadata'][key]}</td>
             </tr>"""
             for key in metadata["metadata"]])
        metadata["metadata"] = f"<table>{metadata['metadata']}</table>"

        metadata_html = shared.html("extra-networks-metadata.html").format(**metadata)
        return HTMLResponse(metadata_html)
    except Exception as e:
        return HTMLResponse(f"<h1>500, {e.__str__()}</h1>")


def get_metadata(page: str = "", item: str = ""):
    from starlette.responses import HTMLResponse

    # There are two sources where this api being called
    # one is construct in python code, which directly users page.name
    # the other one is in js code which uses model_type
    page = next(iter([x for x in extra_pages if x.name == page or x.name.lower().replace(" ", "_") == page]), None)
    if page is None:
        return HTMLResponse("<h1>404, could not find page</h1>")

    metadata = page.metadata.get(item)
    if metadata is None:
        return HTMLResponse("<h1>404, could not find metadata</h1>")

    metadata = deepcopy(metadata)
    return make_html_metadata(metadata)


def get_extra_networks_models(request: Request, page_name: str, search_value: str, page: int, page_size: int,
                              need_refresh: bool):
    from starlette.responses import JSONResponse

    model_list = []
    count = 0
    allow_negative_prompt = False

    def item_filter(item: dict) -> bool:
        return search_value in item.get('search_term', '').lower()

    for page_item in extra_pages:
        if page_item.name.replace(" ", "_") == page_name:
            with model_list_refresh_lock:
                if need_refresh:
                    page_item.refresh(request)
                items = list(filter(item_filter, page_item.list_items()))
            model_list = items[(page - 1) * page_size: page * page_size]
            count = len(items)
            allow_negative_prompt = page_item.allow_negative_prompt
            break

    return JSONResponse({
        "page": page,
        "total_count": count,
        "model_list": model_list,
        "allow_negative_prompt": allow_negative_prompt
    })


def get_private_previews(request: Request, model_type: str):
    from starlette.responses import JSONResponse
    paths = Paths(request)
    private_preview_search_dir = os.path.join(paths.model_previews_dir(), model_type)
    private_preview_list = []
    if os.path.exists(private_preview_search_dir):
        for filename in os.listdir(private_preview_search_dir):
            ext = os.path.splitext(filename)[1].lower()
            if ext in (".png", ".jpg", ".webp"):
                file_mtime = os.path.getmtime(os.path.join(private_preview_search_dir, filename))
                preview_info = {
                    "filename_no_extension": os.path.splitext(filename)[0],
                    "filename": filename,
                    "model_type": model_type,
                    "mtime": file_mtime,
                    "css_url":
                        f'url("/sd_extra_networks/thumb?filename={filename}&model_type={model_type}&mtime={file_mtime}")'
                }
                private_preview_list.append(preview_info)
    return JSONResponse(private_preview_list)


def add_pages_to_demo(app):
    app.add_api_route("/sd_extra_networks/thumb", fetch_file, methods=["GET"])
    app.add_api_route("/sd_extra_networks/metadata", get_metadata, methods=["GET"])
    app.add_api_route("/sd_extra_networks/private_previews", get_private_previews, methods=["GET"])
    app.add_api_route("/sd_extra_networks/models", get_extra_networks_models, methods=["GET"])


class ExtraNetworksPage:
    def __init__(self, title):
        self.title = title
        self.name = title.lower()
        self.card_page = shared.html("extra-networks-card.html")
        self.allow_negative_prompt = False
        self.metadata = {}
        self.max_model_size_mb = None  # If `None`, there is no limitation
        self.min_model_size_mb = None  # If `None`, there is no limitation

    @staticmethod
    def read_metadata_from_file(metadata_path: str):
        metadata = None
        if os.path.exists(metadata_path):
            with open(metadata_path, "r", encoding='utf8') as f:
                metadata = json.load(f)
        return metadata

    def refresh(self, request: gr.Request):
        pass

    def refresh_metadata(self):
        pass

    def link_preview(self, filename):
        model_type = self.name.replace(" ", "_")
        filename_unix = os.path.abspath(filename.replace('\\', '/'))
        if model_type not in preview_search_dir:
            preview_search_dir[model_type] = list()
        dirpath = os.path.dirname(filename_unix)
        if dirpath and (dirpath not in preview_search_dir[model_type]):
            preview_search_dir[model_type].append(dirpath)
        return "/sd_extra_networks/thumb?filename=" + \
               urllib.parse.quote(os.path.basename(filename_unix)) + \
               "&model_type=" + model_type + "&mtime=" + str(os.path.getmtime(filename))

    def search_terms_from_path(self, filename, possible_directories=None):
        abspath = os.path.abspath(filename)

        for parentdir in (
                possible_directories if possible_directories is not None else self.allowed_directories_for_previews()):
            parentdir = os.path.abspath(parentdir)
            if abspath.startswith(parentdir):
                return abspath[len(parentdir):].replace('\\', '/')

        return ""

    def create_html(self, tabname, upload_button_id, button_id=None, return_callbacks=False):
        view = shared.opts.extra_networks_default_view
        items_html = ''

        subdirs = {}
        for parentdir in [os.path.abspath(x) for x in self.allowed_directories_for_previews()]:
            for x in glob.glob(os.path.join(parentdir, '**/*'), recursive=True):
                if not os.path.isdir(x):
                    continue

                subdir = os.path.abspath(x)[len(parentdir):].replace("\\", "/")
                while subdir.startswith("/"):
                    subdir = subdir[1:]

                is_empty = len(os.listdir(x)) == 0
                if not is_empty and not subdir.endswith("/"):
                    subdir = subdir + "/"

                subdirs[subdir] = 1

        if subdirs:
            subdirs = {"": 1, **subdirs}

        subdirs_html = "".join([f"""
<button class='lg secondary gradio-button custom-button{" search-all" if subdir == "" else ""}' onclick='extraNetworksSearchButton("{tabname}_extra_tabs", event)'>
{html.escape(subdir if subdir != "" else "all")}
</button>
""" for subdir in subdirs])

        self_name_id = self.name.replace(" ", "_")

        # self.refresh_metadata()

        # Add a upload model button
        plus_sign_elem_id = f"{tabname}_{self_name_id}-plus-sign"
        loading_sign_elem_id = f"{tabname}_{self_name_id}-loading-sign"
        if not button_id:
            button_id = f"{upload_button_id}-card"
        dashboard_title_hint = ""
        model_size = ""
        if self.min_model_size_mb:
            model_size += f" min_model_size_mb='{self.min_model_size_mb}'"
            dashboard_title_hint += f" ( > {self.min_model_size_mb} MB"
        if self.max_model_size_mb:
            model_size += f" max_model_size_mb='{self.max_model_size_mb}'"
            if dashboard_title_hint:
                dashboard_title_hint += f" and < {self.max_model_size_mb} MB"
            else:
                dashboard_title_hint += f" ( < {self.max_model_size_mb} MB"
        if dashboard_title_hint:
            dashboard_title_hint += ")"
        height = f"height: {shared.opts.extra_networks_card_height}px;" if shared.opts.extra_networks_card_height else ''
        width = f"width: {shared.opts.extra_networks_card_width}px;" if shared.opts.extra_networks_card_width else ''
        items_html += shared.html("extra-networks-upload-button.html").format(
            button_id=button_id,
            style=f"{height}{width}",
            model_type=self_name_id,
            tabname=tabname,
            card_clicked=f'if (typeof register_button == "undefined") {{document.querySelector("#{upload_button_id}").click();}}',
            dashboard_title=f'{self.title} files only.{dashboard_title_hint}',
            model_size=model_size,
            plus_sign_elem_id=plus_sign_elem_id,
            loading_sign_elem_id=loading_sign_elem_id,
            name=f'Upload {self.title} Models',
            add_model_button_id=f"{tabname}_{self_name_id}_add_model-to-workspace",
        )

        res = f"""
<div id='{tabname}_{self_name_id}_subdirs' class='extra-network-subdirs extra-network-subdirs-{view}'>
{subdirs_html}
</div>
<div id='{tabname}_{self_name_id}_cards' class='extra-network-{view}'>
<div id="total_count" style="display: none">{self.get_items_count()}</div>
{items_html}
</div>
"""

        if return_callbacks:
            start_upload_callback = f"""
                var plus_icon = document.querySelector("#{plus_sign_elem_id}");
                plus_icon.style.display = "none";
                var loading_icon = document.querySelector("#{loading_sign_elem_id}");
                loading_icon.style.display = "inline-block";
            """
            finish_upload_callback = f"""
                var plus_icon = document.querySelector("#{plus_sign_elem_id}");
                plus_icon.style.display = "inline-block";
                var loading_icon = document.querySelector("#{loading_sign_elem_id}");
                loading_icon.style.display = "none";
            """
            return res, start_upload_callback, finish_upload_callback
        return res

    def list_items(self):
        raise NotImplementedError()

    def get_items_count(self):
        raise NotImplementedError()

    def allowed_directories_for_previews(self):
        return []

    def find_preview(self, path):
        """
        Find a preview PNG for a given path (without extension) and call link_preview on it.
        """

        preview_extensions = ["png", "jpg", "webp"]
        if shared.opts.samples_format not in preview_extensions:
            preview_extensions.append(shared.opts.samples_format)

        potential_files = sum([[path + "." + ext, path + ".preview." + ext] for ext in preview_extensions], [])

        for file in potential_files:
            if os.path.isfile(file):
                return self.link_preview(file)

        return None

    def find_description(self, path):
        """
        Find and read a description file for a given path (without extension).
        """
        for file in [f"{path}.txt", f"{path}.description.txt"]:
            try:
                with open(file, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except OSError:
                pass
        return None


def intialize():
    extra_pages.clear()


class ExtraNetworksUi:
    def __init__(self):
        self.pages = None
        self.stored_extra_pages = None

        self.button_save_preview = None
        self.preview_target_filename = None

        self.tabname = None
        self.saved_preview_url = None


def pages_in_preferred_order(pages):
    tab_order = [x.lower().strip() for x in shared.opts.ui_extra_networks_tab_reorder.split(",")]

    def tab_name_score(name):
        name = name.lower()
        for i, possible_match in enumerate(tab_order):
            if possible_match in name:
                return i

        return len(pages)

    tab_scores = {page.name: (tab_name_score(page.name), original_index) for original_index, page in enumerate(pages)}

    return sorted(pages, key=lambda x: tab_scores[x.name])


def create_ui(container, button, tabname):
    ui = ExtraNetworksUi()
    ui.pages = []
    ui.stored_extra_pages = pages_in_preferred_order(extra_pages.copy())
    ui.tabname = tabname

    with gr.Tabs(elem_id=tabname + "_extra_tabs") as tabs:
        for page in ui.stored_extra_pages:
            self_name_id = page.name.replace(" ", "_")
            with gr.Tab(label=page.title, id=self_name_id, elem_id=self_name_id) as tab:
                upload_button_id = f"{ui.tabname}_{self_name_id}_upload_button"
                button_id = f"{upload_button_id}-card"
                page_html_str, start_upload_callback, finish_upload_callback = page.create_html(
                    ui.tabname, upload_button_id, button_id, return_callbacks=True)
                page_elem = gr.HTML(page_html_str, elem_id=f"{ui.tabname}-{self_name_id}")
                # TODO: Need to handle the case where there are multiple sub dirs
                upload_destination = page.allowed_directories_for_previews()[0] \
                    if page.allowed_directories_for_previews() else "./"
                with gr.Row():
                    create_upload_button(
                        f"Upload {page.title}",
                        upload_button_id,
                        upload_destination,
                        visible=False,
                        start_uploading_call_back=start_upload_callback,
                        finish_uploading_call_back=finish_upload_callback
                    )
                tab_click_params = gr.JSON(value={"tabname": ui.tabname, "model_type": self_name_id}, visible=False)
                tab.select(fn=None, _js=f"modelTabClick", inputs=[tab_click_params], outputs=[])
                ui.pages.append(page_elem)
                with gr.Row(elem_id=f"{ui.tabname}_{self_name_id}_pagination", elem_classes="pagination"):
                     with gr.Column(scale=7):
                         gr.Button("hide", visible=False)
                     with gr.Column(elem_id=f"{ui.tabname}_{self_name_id}_upload_btn", elem_classes="pagination_upload_btn", scale=2,  min_width=220):
                        upload_btn = gr.Button(f"Add {page.title} to Workspace", variant="primary")
                        upload_btn.click(
                            fn=None,
                            _js=f"openWorkSpaceDialog('{self_name_id}')"
                        )
                    #  with gr.Column(elem_id=f"{ui.tabname}_{self_name_id}_upload_btn", elem_classes="pagination_upload_btn", scale=2,  min_width=220):
                    #     upload_btn = gr.Button(f"Upload {page.title} Model", variant="primary")
                    #     upload_btn.click(
                    #         fn=None,
                    #         _js=f'''() => {{
                    #             if (typeof register_button == "undefined") {{document.querySelector("#{upload_button_id}").click();}}
                    #             else {{document.querySelector("#{button_id}").click();}}
                    #         }}'''
                    #     )
                     with gr.Column(elem_id=f"{ui.tabname}_{self_name_id}_pagination_row", elem_classes="pagination_row",  min_width=220):
                        gr.HTML(
                            value="<div class='pageniation-info'>"
                                  f"<div class='page-prev' onclick=\"updatePage('{ui.tabname}', '{self_name_id}', 'previous')\">< Prev </div>"
                                  "<div class='page-total'><span class='current-page'>1</span><span class='separator'>/</span><span class='total-page'></span></div>"
                                  f"<div class='page-next' onclick=\"updatePage('{ui.tabname}', '{self_name_id}', 'next')\">Next ></div></div>",
                            show_label=False)

    filter = gr.Textbox('', show_label=False, elem_id=tabname + "_extra_search", placeholder="Search...", visible=False)
    button_refresh = gr.Button('Refresh', elem_id=tabname + "_extra_refresh")
    mature_level = gr.Dropdown(label="Mature Content:", elem_id=f"{tabname}_mature_level", choices=["None", "Soft", "Mature"], value="None", interactive=True)

    ui.button_save_preview = gr.Button('Save preview', elem_id=tabname + "_save_preview", visible=False)
    ui.preview_target_filename = gr.Textbox('Preview save filename', elem_id=tabname + "_preview_filename",
                                            visible=False)
    ui.saved_preview_url = gr.Textbox('', elem_id=tabname + "_preview_url", visible=False, interactive=False)
    ui.saved_preview_url.change(
        None, ui.saved_preview_url, None, _js=f"(preview_url) => {{updateTabPrivatePreviews('{ui.tabname}');}}")

    def toggle_visibility(is_visible):
        is_visible = not is_visible
        return is_visible, gr.update(visible=is_visible), gr.update(
            variant=("secondary-down" if is_visible else "secondary"))

    state_visible = gr.State(value=False)
    button.click(fn=toggle_visibility, inputs=[state_visible], outputs=[state_visible, container, button])
    refresh_params = gr.JSON(value={"tabname": ui.tabname}, visible=False)
    button_refresh.click(fn=None, _js=f"refreshModelList", inputs=[refresh_params], outputs=[])
    mature_level.change(fn=None, _js=f"changeHomeMatureLevel", inputs=[mature_level, refresh_params])
    return ui


def path_is_parent(parent_path, child_path):
    parent_path = os.path.abspath(parent_path)
    child_path = os.path.abspath(child_path)

    return child_path.startswith(parent_path)


# noinspection PyUnusedLocal
def on_preview_created(user_id: str, tab: str, model_name: str, preview_path: str):
    # used for hijack, do nothing here
    pass


def setup_ui(ui, gallery):
    def save_preview(index, images, filename, request: gr.Request):
        paths = Paths(request)
        if len(images) == 0:
            print("There is no image in gallery to save as a preview.")
            return ""

        index = int(index)
        index = 0 if index < 0 else index
        index = len(images) - 1 if index >= len(images) else index

        img_info = images[index if index >= 0 else 0]
        image = image_from_url_text(img_info)
        geninfo, items = read_info_from_image(image)

        preview_path = os.path.join(paths.model_previews_dir(), filename)
        preview_path_dir = os.path.dirname(preview_path)
        if not os.path.exists(preview_path_dir):
            os.makedirs(preview_path_dir, exist_ok=True)

        if geninfo:
            pnginfo_data = PngImagePlugin.PngInfo()
            pnginfo_data.add_text('parameters', geninfo)
            image.save(preview_path, pnginfo=pnginfo_data)
        else:
            image.save(preview_path)
        file_mtime = os.path.getmtime(preview_path)
        model_type = os.path.dirname(filename)
        base_filename = os.path.basename(filename)
        model_name = os.path.splitext(os.path.basename(filename))[0]
        user = modules.user.User.current_user(request)
        on_preview_created(user.uid, model_type, model_name, preview_path)

        return f'url("/sd_extra_networks/thumb?filename={base_filename}&model_type={model_type}&mtime={file_mtime}")'

    ui.button_save_preview.click(
        fn=save_preview,
        _js="function(x, y, z){return [selected_gallery_index(), y, z]}",
        inputs=[ui.preview_target_filename, gallery, ui.preview_target_filename],
        outputs=ui.saved_preview_url
    )
