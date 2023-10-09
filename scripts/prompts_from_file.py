import copy
import random
import shlex

import modules.scripts as scripts
import gradio as gr

from modules import sd_samplers, errors
from modules.processing import Processed, process_images, build_decoded_params_from_processing, get_function_name_from_processing
from modules.shared import state
from modules.system_monitor import monitor_call_context


def process_string_tag(tag):
    return tag


def process_int_tag(tag):
    return int(tag)


def process_float_tag(tag):
    return float(tag)


def process_boolean_tag(tag):
    return True if (tag == "true") else False


prompt_tags = {
    "sd_model": None,
    #"outpath_samples": process_string_tag,
    #"outpath_grids": process_string_tag,
    "prompt_for_display": process_string_tag,
    "prompt": process_string_tag,
    "negative_prompt": process_string_tag,
    "styles": process_string_tag,
    "seed": process_int_tag,
    "subseed_strength": process_float_tag,
    "subseed": process_int_tag,
    "seed_resize_from_h": process_int_tag,
    "seed_resize_from_w": process_int_tag,
    "sampler_index": process_int_tag,
    "sampler_name": process_string_tag,
    "batch_size": process_int_tag,
    "n_iter": process_int_tag,
    "steps": process_int_tag,
    "cfg_scale": process_float_tag,
    "width": process_int_tag,
    "height": process_int_tag,
    "restore_faces": process_boolean_tag,
    "tiling": process_boolean_tag,
    "do_not_save_samples": process_boolean_tag,
    "do_not_save_grid": process_boolean_tag
}


def cmdargs(line):
    args = shlex.split(line)
    pos = 0
    res = {}

    while pos < len(args):
        arg = args[pos]

        assert arg.startswith("--"), f'must start with "--": {arg}'
        assert pos+1 < len(args), f'missing argument for command line option {arg}'

        tag = arg[2:]

        if tag == "prompt" or tag == "negative_prompt":
            pos += 1
            prompt = args[pos]
            pos += 1
            while pos < len(args) and not args[pos].startswith("--"):
                prompt += " "
                prompt += args[pos]
                pos += 1
            res[tag] = prompt
            continue


        func = prompt_tags.get(tag, None)
        assert func, f'unknown commandline option: {arg}'

        val = args[pos+1]
        if tag == "sampler_name":
            val = sd_samplers.samplers_map.get(val.lower(), None)

        res[tag] = func(val)

        pos += 2

    return res


def load_prompt_file(file):
    if file is None:
        return None, gr.update(), gr.update(lines=7)
    else:
        lines = [x.strip() for x in file.decode('utf8', errors='ignore').split("\n")]
        return None, "\n".join(lines), gr.update(lines=7)


class Script(scripts.Script):
    def title(self):
        return "Prompts from file or textbox"

    def ui(self, is_img2img):
        checkbox_iterate = gr.Checkbox(label="Iterate seed every line", value=False, elem_id=self.elem_id("checkbox_iterate"))
        checkbox_iterate_batch = gr.Checkbox(label="Use same random seed for all lines", value=False, elem_id=self.elem_id("checkbox_iterate_batch"))

        prompt_txt = gr.Textbox(label="List of prompt inputs", lines=1, elem_id=self.elem_id("prompt_txt"))
        file = gr.File(label="Upload prompt inputs", type='binary', elem_id=self.elem_id("file"))

        file.change(fn=load_prompt_file, inputs=[file], outputs=[file, prompt_txt, prompt_txt], show_progress=False)

        # We start at one line. When the text changes, we jump to seven lines, or two lines if no \n.
        # We don't shrink back to 1, because that causes the control to ignore [enter], and it may
        # be unclear to the user that shift-enter is needed.
        prompt_txt.change(lambda tb: gr.update(lines=7) if ("\n" in tb) else gr.update(lines=2), inputs=[prompt_txt], outputs=[prompt_txt], show_progress=False)

        explanation = gr.HTML(value="""
        <div id="script_prompts_from_file_rules">
        <h1>Instructions</h1>

        <p>You can either upload a text file or write in the textbox provided. Each line will be treated as a command for generating a image. The commands should follow the Unix shell format.</p>

        <p>If the line does not start with <code>--</code>, it will be treated as a prompt. If it does start with <code>--</code>, it should be followed by a parameter and its corresponding value.</p>

        <p>If the value has white spaces in it, it should use quotes("") at the both end of the value.</p>

        <h2>Supported Parameters</h2>

        <p>Here are the supported parameters and their expected values:</p>

        <ul>
            <li><code>--prompt</code>: String value. The prompt to process.</li>
            <li><code>--negative_prompt</code>: String value. The negative prompt to process.</li>
            <li><code>--styles</code>: String value. The styles to apply. Has to define it first.</li>
            <li><code>--seed</code>: Integer value. The seed for the random number generator. -1 mean random.</li>
            <li><code>--subseed_strength</code>: Float value. The strength of the subseed.</li>
            <li><code>--subseed</code>: Integer value. The subseed for the random number generator.</li>
            <li><code>--seed_resize_from_h</code>: Integer value. The height from which the seed should be resized.</li>
            <li><code>--seed_resize_from_w</code>: Integer value. The width from which the seed should be resized.</li>
            <li><code>--sampler_name</code>: String value. The name of the sampler to use. You probably need to have quotes("") about the value.</li>
            <li><code>--batch_size</code>: Integer value. The size of the batch to process.</li>
            <li><code>--n_iter</code>: Integer value. The number of iterations to process.</li>
            <li><code>--steps</code>: Integer value. The number of steps to process.</li>
            <li><code>--cfg_scale</code>: Float value. The cfg scale.</li>
            <li><code>--width</code>: Integer value. The width of the output image.</li>
            <li><code>--height</code>: Integer value. The height of the output image.</li>
            <li><code>--restore_faces</code>: Boolean value. Whether to restore faces in the image.</li>
            <li><code>--tiling</code>: Boolean value. Whether to apply tiling to the image.</li>
        </ul>

        <p>For example, if you want to set the prompt to "sunset", the seed to 42, and the width and height to 500, you would write:</p>

        <pre style="
            background-color: #151b2b;
            height: 2em;
            vertical-align: middle;
            text-align: left;
            white-space: pre-line;
            padding-top: 0;
            padding-bottom: 0;">
        --prompt sunset --seed 42 --width 512 --height 512 --sampler_name "Eular a"
        </pre>

        <p>Each line will be a seperate generation.</p>
        </div>
        """)

        return [checkbox_iterate, checkbox_iterate_batch, prompt_txt]

    def run(self, p, checkbox_iterate, checkbox_iterate_batch, prompt_txt: str):
        lines = [x for x in (x.strip() for x in prompt_txt.splitlines()) if x]

        p.do_not_save_grid = True

        job_count = 0
        jobs = []

        for line in lines:
            if "--" in line:
                try:
                    args = cmdargs(line)
                except Exception:
                    errors.report(f"Error parsing line {line} as commandline", exc_info=True)
                    args = {"prompt": line}
            else:
                args = {"prompt": line}

            job_count += args.get("n_iter", p.n_iter)

            jobs.append(args)

        print(f"Will process {len(lines)} lines in {job_count} jobs.")
        if (checkbox_iterate or checkbox_iterate_batch) and p.seed == -1:
            p.seed = int(random.randrange(4294967294))

        state.job_count = job_count

        images = []
        all_prompts = []
        infotexts = []
        for args in jobs:
            state.job = f"{state.job_no + 1} out of {state.job_count}"

            copy_p = copy.copy(p)
            for k, v in args.items():
                setattr(copy_p, k, v)

            with monitor_call_context(
                    p.get_request(),
                    get_function_name_from_processing(copy_p),
                    "script.prompts_from_file.line",
                    decoded_params=build_decoded_params_from_processing(copy_p),
                    only_available_for=["plus", "pro", "api"]):
                proc = process_images(copy_p)
                images += proc.images

            if checkbox_iterate:
                p.seed = p.seed + (p.batch_size * p.n_iter)
            all_prompts += proc.all_prompts
            infotexts += proc.infotexts

        return Processed(p, images, p.seed, "", all_prompts=all_prompts, infotexts=infotexts)
