import glob
import os.path
import urllib.parse
from pathlib import Path
from PIL import PngImagePlugin
import time

from modules import shared
from modules.images import read_info_from_image
from modules.paths import Paths
from modules.paths_internal import script_path
import gradio as gr
from fastapi import Request
import json
import html

from modules.generation_parameters_copypaste import image_from_url_text
from modules.ui_common import create_upload_button

extra_pages = []
allowed_dirs = set()
preview_search_dir = dict()


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


def get_metadata(page: str = "", item: str = ""):
    from starlette.responses import JSONResponse

    page = next(iter([x for x in extra_pages if x.name == page]), None)
    if page is None:
        return JSONResponse({})

    metadata = page.metadata.get(item)
    if metadata is None:
        return JSONResponse({})

    return JSONResponse({"metadata": metadata})


def add_pages_to_demo(app):
    app.add_api_route("/sd_extra_networks/thumb", fetch_file, methods=["GET"])
    app.add_api_route("/sd_extra_networks/metadata", get_metadata, methods=["GET"])


class ExtraNetworksPage:
    def __init__(self, title):
        self.title = title
        self.name = title.lower()
        self.card_page = shared.html("extra-networks-card.html")
        self.allow_negative_prompt = False
        self.metadata = {}

    def refresh(self, request: gr.Request):
        pass

    def link_preview(self, filename):
        model_type = self.name.replace(" ", "_")
        filename_unix = os.path.abspath(filename.replace('\\', '/'))
        if model_type not in preview_search_dir:
            preview_search_dir[model_type] = list()
        dirpath = os.path.dirname(filename_unix)
        if  dirpath and (dirpath not in preview_search_dir[model_type]):
            preview_search_dir[model_type].append(dirpath)
        return "/sd_extra_networks/thumb?filename=" + \
            urllib.parse.quote(os.path.basename(filename_unix)) + \
            "&model_type=" + model_type + "&timestamp=" + str(time.time())

    def search_terms_from_path(self, filename, possible_directories=None):
        abspath = os.path.abspath(filename)

        for parentdir in (possible_directories if possible_directories is not None else self.allowed_directories_for_previews()):
            parentdir = os.path.abspath(parentdir)
            if abspath.startswith(parentdir):
                return abspath[len(parentdir):].replace('\\', '/')

        return ""

    def create_html(self, tabname, upload_button_id, return_callbacks=False):
        view = shared.opts.extra_networks_default_view
        items_html = ''

        self.metadata = {}

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
<button class='lg secondary gradio-button custom-button{" search-all" if subdir=="" else ""}' onclick='extraNetworksSearchButton("{tabname}_extra_tabs", event)'>
{html.escape(subdir if subdir!="" else "all")}
</button>
""" for subdir in subdirs])

        for item in self.list_items():
            metadata = item.get("metadata")
            if metadata:
                self.metadata[item["name"]] = metadata

            items_html += self.create_html_for_item(item, tabname)

        self_name_id = self.name.replace(" ", "_")

        # Add a upload model button
        plus_sign_elem_id=f"{tabname}_{self_name_id}-plus-sign"
        loading_sign_elem_id=f"{tabname}_{self_name_id}-loading-sign"
        height = f"height: {shared.opts.extra_networks_card_height}px;" if shared.opts.extra_networks_card_height else ''
        width = f"width: {shared.opts.extra_networks_card_width}px;" if shared.opts.extra_networks_card_width else ''
        items_html += shared.html("extra-networks-upload-button.html").format(
            style=f"{height}{width}",
            card_clicked=f'document.querySelector("#{upload_button_id}").click()',
            plus_sign_elem_id=plus_sign_elem_id,
            loading_sign_elem_id=loading_sign_elem_id
        )

        res = f"""
<div id='{tabname}_{self_name_id}_subdirs' class='extra-network-subdirs extra-network-subdirs-{view}'>
{subdirs_html}
</div>
<div id='{tabname}_{self_name_id}_cards' class='extra-network-{view}'>
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

    def allowed_directories_for_previews(self):
        return []

    def create_html_for_item(self, item, tabname):
        preview = item.get("preview", None)

        onclick = item.get("onclick", None)
        if onclick is None:
            onclick = '"' + html.escape(f"""return cardClicked({json.dumps(tabname)}, {item["prompt"]}, {"true" if self.allow_negative_prompt else "false"})""") + '"'

        height = f"height: {shared.opts.extra_networks_card_height}px;" if shared.opts.extra_networks_card_height else ''
        width = f"width: {shared.opts.extra_networks_card_width}px;" if shared.opts.extra_networks_card_width else ''
        background_image = f"background-image: url(\"{html.escape(preview)}\");" if preview else ''
        metadata_button = ""
        metadata = item.get("metadata")
        if metadata:
            metadata_button = f"<div class='metadata-button' title='Show metadata' onclick='extraNetworksRequestMetadata(event, {json.dumps(self.name)}, {json.dumps(item['name'])})'></div>"

        model_type = self.name.replace(" ", "_")
        preview_filename = os.path.join(model_type, os.path.basename(item["local_preview"]))

        args = {
            "style": f"'{height}{width}{background_image}'",
            "prompt": item.get("prompt", None),
            "tabname": json.dumps(tabname),
            "local_preview": json.dumps(preview_filename),
            "name": item["name"],
            "description": (item.get("description") or ""),
            "card_clicked": onclick,
            "save_card_preview": '"' + html.escape(f"""return saveCardPreview(event, {json.dumps(tabname)}, {json.dumps(preview_filename)})""") + '"',
            "search_term": item.get("search_term", ""),
            "metadata_button": metadata_button,
        }

        return self.card_page.format(**args)

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

        # TODO: If generated image is not png, this will likely fail
        return self.link_preview(os.path.basename(path) + ".png")

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

    with gr.Tabs(elem_id=tabname+"_extra_tabs") as tabs:
        for page in ui.stored_extra_pages:
            with gr.Tab(page.title):

                self_name_id = page.name.replace(" ", "_")
                upload_button_id = f"{ui.tabname}_{self_name_id}_upload_button"
                page_html_str, start_upload_callback, finish_upload_callback = page.create_html(
                    ui.tabname, upload_button_id, return_callbacks=True)
                page_elem = gr.HTML(page_html_str)
                # TODO: Need to handle the case where there are multiple sub dirs
                upload_destination = page.allowed_directories_for_previews()[0] \
                    if page.allowed_directories_for_previews() else "./"
                with gr.Row():
                    create_upload_button(
                        f"Upload {page.name}",
                        upload_button_id,
                        upload_destination,
                        visible=False,
                        start_uploading_call_back=start_upload_callback,
                        finish_uploading_call_back=finish_upload_callback
                    )
                ui.pages.append(page_elem)

    filter = gr.Textbox('', show_label=False, elem_id=tabname+"_extra_search", placeholder="Search...", visible=False)
    button_refresh = gr.Button('Refresh', elem_id=tabname+"_extra_refresh")

    ui.button_save_preview = gr.Button('Save preview', elem_id=tabname+"_save_preview", visible=False)
    ui.preview_target_filename = gr.Textbox('Preview save filename', elem_id=tabname+"_preview_filename", visible=False)

    def toggle_visibility(is_visible):
        is_visible = not is_visible
        return is_visible, gr.update(visible=is_visible), gr.update(variant=("secondary-down" if is_visible else "secondary"))

    state_visible = gr.State(value=False)
    button.click(fn=toggle_visibility, inputs=[state_visible], outputs=[state_visible, container, button])

    def refresh(request: gr.Request):
        res = []

        for pg in ui.stored_extra_pages:
            pg.refresh(request)
            self_name_id = pg.name.replace(" ", "_")
            upload_button_id = f"{ui.tabname}_{self_name_id}_upload_button"
            res.append(pg.create_html(ui.tabname, upload_button_id))

        return res

    button_refresh.click(fn=refresh, inputs=[], outputs=ui.pages)

    return ui


def path_is_parent(parent_path, child_path):
    parent_path = os.path.abspath(parent_path)
    child_path = os.path.abspath(child_path)

    return child_path.startswith(parent_path)


def setup_ui(ui, gallery):
    def save_preview(index, images, filename, request: gr.Request):
        paths = Paths(request)
        if len(images) == 0:
            print("There is no image in gallery to save as a preview.")
            return [page.create_html(
                ui.tabname,
                f"{ui.tabname}_" + page.name.replace(' ', '_') + "_upload_button") for page in ui.stored_extra_pages]

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

        return [page.create_html(
            ui.tabname,
            f"{ui.tabname}_" + page.name.replace(' ', '_') + "_upload_button") for page in ui.stored_extra_pages]

    ui.button_save_preview.click(
        fn=save_preview,
        _js="function(x, y, z){return [selected_gallery_index(), y, z]}",
        inputs=[ui.preview_target_filename, gallery, ui.preview_target_filename],
        outputs=[*ui.pages]
    )

