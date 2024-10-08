import gradio as gr

from modules import shared, ui_common, ui_components, styles

styles_edit_symbol = '\U0001f58c\uFE0F'  # 🖌️
styles_materialize_symbol = '\U0001f4cb'  # 📋
styles_copy_symbol = '\U0001f4dd'  # 📝


def select_style(request: gr.Request, name):
    style = shared.prompt_styles(request).styles.get(name)
    existing = style is not None
    empty = not name

    prompt = style.prompt if style else gr.update()
    negative_prompt = style.negative_prompt if style else gr.update()

    return prompt, negative_prompt, gr.update(visible=existing), gr.update(visible=not empty)


def save_style(request: gr.Request, name, prompt, negative_prompt):
    if not name:
        return gr.update(visible=False)

    style = styles.PromptStyle(name, prompt, negative_prompt)
    prompt_styles = shared.prompt_styles(request)
    prompt_styles.styles[style.name] = style
    prompt_styles.save_styles()

    return gr.update(visible=True)


def delete_style(request: gr.Request, name, prompt, negative_prompt):
    if not name or (not prompt and not negative_prompt):
        return name, prompt, negative_prompt

    prompt_styles = shared.prompt_styles(request)
    prompt_styles.styles.pop(name, None)
    prompt_styles.save_styles()

    return '', '', ''


def materialize_styles(request: gr.Request, prompt, negative_prompt, styles):
    prompt = shared.prompt_styles(request).apply_styles_to_prompt(prompt, styles)
    negative_prompt = shared.prompt_styles(request).apply_negative_styles_to_prompt(negative_prompt, styles)

    return [gr.Textbox.update(value=prompt), gr.Textbox.update(value=negative_prompt), gr.Dropdown.update(value=[])]


def refresh_styles(request: gr.Request):
    return gr.update(choices=list(shared.prompt_styles(request).styles)), gr.update(choices=list(shared.prompt_styles(request).styles))


class UiPromptStyles:
    def __init__(self, tabname, main_ui_prompt, main_ui_negative_prompt):
        self.tabname = tabname
        self.main_ui_prompt = main_ui_prompt
        self.main_ui_negative_prompt = main_ui_negative_prompt

        with gr.Row(elem_id=f"{tabname}_styles_row"):
            self.dropdown = gr.Dropdown(label="Styles", show_label=False, elem_id=f"{tabname}_styles", choices=list(), value=[], multiselect=True, tooltip="Styles")
            self.materialize = ui_components.ToolButton(value=styles_materialize_symbol, elem_id=f"{tabname}_style_apply", tooltip="Apply all selected styles from the style selction dropdown in main UI to the prompt.")
            edit_button = ui_components.ToolButton(value=styles_edit_symbol, elem_id=f"{tabname}_styles_edit_button", tooltip="Edit styles")

        with gr.Box(elem_id=f"{tabname}_styles_dialog", elem_classes="popup-dialog") as styles_dialog:
            with gr.Row():
                self.selection = gr.Dropdown(label="Styles", elem_id=f"{tabname}_styles_edit_select", choices=list(), value=[], allow_custom_value=True, info="Styles allow you to add custom text to prompt. Use the {prompt} token in style text, and it will be replaced with user's prompt when applying style. Otherwise, style's text will be added to the end of the prompt.")

                def current_prompt_styles(request: gr.Request):
                    return {"choices": list(shared.prompt_styles(request).styles.keys())}

                ui_common.create_refresh_button([self.dropdown, self.selection], shared.reload_style, current_prompt_styles, f"refresh_{tabname}_styles")
                self.copy = ui_components.ToolButton(value=styles_copy_symbol, elem_id=f"{tabname}_style_copy", tooltip="Copy main UI prompt to style.")

            with gr.Row():
                self.prompt = gr.Textbox(label="Prompt", show_label=True, elem_id=f"{tabname}_edit_style_prompt", lines=3, elem_classes=["prompt"])

            with gr.Row():
                self.neg_prompt = gr.Textbox(label="Negative prompt", show_label=True, elem_id=f"{tabname}_edit_style_neg_prompt", lines=3, elem_classes=["prompt"])

            with gr.Row():
                self.save = gr.Button('Save', variant='primary', elem_id=f'{tabname}_edit_style_save', visible=False)
                self.delete = gr.Button('Delete', variant='primary', elem_id=f'{tabname}_edit_style_delete', visible=False)
                self.close = gr.Button('Close', variant='secondary', elem_id=f'{tabname}_edit_style_close')

        self.selection.change(
            fn=select_style,
            inputs=[self.selection],
            outputs=[self.prompt, self.neg_prompt, self.delete, self.save],
            show_progress="hidden",
        )

        self.save.click(
            fn=save_style,
            inputs=[self.selection, self.prompt, self.neg_prompt],
            outputs=[self.delete],
            show_progress="hidden",
        ).then(refresh_styles, outputs=[self.dropdown, self.selection], show_progress="hidden")

        self.delete.click(
            fn=delete_style,
            _js='''function(name, prompt, neg_prompt){
                if(name == "") return ["", prompt, neg_prompt];
                return confirm("Delete style " + name + "?") ? [name, prompt, neg_prompt] : ["", prompt, neg_prompt]; }''',
            inputs=[self.selection, self.prompt, self.neg_prompt],
            outputs=[self.selection, self.prompt, self.neg_prompt],
            show_progress="hidden",
        ).then(refresh_styles, outputs=[self.dropdown, self.selection], show_progress="hidden")

        self.setup_apply_button(self.materialize)

        self.copy.click(
            fn=lambda p, n: (p, n),
            inputs=[main_ui_prompt, main_ui_negative_prompt],
            outputs=[self.prompt, self.neg_prompt],
            show_progress=False,
        )

        ui_common.setup_dialog(button_show=edit_button, dialog=styles_dialog, button_close=self.close)

    def setup_apply_button(self, button):
        button.click(
            fn=materialize_styles,
            inputs=[self.main_ui_prompt, self.main_ui_negative_prompt, self.dropdown],
            outputs=[self.main_ui_prompt, self.main_ui_negative_prompt, self.dropdown],
            show_progress=False,
        ).then(fn=None, _js="function(){update_"+self.tabname+"_tokens(); closePopup();}", show_progress=False)
