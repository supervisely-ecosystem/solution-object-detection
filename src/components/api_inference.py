from typing import Literal, Optional

import supervisely as sly
import supervisely.app.widgets as widgets
from src.components.overview import MarkdownNode, SolutionCard


class ApiInferenceNode(MarkdownNode):
    def __init__(
        self,
        markdown_path: str,
        title: str,
        description: str,
        width: int = 250,
        x: int = 0,
        y: int = 0,
        icon: Optional[widgets.Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        markdown_title: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """A node that displays API inference documentation."""
        content = open(markdown_path, "r", encoding="utf-8").read()
        super().__init__(
            content=content,
            title=title,
            description=description,
            width=width,
            x=x,
            y=y,
            icon=icon,
            tooltip_position=tooltip_position,
            markdown_title=markdown_title,
            *args,
            **kwargs,
        )
