# здесь будет класс, которые будет отвечать за деплой модели, показывать информацию о ней


from typing import Callable, Dict, List, Literal, Optional, Tuple

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
from supervisely.sly_logger import logger
from supervisely.solution.base_node import Automation, SolutionCardNode, SolutionElement
from supervisely.solution.components.tasks_history import SolutionTasksHistory


class DeployTasksAutomation(Automation):
    REFRESH_RATE = 30  # seconds

    def __init__(self):
        super().__init__()
        self.job_id = f"deploy_tasks_automation"  # ! This should be unique for each automation

    def apply(self, func: Optional[Callable] = None) -> None:
        self.func = func or self.func
        if self.scheduler.is_job_scheduled(self.job_id):
            self.scheduler.remove_job(self.job_id)
        self.scheduler.add_job(self.func, self.REFRESH_RATE, self.job_id)

    def remove(self) -> None:
        if self.scheduler.is_job_scheduled(self.job_id):
            self.scheduler.remove_job(self.job_id)
        self.func = None


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
        self.tasks_history.columns_keys = [
            ["task_info", "id"],
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

    def deploy(
        self,
        model: Optional[str] = None,
        agent_id: Optional[int] = None,
        stop_current: bool = True,
    ) -> None:
        try:
            if model is None:
                model = self.model_name_input.get_value()
            else:
                self.model_name_input.set_value(model)
            if self.model is not None and stop_current:
                self.model.shutdown()
                self.enable_gui()
                self.model = None
            if agent_id is None:
                agent_id = self.select_agent.get_value()
            else:
                self.select_agent.set_value(agent_id)
            if not model:
                show_dialog(
                    title="Error", description="Model name cannot be empty.", status="error"
                )
                return
            self.model = self.api.nn.deploy(model=model, agent_id=agent_id)
            self.disable_gui()
        except Exception as e:
            show_dialog(
                title="Deployment Error",
                description=f"An error occurred while deploying the model: {str(e)}",
                status="error",
            )
            self.model = None
            self.enable_gui()

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
        x: int,
        y: int,
        api: Api,
        title: str = "Deploy Model",
        description: str = "Deploy the trained model to the Supervisely platform for inference.",
        *args,
        **kwargs,
    ):

        self.title = title
        self.description = description
        self.icon = Icons(class_name="zmdi zmdi-memory")
        self.width = 250

        self.api = api
        self.tasks_history = DeployTasksHistory(self.api)
        self.automation = DeployTasksAutomation()
        self.main_widget = self.gui_class(api=api, team_id=env_team_id())
        self.automation.apply(self.refresh_memory_usage_info)

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

    def deploy(self, model: Optional[str] = None, agent_id: Optional[int] = None) -> None:
        """
        Deploys the model using the main widget's deploy method.
        """
        try:
            self.main_widget.deploy(model=model, agent_id=agent_id)
            if self.main_widget.model is not None:
                self.session_link = self.main_widget.model.url
            task_info, deploy_info = self._get_deployed_model_info()
            self.tasks_history.add_task({"task_info": task_info, "deploy_info": deploy_info})

            self.session_link = self.main_widget.model.url
            self._update_properties(deploy_info)
        except Exception as e:
            show_dialog(
                title="Deployment Error",
                description=f"An error occurred while deploying the model: {str(e)}",
                status="error",
            )
            self.session_link = ""

    def _get_deployed_model_info(self) -> Tuple[Optional[Dict], Optional[Dict]]:
        """
        Returns the deployment information.
        """
        if self.main_widget.model is None:
            return None, None
        task_info = self.api.task.get_info_by_id(self.main_widget.model.task_id)
        deploy_info = self.main_widget.model.get_info()
        return task_info, deploy_info

    def _get_agent_info(self) -> Optional[Dict]:
        """
        Returns GPU information with available and total memory.
        If the model is not deployed or the agent does not have GPU info, returns None.

        """
        try:
            agent_id = self.main_widget.select_agent.get_value()
            if agent_id is None:
                return None
            agent_info = self.api.agent.get_info_by_id(agent_id)
            if not hasattr(agent_info, "gpu_info"):
                return None
            return {
                "available": agent_info.gpu_info["device_memory"][0]["available"],
                "total": agent_info.gpu_info["device_memory"][0]["total"],
                "agent_name": agent_info.name,
            }
        except Exception as e:
            logger.warning(f"Failed to get GPU info: {e}")
            return None

    def refresh_memory_usage_info(self) -> None:
        """
        Refreshes the GPU memory usage information.
        """
        agent_info = self._get_agent_info()
        if agent_info is not None:
            total = agent_info["total"]
            used = total - agent_info["available"]
            self.card.update_property("Agent", agent_info["agent_name"])
            self.card.update_property(
                "GPU Memory",
                f"{used / (1024 ** 3):.2f} GB / {total / (1024 ** 3):.2f} GB",
                False,
                True,
            )
        else:
            self.card.remove_property_by_key("Agent")
            self.card.remove_property_by_key("GPU Memory")

    def _update_properties(self, deploy_info: Optional[Dict] = None) -> None:
        """
        Updates the properties of the card with the current model and agent information.
        """
        if self.main_widget.model is not None:
            self.refresh_memory_usage_info()
            deploy_info = deploy_info or self._get_deployed_model_info()[1]
            self.card.update_property("Source", deploy_info["model_source"])
            self.card.update_property("Hardware", deploy_info["hardware"])
            self.card.update_property("Model", deploy_info["model_name"], False, True)
        else:
            self.card.remove_property_by_key("Source")
            self.card.remove_property_by_key("Hardware")
            self.card.remove_property_by_key("Model")
