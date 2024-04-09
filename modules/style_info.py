#!/usr/bin/env python3

import json

import gradio as gr
from fastapi import FastAPI, Query, Request
from pydantic import BaseModel
from typing_extensions import Self

import modules.script_callbacks as script_callbacks
from modules.shared import prompt_styles
from modules.styles import PromptStyle, StyleDatabase


class StyleInfoResponse(BaseModel):
    name: str
    prompt: str | None
    negative_prompt: str | None

    @classmethod
    def from_prompt_style(cls, style: PromptStyle) -> Self:
        return cls(
            name=style.name,
            prompt=style.prompt,
            negative_prompt=style.negative_prompt,
        )


class ListCandidateStylesResponse(BaseModel):
    styles: list[StyleInfoResponse]


class AllStyleInfo(StyleDatabase):
    def __init__(self, data: str) -> None:
        self.no_style = PromptStyle("None", "", "", None)
        self.styles = {item["name"]: PromptStyle(**item) for item in json.loads(data)}


def list_candidate_styles(
    request: Request, style: list[str] | None = Query(None)
) -> ListCandidateStylesResponse:
    if not style:
        return ListCandidateStylesResponse(styles=[])

    database = prompt_styles(request)
    styles = [database.styles.get(name) for name in style]
    return ListCandidateStylesResponse(
        styles=[StyleInfoResponse.from_prompt_style(item) for item in styles if item]
    )


def setup_style_api(_: gr.Blocks, app: FastAPI) -> None:
    app.add_api_route(
        "/internal/candidate_styles",
        list_candidate_styles,
        methods=["GET"],
        response_model=ListCandidateStylesResponse,
    )


script_callbacks.on_app_started(setup_style_api)
