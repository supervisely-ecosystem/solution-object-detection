from typing import Any, Callable, Dict, List, Literal, Optional

from supervisely.api.api import Api
from supervisely.app.widgets import (
    ClassesTable,
    Container,
    Dialog,
    Field,
    Icons,
    SolutionCard,
    Text,
    Widget,
)
from supervisely.geometry.rectangle import Rectangle
from supervisely.project.project_meta import ProjectMeta
from supervisely.solution.base_node import Automation, SolutionCardNode, SolutionElement


class RefreshDefinitions(Automation):
    """
    This automation is used to refresh the definitions (classes) in the project.
    It updates the main widget with the latest definitions data.
    """

    def __init__(self, func: Callable, interval: int = 60):
        self.func = func
        self.interval = interval

    def apply(self):
        self.scheduler.add_job(self.func, interval=self.interval, job_id="refresh_definitions_info")


class DefinitionsGUI(Widget):
    def __init__(
        self,
        project_id: int,
        widget_id: Optional[str] = None,
    ):
        super().__init__(widget_id=widget_id)
        self.project_id = project_id
        self.content = self._init_gui()

    @property
    def classes_table(self) -> ClassesTable:
        if not hasattr(self, "_classes_table"):
            self._classes_table = ClassesTable(
                project_meta=ProjectMeta(),
                allowed_types=[Rectangle],
                selectable=False,
            )
        return self._classes_table

    def _init_gui(self):
        return Container(
            widgets=[
                Field(
                    title="Classes",
                    description="List of classes used for labeling.",
                    content=self.classes_table,
                    icon=Field.Icon(
                        zmdi_class="zmdi zmdi-shape",
                        color_rgb=[255, 255, 255],
                        bg_color_rgb=[0, 154, 255],
                    ),
                ),
            ]
        )

    def update_classes(self, meta: ProjectMeta):
        """
        Updates the classes table with the provided project meta.
        """
        self.classes_table.set_project_meta(meta)

    def get_json_data(self) -> dict:
        return {}

    def get_json_state(self) -> dict:
        return {}


class DefinitionsNode(SolutionElement):
    def __init__(
        self,
        api: Api,
        project_id: int,
        x: int = 0,
        y: int = 0,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.api = api
        self.project_id = project_id
        self.main_widget = DefinitionsGUI(project_id=self.project_id)
        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.automation = RefreshDefinitions(func=self.update_classes)
        self.automation.apply()
        self.modals = [self.modal]

    def _create_card(self) -> SolutionCard:
        card = SolutionCard(
            title="Definitions",
            tooltip=SolutionCard.Tooltip(
                description="List of classes used in the project for labeling."
            ),
            width=250,
            icon=Icons(
                class_name="zmdi zmdi-shape",
                color="#1976D2",
                bg_color="#E3F2FD",
            ),
            tooltip_position="right",
        )

        @card.click
        def _on_card_click():
            self.modal.show()

        return card

    @property
    def modal(self) -> Widget:
        if not hasattr(self, "_modal"):
            self._modal = self._create_modal()
        return self._modal

    def _create_modal(self) -> Dialog:
        return Dialog(
            title="Classes",
            content=self.main_widget.content,
            size="tiny",
        )

    def update_classes(self):
        meta = ProjectMeta.from_json(self.api.project.get_meta(self.project_id))
        self.main_widget.update_classes(meta)
