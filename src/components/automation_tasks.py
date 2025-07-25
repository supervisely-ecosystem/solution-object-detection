from typing import Any, Callable, Dict, List, Literal, Optional

from supervisely.app.widgets import (
    Container,
    Dialog,
    FastTable,
    Icons,
    SolutionCard,
    Widget,
)
from supervisely.solution.base_node import Automation, SolutionCardNode, SolutionElement
from supervisely.solution.utils import get_interval_period

REFRESH_JOB_ID = "refresh_automation_info"


class RefreshAutomationInfo(Automation):
    """
    This automation is used to refresh the information about scheduled tasks.
    It updates the main widget with the latest tasks data.
    """

    def __init__(self, func: Callable, interval: int = 10):
        self.func = func
        self.interval = interval

    def apply(self):
        self.scheduler.add_job(self.func, interval=self.interval, job_id=REFRESH_JOB_ID)


class AutomationTasksGUI(Widget):
    def __init__(self, widget_id: Optional[str] = None):
        super().__init__(widget_id=widget_id)
        self.content = self._init_gui()

    @property
    def table(self):
        if not hasattr(self, "_table"):
            self._table = FastTable(columns=["ID", "Job ID", "Interval", "Options"])
        return self._table

    def _init_gui(self):
        return Container(widgets=[self.table])

    def get_json_data(self) -> dict:
        return {}

    def get_json_state(self) -> dict:
        return {}

    def _get_table_data(self, tasks: Dict[str, Any]) -> List[List[str]]:
        data = []
        for idx, job_id in enumerate(tasks.keys(), start=1):
            if job_id == REFRESH_JOB_ID:
                continue
            sec = tasks[job_id].trigger.interval  # datetime seconds
            sec = int(sec.total_seconds()) if hasattr(sec, "total_seconds") else sec
            period, interval = get_interval_period(sec)
            readable_interval = f"{interval} {period}"
            row = [
                idx,
                job_id,
                readable_interval,
                "N/A",  # Options column will be implemented later
            ]
            data.append(row)
        return data


class AutomationTasksNode(SolutionElement):
    def __init__(self, x: int = 0, y: int = 0, *args, **kwargs):

        super().__init__(*args, **kwargs)
        self.main_widget = AutomationTasksGUI()
        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.tasks_modal]
        self.automation = RefreshAutomationInfo(func=self.update_properties)
        self.automation.apply()

    def _create_card(self) -> SolutionCard:
        card = SolutionCard(
            title="All Automations",
            tooltip=SolutionCard.Tooltip(
                description="All automations are listed here. Automations can be used to perform various tasks, such as data import, export, and training models automatically."
            ),
            width=250,
            icon=Icons(
                class_name="zmdi zmdi-flash-auto",
                color="#1976D2",
                bg_color="#E3F2FD",
            ),
            tooltip_position="right",
        )

        @card.click
        def _on_card_click():
            self.tasks_modal.show()
            self.main_widget.table.clear()
            data = self.main_widget._get_table_data(tasks=self.automation.scheduler.jobs)
            for row in data:
                self.main_widget.table.insert_row(row)

        return card

    @property
    def tasks_modal(self) -> Widget:
        if not hasattr(self, "_tasks_modal"):
            self._tasks_modal = self._create_tasks_modal()
        return self._tasks_modal

    def _create_tasks_modal(self) -> Dialog:
        return Dialog(
            title="Automation Tasks",
            content=self.main_widget.content,
            size="tiny",
        )

    def update_properties(self):
        """Update node properties with current tasks number."""
        tasks_number = len(self.automation.scheduler.jobs)
        self.card.update_property(key="Total automations", value=f"{tasks_number}")
        self.card.update_badge_by_key(key="Total automations:", label=f"{tasks_number}")
