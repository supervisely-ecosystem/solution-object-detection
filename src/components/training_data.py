from typing import List, Literal, Optional

from supervisely.api.api import Api
from supervisely.app import DataJson
from supervisely.app.widgets import Dialog, FastTable, Icons, SolutionCard, Widget
from supervisely.project import ProjectType
from supervisely.solution.base_node import SolutionCardNode, SolutionElement


class TrainingDataGUI(Widget):
    pass


class TrainingDataNode(SolutionElement):
    def __init__(
        self,
        api: Api,
        title: str,
        description: str,
        width: int = 250,
        x: int = 0,
        y: int = 0,
        team_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        *args,
        **kwargs,
    ):
        self.api = api
        self.title = title
        self.description = description
        self.width = width
        self.icon = icon or Icons(
            "zmdi zmdi-collection-folder-image",
            color="#1976D2",
            bg_color="#E3F2FD",
        )
        self.tooltip_position = tooltip_position
        super().__init__(*args, **kwargs)

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = []

    def _create_card(self) -> SolutionCard:
        return SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            icon=self.icon,
            tooltip_position=self.tooltip_position,
        )

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        return SolutionCard.Tooltip(description=self.description)
