import json
import csv
import html
import os
import platform
import sys
import shutil
import time

import gradio as gr
import subprocess as sp

from fastapi import FastAPI, HTTPException
from starlette.responses import FileResponse

from modules import call_queue, shared, hashes
from modules.generation_parameters_copypaste import image_from_url_text
from modules.paths import Paths
from modules.paths_internal import script_path
import modules.images
import modules.user

folder_symbol = '\U0001f4c2'  # 📂


def update_generation_info(generation_info, html_info, img_index):
    try:
        generation_info = json.loads(generation_info)
        if img_index < 0 or img_index >= len(generation_info["infotexts"]):
            return html_info, gr.update()
        return plaintext_to_html(generation_info["infotexts"][img_index]), gr.update()
    except Exception:
        pass
    # if the json parse or anything else fails, just return the old html_info
    return html_info, gr.update()


def plaintext_to_html(text):
    text = "<p>" + "<br>\n".join([f"{html.escape(x)}" for x in text.split('\n')]) + "</p>"
    return text


def save_files(request: gr.Request, js_data, images, do_make_zip, index):
    filenames = []
    fullfns = []

    #quick dictionary to class object conversion. Its necessary due apply_filename_pattern requiring it
    class MyObject:
        def __init__(self, d=None):
            if d is not None:
                for key, value in d.items():
                    setattr(self, key, value)

    data = json.loads(js_data)

    p = MyObject(data)
    save_to = Paths(request).save_dir()
    save_to_dirs = shared.opts.use_save_to_dirs_for_ui
    extension: str = shared.opts.samples_format
    start_index = 0

    if index > -1 and shared.opts.save_selected_only and (index >= data["index_of_first_image"]):  # ensures we are looking at a specific non-grid picture, and we have save_selected_only

        images = [images[index]]
        start_index = index

    with open(os.path.join(save_to, "log.csv"), "a", encoding="utf8", newline='') as file:
        at_start = file.tell() == 0
        writer = csv.writer(file)
        if at_start:
            writer.writerow(["prompt", "seed", "width", "height", "sampler", "cfgs", "steps", "filename", "negative_prompt"])

        for image_index, filedata in enumerate(images, start_index):
            image = image_from_url_text(filedata)

            is_grid = image_index < p.index_of_first_image
            i = 0 if is_grid else (image_index - p.index_of_first_image)

            fullfn, txt_fullfn = modules.images.save_image(image, save_to, "", seed=p.all_seeds[i], prompt=p.all_prompts[i], extension=extension, info=p.infotexts[image_index], grid=is_grid, p=p, save_to_dirs=save_to_dirs)

            filename = os.path.relpath(fullfn, save_to)
            filenames.append(filename)
            fullfns.append(fullfn)
            if txt_fullfn:
                filenames.append(os.path.basename(txt_fullfn))
                fullfns.append(txt_fullfn)

        writer.writerow([data["prompt"], data["seed"], data["width"], data["height"], data["sampler_name"], data["cfg_scale"], data["steps"], filenames[0], data["negative_prompt"]])

    # Make Zip
    if do_make_zip:
        zip_filepath = os.path.join(save_to, "images.zip")

        from zipfile import ZipFile
        with ZipFile(zip_filepath, "w") as zip_file:
            for i in range(len(fullfns)):
                with open(fullfns[i], mode="rb") as f:
                    zip_file.writestr(filenames[i], f.read())
        fullfns.insert(0, zip_filepath)

    return gr.File.update(value=fullfns, visible=True), plaintext_to_html(f"Saved: {filenames[0]}")


def create_output_panel(tabname, outdir):
    from modules import shared
    import modules.generation_parameters_copypaste as parameters_copypaste

    def open_folder(f):
        if not os.path.exists(f):
            print(f'Folder "{f}" does not exist. After you create an image, the folder will be created.')
            return
        elif not os.path.isdir(f):
            print(f"""
WARNING
An open_folder request was made with an argument that is not a folder.
This could be an error or a malicious attempt to run code on your computer.
Requested path was: {f}
""", file=sys.stderr)
            return

        if not shared.cmd_opts.hide_ui_dir_config:
            path = os.path.normpath(f)
            if platform.system() == "Windows":
                os.startfile(path)
            elif platform.system() == "Darwin":
                sp.Popen(["open", path])
            elif "microsoft-standard-WSL2" in platform.uname().release:
                sp.Popen(["wsl-open", path])
            else:
                sp.Popen(["xdg-open", path])

    with gr.Column(variant='panel', elem_id=f"{tabname}_results"):
        with gr.Group(elem_id=f"{tabname}_gallery_container"):
            result_gallery = gr.Gallery(label='Output', show_label=False, elem_id=f"{tabname}_gallery").style(grid=4)

        generation_info = None
        with gr.Column():
            with gr.Row(elem_id=f"image_buttons_{tabname}", elem_classes="image-buttons"):
                # open_folder_button = gr.Button(folder_symbol, visible=not shared.cmd_opts.hide_ui_dir_config)

                if tabname != "extras":
                    save = gr.Button('Save', elem_id=f'save_{tabname}')
                    save_zip = gr.Button('Zip', elem_id=f'save_zip_{tabname}')

                buttons = parameters_copypaste.create_buttons(["img2img", "inpaint", "extras"])

            def on_open_folder(request: gr.Request):
                open_folder(Paths(request).outdir() or outdir)

            # open_folder_button.click(
            #     fn=on_open_folder,
            #     inputs=[],
            #     outputs=[],
            # )

            if tabname != "extras":
                download_files = gr.File(None, file_count="multiple", interactive=False, show_label=False, visible=False, elem_id=f'download_files_{tabname}')

                with gr.Group():
                    html_info = gr.HTML(elem_id=f'html_info_{tabname}', elem_classes="infotext")
                    html_log = gr.HTML(elem_id=f'html_log_{tabname}')

                    generation_info = gr.Textbox(visible=False, elem_id=f'generation_info_{tabname}')
                    if tabname == 'txt2img' or tabname == 'img2img':
                        generation_info_button = gr.Button(visible=False, elem_id=f"{tabname}_generation_info_button")
                        generation_info_button.click(
                            fn=update_generation_info,
                            _js="function(x, y, z){ return [x, y, selected_gallery_index()] }",
                            inputs=[generation_info, html_info, html_info],
                            outputs=[html_info, html_info],
                            show_progress=False,
                        )

                    save.click(
                        fn=call_queue.wrap_gradio_call(save_files),
                        _js="(x, y, z, w) => [x, y, false, selected_gallery_index()]",
                        inputs=[
                            generation_info,
                            result_gallery,
                            html_info,
                            html_info,
                        ],
                        outputs=[
                            download_files,
                            html_log,
                        ],
                        show_progress=False,
                    )

                    save_zip.click(
                        fn=call_queue.wrap_gradio_call(save_files),
                        _js="(x, y, z, w) => [x, y, true, selected_gallery_index()]",
                        inputs=[
                            generation_info,
                            result_gallery,
                            html_info,
                            html_info,
                        ],
                        outputs=[
                            download_files,
                            html_log,
                        ]
                    )

            else:
                html_info_x = gr.HTML(elem_id=f'html_info_x_{tabname}')
                html_info = gr.HTML(elem_id=f'html_info_{tabname}', elem_classes="infotext")
                html_log = gr.HTML(elem_id=f'html_log_{tabname}')

            paste_field_names = []
            if tabname == "txt2img":
                paste_field_names = modules.scripts.scripts_txt2img.paste_field_names
            elif tabname == "img2img":
                paste_field_names = modules.scripts.scripts_img2img.paste_field_names

            for paste_tabname, paste_button in buttons.items():
                parameters_copypaste.register_paste_params_button(parameters_copypaste.ParamBinding(
                    paste_button=paste_button, tabname=paste_tabname, source_tabname="txt2img" if tabname == "txt2img" else None, source_image_component=result_gallery,
                    paste_field_names=paste_field_names
                ))

            return result_gallery, generation_info if tabname != "extras" else html_info_x, html_info, html_log


def create_upload_button(
        label, elem_id, destination_dir,
        model_tracking_csv="models.csv", button_style="", visible=True,
        start_uploading_call_back="", finish_uploading_call_back=""):

    model_list_csv_path = os.path.join(destination_dir, model_tracking_csv)

    def verify_model_existence(hash_str):
        if os.path.exists(model_list_csv_path):
            with open(model_list_csv_path) as csvfile:
                modelreader = csv.reader(csvfile, delimiter=',')
                for file_hash_str, file_name, user_id, timestamp_s in modelreader:
                    if hash_str == file_hash_str:
                        return os.path.basename(file_name)
        return hash_str

    def upload_file(file, hash_str, request: gr.Request):
        file_path = file.name
        readable_hash = hashes.calculate_sha256(file_path)
        if hash_str == readable_hash:
            new_path = shutil.move(file_path, destination_dir)
            user = modules.user.User.current_user(request)
            with open(model_list_csv_path, 'a') as csvfile:
                modelwriter = csv.writer(csvfile, delimiter=',')
                modelwriter.writerow([hash_str, new_path, user.uid, time.time()])
            return os.path.basename(new_path)
        return readable_hash
    hash_str_id = elem_id+'-hash-str'
    hash_str = gr.Textbox(label='hash str', elem_id=hash_str_id, visible=False)
    existing_filepath = gr.Textbox(label='existing filepath', visible=False)
    uploaded_filepath = gr.Textbox(label='uploaded filepath', visible=False)
    button_id = elem_id
    hidden_button_id = "hidden-button-" + elem_id
    upload_button_id = "hidden-upload-button-" + elem_id
    button = gr.Button(label, elem_id=button_id, variant="primary", visible=visible)
    if button_style:
        gr.HTML("""
        <style>
        #{button_id} {{
            {button_style};
        }}
        <\\style>
        """.format(button_id=button_id, button_style=button_style), visible=False)
    button.style(full_width=False)

    compute_hash_js = """
        () => {{
            const upload_button = document.querySelector(
                "#{upload_button_id}");
            var input_box = upload_button.previousElementSibling;
            var extra_input = input_box.cloneNode();
            extra_input.id = "input-for-hash-{elem_id}";

            extra_input.onchange = async (e) => {{
                const target = e.target;
                if (!target.files || target.files.length == 0) return;

                notifier.info('Start to upload model.');
                var button = document.querySelector("#{button_id}");
                button.disabled = true;
                {start_uploading_call_back}

                input_box.files = target.files;
                const hash_str = await hashFile(input_box.files[0]);
                const checkpoint_hash_str = document.querySelector("#{hash_str_id} > label > textarea");
                checkpoint_hash_str.value = hash_str;
                const event = new Event("input");
                checkpoint_hash_str.dispatchEvent(event);
                const hidden_button = document.querySelector(
                    "#{hidden_button_id}");
                hidden_button.click();
            }}
        extra_input.click();
        }}
    """.format(
        upload_button_id=upload_button_id,
        elem_id=elem_id,
        button_id=button_id,
        start_uploading_call_back=start_uploading_call_back,
        hash_str_id=hash_str_id,
        hidden_button_id=hidden_button_id)
    button.click(None, None, None, _js=compute_hash_js)
    hidden_button = gr.Button("Verify hash", elem_id=hidden_button_id, visible=False)
    hidden_button.click(verify_model_existence, hash_str, existing_filepath, api_name="check_hash")
    upload_finish_js = """
        notifier.success('Model uploaded. Use the refresh button to load it.');
        var button = document.querySelector("#{button_id}");
        button.disabled = false;
        {finish_uploading_call_back}
    """.format(
        button_id=button_id,
        finish_uploading_call_back=finish_uploading_call_back)
    existing_filepath.change(None, [hash_str, existing_filepath], None, _js="""
        (hash_str, filepath) => {{
            if (hash_str == filepath) {{
                const upload_button = document.querySelector(
                    "#{upload_button_id}");
                var input_box = upload_button.previousElementSibling;
                const event = new Event("change");
                input_box.dispatchEvent(event);
            }} else {{
                {upload_finish_js}
            }}
        }}
    """.format(upload_button_id=upload_button_id, upload_finish_js=upload_finish_js))
    upload_button = gr.UploadButton(
        label="Upload a file",
        elem_id=upload_button_id,
        file_types=[".ckpt", ".safetensors", ".bin", ".pt"],
        visible=False
    )
    upload_button.upload(
        fn=upload_file,
        inputs=[upload_button, hash_str],
        outputs=uploaded_filepath
    )
    notify_upload_finished_js = """
        () => {{
            {upload_finish_js}
        }}""".format(
            upload_finish_js=upload_finish_js)
    uploaded_filepath.change(None, None, None, _js=notify_upload_finished_js)
    return button


def create_browse_model_button(label, elem_id, button_style="", visible=True):
    button = gr.Button(label, elem_id=elem_id, variant="secondary", visible=visible)
    button.click(None, list(), list(), _js="browseModels")
    if button_style:
        gr.HTML("""
        <style>
        #{button_id} {{
            {button_style};
        }}
        <\\style>
        """.format(button_id=elem_id, button_style=button_style), visible=False)
    button.style(full_width=False)


def get_static_files(filepath: str):
    full_path = os.path.join(script_path, "static", filepath)
    # Make sure the path is in static folder
    full_path = os.path.abspath(full_path)
    if not os.path.exists(full_path) or os.path.abspath(os.path.join(script_path, "static")) not in full_path:
        raise HTTPException(status_code=404, detail=f"{filepath} not found")

    return FileResponse(full_path)


def add_static_filedir_to_demo(app: FastAPI, route="public"):
    app.add_api_route(f"/" + route + "/{filepath:path}", get_static_files, methods=["GET"])
