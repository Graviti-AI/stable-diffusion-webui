import math

import modules.scripts as scripts
import gradio as gr
from PIL import Image

from modules import processing, shared, images, devices
from modules.processing import Processed, build_decoded_params_from_processing, get_function_name_from_processing
from modules.shared import opts, state
from modules.system_monitor import monitor_call_context


class Script(scripts.Script):
    def title(self):
        return "SD upscale"

    def show(self, is_img2img):
        return is_img2img

    def ui(self, is_img2img):
        tab_id = "tab_txt2img"
        function_name = "modules.txt2img.txt2img"
        if is_img2img:
            tab_id = "tab_img2img"
            function_name = "modules.img2img.img2img"
        info = gr.HTML("<p style=\"margin-bottom:0.75em\">Will upscale the image by the selected scale factor; use width and height sliders to set tile size</p>")
        overlap = gr.Slider(minimum=0, maximum=256, step=16, label='Tile overlap', value=64, elem_id=self.elem_id("overlap"))
        scale_factor = gr.Slider(minimum=1.0, maximum=4.0, step=0.05, label='Scale Factor', value=1.0, elem_id=self.elem_id("scale_factor"))
        scale_factor.change(
            None,
            inputs=[],
            outputs=[scale_factor],
            _js=f"""
                monitorMutiplier(
                    '{tab_id}',
                    '{function_name}',
                    'script.sd_upscale.step',
                    extractor = (scale_factor) => {{
                        return (scale_factor + 1) * (scale_factor + 1);
                    }})"""
        )
        upscaler_index = gr.Radio(label='Upscaler', choices=[x.name for x in shared.sd_upscalers], value=shared.sd_upscalers[0].name, type="index", elem_id=self.elem_id("upscaler_index"))

        return [info, overlap, upscaler_index, scale_factor]

    def run(self, p, _, overlap, upscaler_index, scale_factor):
        if isinstance(upscaler_index, str):
            upscaler_index = [x.name.lower() for x in shared.sd_upscalers].index(upscaler_index.lower())
        processing.fix_seed(p)
        upscaler = shared.sd_upscalers[upscaler_index]

        p.extra_generation_params["SD upscale overlap"] = overlap
        p.extra_generation_params["SD upscale upscaler"] = upscaler.name

        initial_info = None
        seed = p.seed

        init_img = p.init_images[0]
        init_img = images.flatten(init_img, opts.img2img_background_color)

        if upscaler.name != "None":
            img = upscaler.scaler.upscale(init_img, scale_factor, upscaler.data_path)
        else:
            img = init_img

        devices.torch_gc()

        grid = images.split_grid(img, tile_w=p.width, tile_h=p.height, overlap=overlap)

        batch_size = p.batch_size
        upscale_count = p.n_iter
        p.n_iter = 1
        p.do_not_save_grid = True
        p.do_not_save_samples = True

        work = []

        for _y, _h, row in grid.tiles:
            for tiledata in row:
                work.append(tiledata[2])

        batch_count = math.ceil(len(work) / batch_size)
        state.job_count = batch_count * upscale_count

        print(f"SD upscaling will process a total of {len(work)} images tiled as {len(grid.tiles[0][2])}x{len(grid.tiles)} per upscale in a total of {state.job_count} batches.")

        result_images = []
        for n in range(upscale_count):
            start_seed = seed + n
            p.seed = start_seed

            work_results = []
            for i in range(batch_count):
                p.batch_size = batch_size
                p.init_images = work[i * batch_size:(i + 1) * batch_size]

                state.job = f"Batch {i + 1 + n * batch_count} out of {state.job_count}"
                with monitor_call_context(
                        p.get_request(),
                        get_function_name_from_processing(p),
                        "script.sd_upscale.step",
                        decoded_params=build_decoded_params_from_processing(p),
                        only_available_for=["plus", "pro", "api"]):
                    processed = processing.process_images(p)

                if initial_info is None:
                    initial_info = processed.info

                p.seed = processed.seed + 1
                work_results += processed.images

            image_index = 0
            for _y, _h, row in grid.tiles:
                for tiledata in row:
                    tiledata[2] = work_results[image_index] if image_index < len(work_results) else Image.new("RGB", (p.width, p.height))
                    image_index += 1

            combined_image = images.combine_grid(grid)
            result_images.append(combined_image)

            if opts.samples_save:
                images.save_image(combined_image, p.outpath_samples, "", start_seed, p.prompt, opts.samples_format, info=initial_info, p=p)

        processed = Processed(p, result_images, seed, initial_info)

        return processed
