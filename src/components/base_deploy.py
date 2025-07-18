# здесь будет класс, которые будет отвечать за деплой модели, показывать информацию о ней


from typing import List, Literal, Optional

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
    SolutionCard,
    TasksHistory,
    Text,
    Widget,
)
from supervisely.io.env import team_id as env_team_id
from supervisely.solution.base_node import SolutionCardNode, SolutionElement
from supervisely.solution.components.tasks_history import SolutionTasksHistory


class DeployTasksHistory(SolutionTasksHistory):
    def __init__(self, api: Api, title: str = "Tasks History"):
        super().__init__(api, title)
        self.tasks_history.table_columns = [
            "Task ID",
            "App Name",
            "Model Name",
            "Started At",
            # "Classses Count",
            "Status",
            "Runtime",
            "Hardware",
            "Device",
        ]
        self.tasks_history.table_columns_keys = [
            ["id"],
            ["task_info", "meta", "app", "name"],
            ["deploy_info", "model_name"],
            ["task_info", "created_at"],
            # ["meta", "model", "classes_count"],
            ["status"],
            ["deploy_info", "runtime"],
            ["deploy_info", "hardware"],
            ["deploy_info", "device"],
        ]


class BaseDeployGUI(Widget):
    def __init__(
        self,
        api: Api,
        team_id: Optional[int] = None,
        widget_id: Optional[str] = None,
    ):
        self.api = api
        self.team_id = team_id
        self.model = None
        super().__init__(widget_id=widget_id)
        self.content = self._init_gui()

    @property
    def select_agent(self):
        if not hasattr(self, "_select_agent"):
            self._select_agent = AgentSelector(team_id=self.team_id, compact=True)
        return self._select_agent

    @property
    def select_agent_field(self):
        if not hasattr(self, "_select_agent_field"):
            self._select_agent_field = Field(
                title="Select Agent",
                content=self.select_agent_container,
                description="Select an agent to deploy the model.",
            )
        return self._select_agent_field

    @property
    def change_agent_button(self):
        if not hasattr(self, "_change_agent_button"):
            self._change_agent_button = Button(
                text="Change Agent",
                icon="zmdi zmdi-refresh",
                button_type="text",
                button_size="mini",
                plain=True,
            )

            @self._change_agent_button.click
            def _on_change_agent_click():
                self.select_agent.enable()
                if self.model is not None:
                    self.enable_gui()
                    self.model.shutdown()
                    self.model = None

            self._change_agent_button.hide()

        return self._change_agent_button

    @property
    def select_agent_container(self):
        if not hasattr(self, "_select_agent_container"):
            self._select_agent_container = Flexbox(
                [
                    self.select_agent,
                    self.change_agent_button,
                ],
                vertical_alignment="center",
                gap=15,
                # style="padding-top: 10px;",
                # direction="horizontal",
            )
        return self._select_agent_container

    @property
    def model_name_input(self):
        if not hasattr(self, "_model_name_input"):
            self._model_name_input = Input(
                placeholder="Enter model name. E.g. 'RT-DETRv2/rt-detrv2-s"
            )
        return self._model_name_input

    @property
    def model_name_input_container(self):
        if not hasattr(self, "_model_name_input_container"):
            self._model_name_input_container = Container(
                widgets=[
                    Field(
                        title="Model",
                        content=self.model_name_input,
                        description="Enter the name of the Pre-trained model or the path to a Custom checkpoint in Team Files.",
                    ),
                ],
                style="padding-top: 15px;",
            )
        return self._model_name_input_container

    @property
    def deploy_button(self):
        if not hasattr(self, "_deploy_button"):
            self._deploy_button = Button(text="Deploy")
        return self._deploy_button

    @property
    def stop_button(self):
        if not hasattr(self, "_stop_button"):
            self._stop_button = Button(text="Stop", button_type="danger")
            self._stop_button.hide()
        return self._stop_button

    @property
    def deploy_button_container(self):
        if not hasattr(self, "_deploy_button_container"):
            self._deploy_button_container = Container(
                widgets=[self.stop_button, self.deploy_button],
                direction="horizontal",
                overflow="wrap",
                style="display: flex; justify-content: flex-end;",
                widgets_style="display: flex; flex: none;",
            )
        return self._deploy_button_container

    def _init_gui(self):
        return Container(
            widgets=[
                Container(
                    widgets=[
                        self.model_name_input_container,
                        self.select_agent_field,
                        self.deploy_button_container,
                    ],
                    gap=20,
                ),
            ],
        )

    def deploy(self, model: Optional[str] = None) -> None:
        try:
            if model is None:
                model = self.model_name_input.get_value()
            agent_id = self.select_agent.get_value()
            if not model:
                show_dialog(
                    title="Error", description="Model name cannot be empty.", status="error"
                )
            self.model = self.api.nn.deploy(model=model, agent_id=agent_id)
        except Exception as e:
            show_dialog(
                title="Deployment Error",
                description=f"An error occurred while deploying the model: {str(e)}",
                status="error",
            )
            self.model = None

    def get_json_data(self) -> dict:
        return {}

    def get_json_state(self) -> dict:
        return {}

    def enable_gui(self):
        self.select_agent.enable()
        self.model_name_input.enable()
        self.deploy_button.show()
        self.stop_button.hide()
        self.change_agent_button.hide()

    def disable_gui(self):
        self.select_agent.disable()
        self.model_name_input.disable()
        self.deploy_button.hide()
        self.stop_button.show()
        self.change_agent_button.show()


class BaseDeployNode(SolutionElement):
    gui_class = BaseDeployGUI

    def __init__(
        self,
        api: Api,
        title: str,
        description: str,
        icon: Icons,
        x: int = 0,
        y: int = 0,
        *args,
        **kwargs,
    ):

        self.title = title
        self.description = description
        self.icon = icon
        self.width = 200

        self.api = api
        self.tasks_history = DeployTasksHistory(self.api)
        self.main_widget = self.gui_class(api=api, team_id=env_team_id())

        @self.main_widget.deploy_button.click
        def _on_deploy_button_click():
            self.settings_modal.hide()
            self.card.loading = True
            self.deploy(model=self.main_widget.model_name_input.get_value())
            self.card.loading = False

        @self.main_widget.stop_button.click
        def _on_stop_button_click():
            if self.main_widget.model is None:
                return
            try:
                self.main_widget.model.shutdown()
                self.main_widget.enable_gui()
                self.session_link = ""
            except Exception as e:
                show_dialog(
                    title="Error",
                    description=f"An error occurred while stopping the model: {str(e)}",
                    status="error",
                )

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [
            self.tasks_history.tasks_modal,
            self.tasks_history.logs_modal,
            self.settings_modal,
        ]
        super().__init__(*args, **kwargs)

    def _create_card(self) -> SolutionCard:
        card = SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            width=self.width,
            icon=self.icon,
            tooltip_position="right",
        )

        @card.click
        def _on_card_click():
            self.settings_modal.show()

        return card

    def _create_tooltip(self):
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

    @property
    def settings_modal(self) -> Widget:
        if not hasattr(self, "_settings_modal"):
            self._settings_modal = self._create_settings_modal()
        return self._settings_modal

    def _create_settings_modal(self) -> Dialog:
        return Dialog(
            title="Deploy Settings",
            content=self.main_widget.content,
            size="tiny",
        )

    def deploy(self, model: Optional[str] = None) -> None:
        """
        Deploys the model using the main widget's deploy method.
        """
        try:
            if self.main_widget.model is not None:
                self.main_widget.model.shutdown()
                self.main_widget.enable_gui()
                self.session_link = ""
            self.main_widget.deploy(model=model)
            if self.main_widget.model is not None:
                self.session_link = self.main_widget.model.url
            self.main_widget.disable_gui()
            task_info = self.api.task.get_info_by_id(self.main_widget.model.task_id)
            deploy_info = self.main_widget.model.get_info()
            self.tasks_history.add_task(
                {
                    "id": task_info["id"],
                    "task_info": task_info,
                    "deploy_info": deploy_info,
                }
            )
        except Exception as e:
            show_dialog(
                title="Deployment Error",
                description=f"An error occurred while deploying the model: {str(e)}",
                status="error",
            )
            self.main_widget.enable_gui()
            self.session_link = ""
