import functools
import os.path
import urllib.parse
from pathlib import Path
from typing import Optional, Union
from dataclasses import dataclass

from modules import shared, ui_extra_networks_user_metadata, errors, extra_networks, util
from modules.images import read_info_from_image, save_image_with_geninfo
from modules.paths import Paths
from modules.ui_common import create_upload_button, ToolButton
import gradio as gr
import json
import html
from fastapi.exceptions import HTTPException

from modules.infotext_utils import image_from_url_text

extra_pages = []
allowed_dirs = set()
default_allowed_preview_extensions = ["png", "jpg", "jpeg", "webp", "gif"]

up_down_symbol = '\u2195\ufe0f' # ↕️

@functools.cache
def allowed_preview_extensions_with_extra(extra_extensions=None):
    return set(default_allowed_preview_extensions) | set(extra_extensions or [])


def allowed_preview_extensions():
    return allowed_preview_extensions_with_extra((shared.opts.samples_format, ))


@dataclass
class ExtraNetworksItem:
    """Wrapper for dictionaries representing ExtraNetworks items."""
    item: dict


def get_tree(paths: Union[str, list[str]], items: dict[str, ExtraNetworksItem]) -> dict:
    """Recursively builds a directory tree.

    Args:
        paths: Path or list of paths to directories. These paths are treated as roots from which
            the tree will be built.
        items: A dictionary associating filepaths to an ExtraNetworksItem instance.

    Returns:
        The result directory tree.
    """
    if isinstance(paths, (str,)):
        paths = [paths]

    def _get_tree(_paths: list[str], _root: str):
        _res = {}
        for path in _paths:
            relpath = os.path.relpath(path, _root)
            if os.path.isdir(path):
                dir_items = os.listdir(path)
                # Ignore empty directories.
                if not dir_items:
                    continue
                dir_tree = _get_tree([os.path.join(path, x) for x in dir_items], _root)
                # We only want to store non-empty folders in the tree.
                if dir_tree:
                    _res[relpath] = dir_tree
            else:
                if path not in items:
                    continue
                # Add the ExtraNetworksItem to the result.
                _res[relpath] = items[path]
        return _res

    res = {}
    # Handle each root directory separately.
    # Each root WILL have a key/value at the root of the result dict though
    # the value can be an empty dict if the directory is empty. We want these
    # placeholders for empty dirs so we can inform the user later.
    for path in paths:
        root = os.path.dirname(path)
        relpath = os.path.relpath(path, root)
        # Wrap the path in a list since that is what the `_get_tree` expects.
        res[relpath] = _get_tree([path], root)
        if res[relpath]:
            # We need to pull the inner path out one for these root dirs.
            res[relpath] = res[relpath][relpath]

    return res

def register_page(page):
    """registers extra networks page for the UI; recommend doing it in on_before_ui() callback for extensions"""

    extra_pages.append(page)
    allowed_dirs.clear()
    allowed_dirs.update(set(sum([x.allowed_directories_for_previews() for x in extra_pages], [])))


def fetch_file(filename: str = ""):
    from starlette.responses import FileResponse

    if not os.path.isfile(filename):
        raise HTTPException(status_code=404, detail="File not found")

    if not any(Path(x).absolute() in Path(filename).absolute().parents for x in allowed_dirs):
        raise ValueError(f"File cannot be fetched: {filename}. Must be in one of directories registered by extra pages.")

    ext = os.path.splitext(filename)[1].lower()[1:]
    if ext not in allowed_preview_extensions():
        raise ValueError(f"File cannot be fetched: {filename}. Extensions allowed: {allowed_preview_extensions()}.")

    # would profit from returning 304
    return FileResponse(filename, headers={"Accept-Ranges": "bytes"})


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
    from starlette.responses import JSONResponse

    page = next(iter([x for x in extra_pages if x.name == page]), None)
    if page is None:
        return JSONResponse({})

    metadata = page.metadata.get(item)
    if metadata is None:
        return JSONResponse({})

    return JSONResponse({"metadata": json.dumps(metadata, indent=4, ensure_ascii=False)})


def get_single_card(page: str = "", tabname: str = "", name: str = ""):
    from starlette.responses import JSONResponse

    page = next(iter([x for x in extra_pages if x.name == page]), None)

    try:
        item = page.create_item(name, enable_filter=False)
        page.items[name] = item
    except Exception as e:
        errors.display(e, "creating item for extra network")
        item = page.items.get(name)

    page.read_user_metadata(item, use_cache=False)
    item_html = page.create_item_html(tabname, item, shared.html("extra-networks-card.html"))

    return JSONResponse({"html": item_html})


def add_pages_to_demo(app):
    app.add_api_route("/sd_extra_networks/thumb", fetch_file, methods=["GET"])
    app.add_api_route("/sd_extra_networks/metadata", get_metadata, methods=["GET"])
    app.add_api_route("/sd_extra_networks/get-single-card", get_single_card, methods=["GET"])


def quote_js(s):
    s = s.replace('\\', '\\\\')
    s = s.replace('"', '\\"')
    return f'"{s}"'

class ExtraNetworksPage:
    def __init__(self, title):
        self.title = title
        self.name = title.lower()
        # This is the actual name of the extra networks tab (not txt2img/img2img).
        self.extra_networks_tabname = self.name.replace(" ", "_")
        self.allow_prompt = True
        self.allow_negative_prompt = False
        self.metadata = {}
        self.items = {}
        self.lister = util.MassFileLister()
        # HTML Templates
        self.pane_tpl = shared.html("extra-networks-pane.html")
        self.card_tpl = shared.html("extra-networks-card.html")
        self.btn_tree_tpl = shared.html("extra-networks-tree-button.html")
        self.btn_copy_path_tpl = shared.html("extra-networks-copy-path-button.html")
        self.btn_metadata_tpl = shared.html("extra-networks-metadata-button.html")
        self.btn_edit_item_tpl = shared.html("extra-networks-edit-item-button.html")
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

    def read_user_metadata(self, item, use_cache=True):
        filename = item.get("filename", None)
        metadata = extra_networks.get_user_metadata(filename, lister=self.lister if use_cache else None)

        desc = metadata.get("description", None)
        if desc is not None:
            item["description"] = desc

        item["user_metadata"] = metadata

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
        for parentdir in (possible_directories if possible_directories is not None else self.allowed_directories_for_previews()):
            parentdir = os.path.dirname(os.path.abspath(parentdir))
            if abspath.startswith(parentdir):
                return os.path.relpath(abspath, parentdir)

        return ""

    def create_item_html(
        self,
        tabname: str,
        item: dict,
        template: Optional[str] = None,
    ) -> Union[str, dict]:
        """Generates HTML for a single ExtraNetworks Item.

        Args:
            tabname: The name of the active tab.
            item: Dictionary containing item information.
            template: Optional template string to use.

        Returns:
            If a template is passed: HTML string generated for this item.
                Can be empty if the item is not meant to be shown.
            If no template is passed: A dictionary containing the generated item's attributes.
        """
        preview = item.get("preview", None)
        style_height = f"height: {shared.opts.extra_networks_card_height}px;" if shared.opts.extra_networks_card_height else ''
        style_width = f"width: {shared.opts.extra_networks_card_width}px;" if shared.opts.extra_networks_card_width else ''
        style_font_size = f"font-size: {shared.opts.extra_networks_card_text_scale*100}%;"
        card_style = style_height + style_width + style_font_size
        background_image = f'<img src="{html.escape(preview)}" class="preview" loading="lazy">' if preview else ''

        onclick = item.get("onclick", None)
        if onclick is None:
            # Don't quote prompt/neg_prompt since they are stored as js strings already.
            onclick_js_tpl = "cardClicked('{tabname}', {prompt}, {neg_prompt}, {allow_neg});"
            onclick = onclick_js_tpl.format(
                **{
                    "tabname": tabname,
                    "prompt": item["prompt"],
                    "neg_prompt": item.get("negative_prompt", "''"),
                    "allow_neg": str(self.allow_negative_prompt).lower(),
                }
            )
            onclick = html.escape(onclick)

        btn_copy_path = self.btn_copy_path_tpl.format(**{"filename": item["filename"]})
        btn_metadata = ""
        metadata = item.get("metadata")
        if metadata:
            btn_metadata = self.btn_metadata_tpl.format(
                **{
                    "extra_networks_tabname": self.extra_networks_tabname,
                    "name": html.escape(item["name"]),
                }
            )
        btn_edit_item = self.btn_edit_item_tpl.format(
            **{
                "tabname": tabname,
                "extra_networks_tabname": self.extra_networks_tabname,
                "name": html.escape(item["name"]),
            }
        )

        local_path = ""
        filename = item.get("filename", "")
        for reldir in self.allowed_directories_for_previews():
            absdir = os.path.abspath(reldir)

            if filename.startswith(absdir):
                local_path = filename[len(absdir):]

        # if this is true, the item must not be shown in the default view, and must instead only be
        # shown when searching for it
        if shared.opts.extra_networks_hidden_models == "Always":
            search_only = False
        else:
            search_only = "/." in local_path or "\\." in local_path

        if search_only and shared.opts.extra_networks_hidden_models == "Never":
            return ""

        sort_keys = " ".join(
            [
                f'data-sort-{k}="{html.escape(str(v))}"'
                for k, v in item.get("sort_keys", {}).items()
            ]
        ).strip()

        search_terms_html = ""
        search_term_template = "<span class='hidden {class}'>{search_term}</span>"
        for search_term in item.get("search_terms", []):
            search_terms_html += search_term_template.format(
                **{
                    "class": f"search_terms{' search_only' if search_only else ''}",
                    "search_term": search_term,
                }
            )

        description = (item.get("description", "") or "" if shared.opts.extra_networks_card_show_desc else "")
        if not shared.opts.extra_networks_card_description_is_html:
            description = html.escape(description)

        # Some items here might not be used depending on HTML template used.
        args = {
            "background_image": background_image,
            "card_clicked": onclick,
            "copy_path_button": btn_copy_path,
            "description": description,
            "edit_button": btn_edit_item,
            "local_preview": quote_js(item["local_preview"]),
            "metadata_button": btn_metadata,
            "name": html.escape(item["name"]),
            "prompt": item.get("prompt", None),
            "save_card_preview": html.escape(f"return saveCardPreview(event, '{tabname}', '{item['local_preview']}');"),
            "search_only": " search_only" if search_only else "",
            "search_terms": search_terms_html,
            "sort_keys": sort_keys,
            "style": card_style,
            "tabname": tabname,
            "extra_networks_tabname": self.extra_networks_tabname,
        }

        if template:
            return template.format(**args)
        else:
            return args

    def create_tree_dir_item_html(
        self,
        tabname: str,
        dir_path: str,
        content: Optional[str] = None,
    ) -> Optional[str]:
        """Generates HTML for a directory item in the tree.

        The generated HTML is of the format:
        ```html
        <li class="tree-list-item tree-list-item--has-subitem">
            <div class="tree-list-content tree-list-content-dir"></div>
            <ul class="tree-list tree-list--subgroup">
                {content}
            </ul>
        </li>
        ```

        Args:
            tabname: The name of the active tab.
            dir_path: Path to the directory for this item.
            content: Optional HTML string that will be wrapped by this <ul>.

        Returns:
            HTML formatted string.
        """
        if not content:
            return None

        btn = self.btn_tree_tpl.format(
            **{
                "search_terms": "",
                "subclass": "tree-list-content-dir",
                "tabname": tabname,
                "extra_networks_tabname": self.extra_networks_tabname,
                "onclick_extra": "",
                "data_path": dir_path,
                "data_hash": "",
                "action_list_item_action_leading": "<i class='tree-list-item-action-chevron'></i>",
                "action_list_item_visual_leading": "🗀",
                "action_list_item_label": os.path.basename(dir_path),
                "action_list_item_visual_trailing": "",
                "action_list_item_action_trailing": "",
            }
        )
        ul = f"<ul class='tree-list tree-list--subgroup' hidden>{content}</ul>"
        return (
            "<li class='tree-list-item tree-list-item--has-subitem' data-tree-entry-type='dir'>"
            f"{btn}{ul}"
            "</li>"
        )

    def create_tree_file_item_html(self, tabname: str, file_path: str, item: dict) -> str:
        """Generates HTML for a file item in the tree.

        The generated HTML is of the format:
        ```html
        <li class="tree-list-item tree-list-item--subitem">
            <span data-filterable-item-text hidden></span>
            <div class="tree-list-content tree-list-content-file"></div>
        </li>
        ```

        Args:
            tabname: The name of the active tab.
            file_path: The path to the file for this item.
            item: Dictionary containing the item information.

        Returns:
            HTML formatted string.
        """
        item_html_args = self.create_item_html(tabname, item)
        action_buttons = "".join(
            [
                item_html_args["copy_path_button"],
                item_html_args["metadata_button"],
                item_html_args["edit_button"],
            ]
        )
        action_buttons = f"<div class=\"button-row\">{action_buttons}</div>"
        btn = self.btn_tree_tpl.format(
            **{
                "search_terms": "",
                "subclass": "tree-list-content-file",
                "tabname": tabname,
                "extra_networks_tabname": self.extra_networks_tabname,
                "onclick_extra": item_html_args["card_clicked"],
                "data_path": file_path,
                "data_hash": item["shorthash"],
                "action_list_item_action_leading": "<i class='tree-list-item-action-chevron'></i>",
                "action_list_item_visual_leading": "🗎",
                "action_list_item_label": item["name"],
                "action_list_item_visual_trailing": "",
                "action_list_item_action_trailing": action_buttons,
            }
        )
        return (
            "<li class='tree-list-item tree-list-item--subitem' data-tree-entry-type='file'>"
            f"{btn}"
            "</li>"
        )

    def create_tree_view_html(self, tabname: str) -> str:
        """Generates HTML for displaying folders in a tree view.

        Args:
            tabname: The name of the active tab.

        Returns:
            HTML string generated for this tree view.
        """
        res = ""

        # Setup the tree dictionary.
        roots = self.allowed_directories_for_previews()
        tree_items = {v["filename"]: ExtraNetworksItem(v) for v in self.items.values()}
        tree = get_tree([os.path.abspath(x) for x in roots], items=tree_items)

        if not tree:
            return res

        def _build_tree(data: Optional[dict[str, ExtraNetworksItem]] = None) -> Optional[str]:
            """Recursively builds HTML for a tree.

            Args:
                data: Dictionary representing a directory tree. Can be NoneType.
                    Data keys should be absolute paths from the root and values
                    should be subdirectory trees or an ExtraNetworksItem.

            Returns:
                If data is not None: HTML string
                Else: None
            """
            if not data:
                return None

            # Lists for storing <li> items html for directories and files separately.
            _dir_li = []
            _file_li = []

            for k, v in sorted(data.items(), key=lambda x: shared.natural_sort_key(x[0])):
                if isinstance(v, (ExtraNetworksItem,)):
                    _file_li.append(self.create_tree_file_item_html(tabname, k, v.item))
                else:
                    _dir_li.append(self.create_tree_dir_item_html(tabname, k, _build_tree(v)))

            # Directories should always be displayed before files so we order them here.
            return "".join(_dir_li) + "".join(_file_li)

        # Add each root directory to the tree.
        for k, v in sorted(tree.items(), key=lambda x: shared.natural_sort_key(x[0])):
            item_html = self.create_tree_dir_item_html(tabname, k, _build_tree(v))
            # Only add non-empty entries to the tree.
            if item_html is not None:
                res += item_html

        return f"<ul class='tree-list tree-list--tree'>{res}</ul>"

    def create_card_view_html(self, tabname: str, *, none_message) -> str:
        """Generates HTML for the network Card View section for a tab.

        This HTML goes into the `extra-networks-pane.html` <div> with
        `id='{tabname}_{extra_networks_tabname}_cards`.

        Args:
            tabname: The name of the active tab.
            none_message: HTML text to show when there are no cards.

        Returns:
            HTML formatted string.
        """
        res = ""
        for item in self.items.values():
            res += self.create_item_html(tabname, item, self.card_tpl)

        if res == "":
            dirs = "".join([f"<li>{x}</li>" for x in self.allowed_directories_for_previews()])
            res = none_message or shared.html("extra-networks-no-cards.html").format(dirs=dirs)

        return res

    def create_html(self, tabname, upload_button_id, button_id=None, return_callbacks=False):
        assert shared.opts is not None, "shared.opts is not initialized"
        items_html = ''

        subdirs = {}
        for parentdir in [os.path.abspath(x) for x in self.allowed_directories_for_previews()]:
            for root, dirs, _ in sorted(os.walk(parentdir, followlinks=True), key=lambda x: shared.natural_sort_key(x[0])):
                for dirname in sorted(dirs, key=shared.natural_sort_key):
                    x = os.path.join(root, dirname)

                    if not os.path.isdir(x):
                        continue

                    subdir = os.path.abspath(x)[len(parentdir):].replace("\\", "/")

                    if shared.opts.extra_networks_dir_button_function:
                        if not subdir.startswith("/"):
                            subdir = "/" + subdir
                    else:
                        while subdir.startswith("/"):
                            subdir = subdir[1:]

                    is_empty = len(os.listdir(x)) == 0
                    if not is_empty and not subdir.endswith("/"):
                        subdir = subdir + "/"

                    if ("/." in subdir or subdir.startswith(".")) and not shared.opts.extra_networks_show_hidden_directories:
                        continue

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
            is_public="true",
            tabname=tabname,
            card_clicked=f'if (typeof register_button == "undefined") {{document.querySelector("#{upload_button_id}").click();}}',
            dashboard_title=f'{self.title} files only.{dashboard_title_hint}',
            model_size=model_size,
            plus_sign_elem_id=plus_sign_elem_id,
            loading_sign_elem_id=loading_sign_elem_id,
            name=f'Upload {self.title} Models',
            add_model_button_id=f"{tabname}_{self_name_id}_add_model-to-workspace",
        )
        items_html += shared.html("extra-networks-upload-button.html").format(
            button_id=f"{button_id}-private",
            style=f"{height}{width}",
            model_type=self_name_id,
            is_public="false",
            tabname=tabname,
            card_clicked=f'if (typeof register_button == "undefined") {{document.querySelector("#{upload_button_id}").click();}}',
            dashboard_title=f'{self.title} files only.{dashboard_title_hint}',
            model_size=model_size,
            plus_sign_elem_id=plus_sign_elem_id,
            loading_sign_elem_id=loading_sign_elem_id,
            name=f'Upload {self.title} Models',
            add_model_button_id=f"{tabname}_{self_name_id}_add_model-to-workspace-private",
        )

        res = f"""
<div id='{tabname}_{self_name_id}_subdirs' class='extra-network-subdirs extra-network-subdirs-cards'>
{subdirs_html}
</div>
<div id='{tabname}_{self_name_id}_cards' class='gallery-cards extra-network-pane'>
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

    def create_item(self, name, index=None):
        raise NotImplementedError()

    def list_items(self):
        raise NotImplementedError()

    def get_items_count(self):
        raise NotImplementedError()

    def allowed_directories_for_previews(self):
        return []

    def get_sort_keys(self, path):
        """
        List of default keys used for sorting in the UI.
        """
        pth = Path(path)
        mtime, ctime = self.lister.mctime(path)
        return {
            "date_created": int(mtime),
            "date_modified": int(ctime),
            "name": pth.name.lower(),
            "path": str(pth).lower(),
        }

    def find_preview(self, path):
        """
        Find a preview PNG for a given path (without extension) and call link_preview on it.
        """

        potential_files = sum([[f"{path}.{ext}", f"{path}.preview.{ext}"] for ext in allowed_preview_extensions()], [])

        for file in potential_files:
            if self.lister.exists(file):
                return self.link_preview(file)

        return None

    def find_description(self, path):
        """
        Find and read a description file for a given path (without extension).
        """
        for file in [f"{path}.txt", f"{path}.description.txt"]:
            if not self.lister.exists(file):
                continue

            try:
                with open(file, "r", encoding="utf-8", errors="replace") as f:
                    return f.read()
            except OSError:
                pass
        return None

    def create_user_metadata_editor(self, ui, tabname):
        return ui_extra_networks_user_metadata.UserMetadataEditor(ui, tabname, self)


def initialize():
    extra_pages.clear()


def register_default_pages():
    from modules.ui_extra_networks_textual_inversion import ExtraNetworksPageTextualInversion
    from modules.ui_extra_networks_hypernets import ExtraNetworksPageHypernetworks
    from modules.ui_extra_networks_checkpoints import ExtraNetworksPageCheckpoints
    register_page(ExtraNetworksPageCheckpoints())
    register_page(ExtraNetworksPageTextualInversion())
    register_page(ExtraNetworksPageHypernetworks())


class ExtraNetworksUi:
    def __init__(self):
        self.pages = None
        """gradio HTML components related to extra networks' pages"""

        self.page_contents = None
        """HTML content of the above; empty initially, filled when extra pages have to be shown"""

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
    ui.pages_contents = []
    ui.user_metadata_editors = []
    ui.stored_extra_pages = pages_in_preferred_order(extra_pages.copy())
    ui.tabname = tabname

    related_tabs = []
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
                editor = page.create_user_metadata_editor(ui, tabname)
                editor.create_ui()
                ui.user_metadata_editors.append(editor)

                #related_tabs.append(tab)

                with gr.Row(elem_id=f"{ui.tabname}_{self_name_id}_pagination", elem_classes="pagination"):
                     with gr.Column(scale=7):
                         gr.Button("hide", visible=False)
                     with gr.Column(elem_id=f"{ui.tabname}_{self_name_id}_upload_btn", elem_classes="pagination_upload_btn", scale=2,  min_width=220):
                        upload_btn = gr.Button(f"Add {page.title} to Workspace", variant="primary")
                        upload_btn.click(
                            fn=None,
                            _js=f"() => {{openWorkSpaceDialog('{self_name_id}');}}"
                        )

                     with gr.Column(elem_id=f"{ui.tabname}_{self_name_id}_pagination_row", elem_classes="pagination_row",  min_width=220):
                        gr.HTML(
                            value="<div class='pageniation-info'>"
                                  f"<div class='page-prev' onclick=\"updatePage('{ui.tabname}', '{self_name_id}', 'previous')\">< Prev </div>"
                                  "<div class='page-total'><span class='current-page'>1</span><span class='separator'>/</span><span class='total-page'></span></div>"
                                  f"<div class='page-next' onclick=\"updatePage('{ui.tabname}', '{self_name_id}', 'next')\">Next ></div></div>",
                            show_label=False)

    filter = gr.Textbox('', show_label=False, elem_id=tabname + "_extra_search", placeholder="Search...", visible=False)
    button_refresh = gr.Button('Refresh', elem_id=tabname + "_extra_refresh")
    mature_level = gr.Dropdown(label="Mature level", elem_id=f"{tabname}_mature_level", choices=["None", "Soft", "Mature"], value="None", interactive=True)

    # TODO: Sort function added by upstream and may not work
    gr.Dropdown(choices=['Default Sort', 'Date Created', 'Date Modified', 'Name'], value='Default Sort', elem_id=tabname+"_extra_sort", multiselect=False, visible=False, show_label=False, interactive=True)
    ToolButton(up_down_symbol, elem_id=tabname+"_extra_sortorder")

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

    button.click(fn=toggle_visibility, inputs=[state_visible], outputs=[state_visible, container, button], show_progress=False)
    refresh_params = gr.JSON(value={"tabname": ui.tabname}, visible=False)
    button_refresh.click(fn=None, _js=f"refreshModelList", inputs=[refresh_params], outputs=[])
    mature_level.change(fn=None, _js=f"changeHomeMatureLevel", inputs=[mature_level, refresh_params])
    return ui

def path_is_parent(parent_path, child_path):
    parent_path = os.path.abspath(parent_path)
    child_path = os.path.abspath(child_path)

    return child_path.startswith(parent_path)


def setup_ui(ui, gallery):
    def save_preview(index, images, filename, request: gr.Request):
        # this function is here for backwards compatibility and likely will be removed soon

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
