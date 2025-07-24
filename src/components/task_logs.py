from typing import Any, Callable, Dict, List, Literal, Optional

from supervisely.app.widgets import (
    Container,
    Dialog,
    Icons,
    SolutionCard,
    TaskLogs,
    Widget,
)
from supervisely.solution.base_node import SolutionCardNode, SolutionElement


class TaskLogsGUI(Widget):
    def __init__(self, task_id: int, widget_id: Optional[str] = None):
        self.task_id = task_id
        super().__init__(widget_id=widget_id)
        self.content = self._init_gui()

    @property
    def logs(self):
        if not hasattr(self, "_logs"):
            self._logs = TaskLogs(task_id=self.task_id)
        return self._logs

    def _init_gui(self):
        return Container(widgets=[self.logs])

    def get_json_data(self) -> dict:
        return {}

    def get_json_state(self) -> dict:
        return {}


class TaskLogsNode(SolutionElement):
    def __init__(self, task_id: int, x: int = 0, y: int = 0, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.task_id = task_id
        self.main_widget = TaskLogsGUI(task_id=self.task_id)
        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.tasks_modal]

    def _create_card(self) -> SolutionCard:
        card = SolutionCard(
            title="Logs",
            tooltip=SolutionCard.Tooltip(
                description="View the logs of the Solution app session to track the progress of the all tasks."
            ),
            width=250,
            icon=Icons(
                class_name="zmdi zmdi-format-list-bulleted",
                color="#1976D2",
                bg_color="#E3F2FD",
            ),
            tooltip_position="right",
        )

        @card.click
        def _on_card_click():
            self.tasks_modal.show()

        return card

    @property
    def tasks_modal(self) -> Widget:
        if not hasattr(self, "_tasks_modal"):
            self._tasks_modal = self._create_tasks_modal()
        return self._tasks_modal

    def _create_tasks_modal(self) -> Dialog:
        return Dialog(title="Task Logs", content=self.main_widget.content)
