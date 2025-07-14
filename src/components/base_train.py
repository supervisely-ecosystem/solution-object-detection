# здесь будет класс, которые будет отвечать за деплой модели, показывать информацию о ней


from typing import List, Literal, Optional

import supervisely.io.env as sly_env
from supervisely.api.api import Api
from supervisely.app.exceptions import show_dialog
from supervisely.app.widgets import (
    AgentSelector,
    Button,
    Container,
    Dialog,
    Field,
    Flexbox,
    Icons,
    Input,
    NewExperiment,
    SolutionCard,
    TasksHistory,
    Text,
    Widget,
)
from supervisely.solution.base_node import SolutionCardNode, SolutionElement
from supervisely.solution.components.tasks_history import SolutionTasksHistory


class TrainTasksHistory(SolutionTasksHistory):
    def __init__(self, api: Api, title: str = "Tasks History"):
        super().__init__(api, title)
        self.tasks_history.table_columns = [
            "Task ID",
            "Model Name",
            "Started At",
            "Status",
            "Hardware",
            "Device",
            # "Classes Count",
            "Images Count",
            "Train Collection",
            "Validation Collection",
        ]
        self.tasks_history.table_columns_keys = [
            ["id"],
            ["model_name"],
            ["task_info", "created_at"],
            ["status"],
            ["hardware"],
            ["device"],
            # ["classes_count"],
            ["images_count"],
            ["train_collection_name"],
            ["validation_collection_name"],
        ]


class BaseTrainGUI(Widget):

    def __init__(
        self,
        api: Api,
        workspace_id: int,
        team_id: Optional[int] = None,
        widget_id: Optional[str] = None,
    ):
        self.api = api
        self.workspace_id = workspace_id
        self.team_id = team_id
        super().__init__(widget_id=widget_id)
        self.content = self._init_gui()

    def _init_gui(self) -> Container:
        content = NewExperiment(workspace_id=self.workspace_id, team_id=self.team_id)

        @content.visible_changed
        def _on_visible_changed(visible: bool):
            print(f"NewExperiment visibility changed: {visible}")

        return content

    def get_json_data(self):
        return {}

    def get_json_state(self):
        return {}


class BaseTrainNode(SolutionElement):
    gui_class = BaseTrainGUI

    def __init__(
        self,
        api: Api,
        title: str,
        description: str,
        workspace_id: int = None,
        x: int = 0,
        y: int = 0,
        icon: Optional[Icons] = None,
        *args,
        **kwargs,
    ):

        self.title = title
        self.description = description
        self.icon = icon
        self.width = 250
        self.workspace_id = workspace_id or sly_env.workspace_id()

        self.api = api
        self.tasks_history = TrainTasksHistory(self.api, title="Train Tasks History")
        self.main_widget = self.gui_class(
            api=api, workspace_id=self.workspace_id, team_id=sly_env.team_id()
        )

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [
            self.tasks_history.tasks_modal,
            self.tasks_history.logs_modal,
            self.main_widget.content,
        ]
        super().__init__(*args, **kwargs)

        @self.card.click
        def _on_card_click():
            # if not self.main_widget.content.visible:
            self.main_widget.content.visible = True

    def _create_card(self) -> SolutionCard:
        return SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            width=self.width,
            icon=self.icon,
            tooltip_position="right",
        )

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        return SolutionCard.Tooltip(
            description=self.description,
            content=[self.tasks_button, self.open_session_button],
        )

    @property
    def tasks_button(self) -> Button:
        if not hasattr(self, "_tasks_button"):
            self._tasks_button = self._create_tasks_button()
        return self._tasks_button

    def _create_tasks_button(self) -> Button:
        btn = Button(
            text="Tasks History",
            icon="zmdi zmdi-view-list",
            button_size="mini",
            plain=True,
            button_type="text",
        )

        @btn.click
        def _show_tasks_dialog():
            self.tasks_history.tasks_history.update()
            self.tasks_history.tasks_modal.show()

        return btn

    @property
    def open_session_button(self) -> Button:
        if not hasattr(self, "_open_session_button"):
            self._open_session_button = self._create_open_session_button()
        return self._open_session_button

    def _create_open_session_button(self) -> Button:
        return Button(
            text="Open Running Session",
            icon="zmdi zmdi-open-in-new",
            button_size="mini",
            plain=True,
            button_type="text",
            link=self.session_link,
        )

    @property
    def session_link(self) -> str:
        return self._session_link if hasattr(self, "_session_link") else ""

    @session_link.setter
    def session_link(self, value: str):
        if not hasattr(self, "_session_link"):
            setattr(self, "_session_link", value)
        else:
            self._session_link = value
        self.open_session_button.link = value
