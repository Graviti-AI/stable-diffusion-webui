import csv
import fnmatch
import os
import os.path
import pathlib
import re
from typing import NamedTuple, Optional
import shutil

from modules.paths_internal import data_path


class PromptStyle(NamedTuple):
    name: str
    prompt: str
    negative_prompt: str


def merge_prompts(style_prompt: str, prompt: str) -> str:
    if "{prompt}" in style_prompt:
        res = style_prompt.replace("{prompt}", prompt)
    else:
        parts = filter(None, (prompt.strip(), style_prompt.strip()))
        res = ", ".join(parts)

    return res


def apply_styles_to_prompt(prompt, styles):
    for style in styles:
        prompt = merge_prompts(style, prompt)

    return prompt


def unwrap_style_text_from_prompt(style_text, prompt):
    """
    Checks the prompt to see if the style text is wrapped around it. If so,
    returns True plus the prompt text without the style text. Otherwise, returns
    False with the original prompt.

    Note that the "cleaned" version of the style text is only used for matching
    purposes here. It isn't returned; the original style text is not modified.
    """
    stripped_prompt = prompt
    stripped_style_text = style_text
    if "{prompt}" in stripped_style_text:
        # Work out whether the prompt is wrapped in the style text. If so, we
        # return True and the "inner" prompt text that isn't part of the style.
        try:
            left, right = stripped_style_text.split("{prompt}", 2)
        except ValueError as e:
            # If the style text has multple "{prompt}"s, we can't split it into
            # two parts. This is an error, but we can't do anything about it.
            print(f"Unable to compare style text to prompt:\n{style_text}")
            print(f"Error: {e}")
            return False, prompt
        if stripped_prompt.startswith(left) and stripped_prompt.endswith(right):
            prompt = stripped_prompt[len(left) : len(stripped_prompt) - len(right)]
            return True, prompt
    else:
        # Work out whether the given prompt ends with the style text. If so, we
        # return True and the prompt text up to where the style text starts.
        if stripped_prompt.endswith(stripped_style_text):
            prompt = stripped_prompt[: len(stripped_prompt) - len(stripped_style_text)]
            if prompt.endswith(", "):
                prompt = prompt[:-2]
            return True, prompt

    return False, prompt


def extract_original_prompts(style: PromptStyle, prompt, negative_prompt):
    """
    Takes a style and compares it to the prompt and negative prompt. If the style
    matches, returns True plus the prompt and negative prompt with the style text
    removed. Otherwise, returns False with the original prompt and negative prompt.
    """
    if not style.prompt and not style.negative_prompt:
        return False, prompt, negative_prompt

    match_positive, extracted_positive = unwrap_style_text_from_prompt(
        style.prompt, prompt
    )
    if not match_positive:
        return False, prompt, negative_prompt

    match_negative, extracted_negative = unwrap_style_text_from_prompt(
        style.negative_prompt, negative_prompt
    )
    if not match_negative:
        return False, prompt, negative_prompt

    return True, extracted_positive, extracted_negative


def _load_styles_from_file(filename):
    p = pathlib.Path(filename)
    styles = {}
    if not p.exists() or p.is_dir():
        return styles
    with open(p, "r", encoding="utf-8-sig", newline='') as file:
        reader = csv.DictReader(file, skipinitialspace=True)
        for row in reader:
            # Ignore empty rows or rows starting with a comment
            if not row or row["name"].startswith("#"):
                continue
            # Support loading old CSV format with "name, text"-columns
            prompt = row["prompt"] if "prompt" in row else row["text"]
            negative_prompt = row.get("negative_prompt", "")
            styles[row["name"]] = PromptStyle(row["name"], prompt, negative_prompt)
    return styles


class StyleDatabase:
    built_in_styles = _load_styles_from_file(pathlib.Path(data_path, 'styles.csv'))

    def __init__(self, path: str):
        self.no_style = PromptStyle("None", "", "")
        self._user_styles = {}
        self._styles = {}
        self.path = path

        folder, file = os.path.split(self.path)
        filename, _, ext = file.partition('*')
        self.default_path = os.path.join(folder, filename + ext)

        self.prompt_fields = [field for field in PromptStyle._fields if field != "path"]

        self.reload()

    @property
    def styles(self):
        if not self._styles:
            self._styles.update(self._user_styles)
            for k, v in self.built_in_styles.items():
                if k not in self._user_styles:
                    self._styles[k] = v
        return self._styles

    def reload(self):
        self._user_styles = _load_styles_from_file(self.path)

    def get_style_prompts(self, styles):
        return [self.styles.get(x, self.no_style).prompt for x in styles]

    def get_negative_style_prompts(self, styles):
        return [self.styles.get(x, self.no_style).negative_prompt for x in styles]

    def apply_styles_to_prompt(self, prompt, styles):
        return apply_styles_to_prompt(
            prompt, [self.styles.get(x, self.no_style).prompt for x in styles]
        )

    def apply_negative_styles_to_prompt(self, prompt, styles):
        return apply_styles_to_prompt(
            prompt, [self.styles.get(x, self.no_style).negative_prompt for x in styles]
        )

    def save_styles(self, style: Optional[PromptStyle] = None) -> None:
        # Always keep a backup file around
        if os.path.exists(self.path):
            shutil.copy(self.path, f"{self.path}.bak")
        if style:
            self._user_styles[style.name] = style
        with open(self.path, 'w', encoding="utf-8-sig", newline='') as file:
            # _fields is actually part of the public API: typing.NamedTuple is a replacement for collections.NamedTuple,
            # and collections.NamedTuple has explicit documentation for accessing _fields. Same goes for _asdict()
            writer = csv.DictWriter(file, fieldnames=PromptStyle._fields)
            writer.writeheader()
            writer.writerows(style._asdict() for k, style in self._user_styles.items())
        self._styles = {}

    def delete_style(self, name: str) -> Optional[PromptStyle]:
        if name in self._user_styles:
            style = self._user_styles.pop(name)
            self.save_styles()
            return style
        return

    def extract_styles_from_prompt(self, prompt, negative_prompt):
        extracted = []

        applicable_styles = list(self.styles.values())

        while True:
            found_style = None

            for style in applicable_styles:
                is_match, new_prompt, new_neg_prompt = extract_original_prompts(
                    style, prompt, negative_prompt
                )
                if is_match:
                    found_style = style
                    prompt = new_prompt
                    negative_prompt = new_neg_prompt
                    break

            if not found_style:
                break

            applicable_styles.remove(found_style)
            extracted.append(found_style.name)

        return list(reversed(extracted)), prompt, negative_prompt
