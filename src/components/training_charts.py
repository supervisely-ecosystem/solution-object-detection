from typing import Literal, Optional

from src.components.overview import MarkdownNode
from supervisely import Api, logger
from supervisely.app.widgets import Icons, SolutionCard


class TrainingChartsNode(MarkdownNode):
    def __init__(
        self,
        api: Api,
        title: str = "Training Charts",
        description: str = "Charts showing the training process of the model.",
        width: int = 250,
        x: int = 0,
        y: int = 0,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
    ):
        self._api = api
        super().__init__(
            content=self._get_charts_md(),
            title=title,
            description=description,
            width=width,
            x=x,
            y=y,
            icon=icon,
            tooltip_position=tooltip_position,
        )

    def _get_charts_md(self) -> str:
        pass
