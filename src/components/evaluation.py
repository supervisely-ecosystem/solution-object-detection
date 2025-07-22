import threading
import time
from typing import Any, Dict, Literal, Optional

from supervisely import logger, timeit
from supervisely.api.api import Api
from supervisely.api.project_api import ProjectInfo
from supervisely.app.widgets import (
    AgentSelector,
    Button,
    Container,
    Dialog,
    Field,
    Icons,
    SelectCudaDevice,
    TasksHistory,
)
from supervisely.solution.base_node import (
    SolutionCard,
    SolutionCardNode,
    SolutionElement,
)


class EvaluationTaskHistory(TasksHistory):
    def __init__(
        self,
        widget_id: str = None,
    ):
        super().__init__(widget_id=widget_id)
        self._table_columns = [
            "Task ID",
            "Model Path",
            "Status",
            "Collection Name",
            "Session ID",
        ]
        self._columns_keys = [
            ["taskId"],
            ["modelPath"],
            ["status"],
            ["collectionName"],
            ["sessionId"],
        ]

    def update(self):
        self.table.clear()
        for task in self._get_table_data():
            self.table.insert_row(task)

    def add_task(self, task: Dict[str, Any]) -> int:
        super().add_task(task)
        self.update()


class EvaluationNode(SolutionElement):
    APP_SLUG = "supervisely-ecosystem/model-benchmark"
    EVALUATION_ENDPOINT = "run_evaluation"

    def __init__(
        self,
        api: Api,
        project_info: ProjectInfo,
        dataset_ids: Optional[list[int]] = None,
        # title: str,
        # description: str,
        # width: int = 320,
        x: int = 0,
        y: int = 0,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        *args,
        **kwargs,
    ):
        self.tooltip_position = tooltip_position
        self.icon = icon or Icons(
            class_name="zmdi zmdi-assignment-check",
            color="#1976D2",
            bg_color="#E3F2FD",
        )
        super().__init__(*args, **kwargs)

        self.api = api
        self.project = project_info
        self.dataset_ids = dataset_ids
        self._finish_callbacks = []

        self.task_history = EvaluationTaskHistory()
        self.modals = [self.task_history_modal, self.evaluation_settings_modal]
        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self._update_tooltip_properties()

    @property
    def automation_enabled(self) -> bool:
        if not hasattr(self, "_automation_enabled"):
            self._automation_enabled = False
        return self._automation_enabled

    @automation_enabled.setter
    def automation_enabled(self, value: bool):
        self._automation_enabled = value

    @property
    def task_history_modal(self) -> Dialog:
        if not hasattr(self, "_task_history_modal"):
            self._task_history_modal = Dialog(
                title="",
                content=self.task_history,
            )
        return self._task_history_modal

    @property
    def evaluation_settings_modal(self) -> Dialog:
        if not hasattr(self, "_evaluation_settings_modal"):
            self._evaluation_settings_modal = Dialog(
                title="Evaluation Settings", content=self._init_eval_settings_layout(), size="tiny"
            )
        return self._evaluation_settings_modal

    def _init_eval_settings_layout(self) -> Container:
        agent_selector = AgentSelector(self.project.team_id)
        agent_selector_field = Field(
            agent_selector,
            title="Select Agent for Evaluation",
            description="Select the agent to deploy the model on.",
            icon=Field.Icon(
                zmdi_class="zmdi zmdi-cloud", color_rgb=(21, 101, 192), bg_color_rgb=(227, 242, 253)
            ),
        )
        # cuda_device = SelectCudaDevice(sort_by_free_ram=True, include_cpu_option=True)
        self._get_agent = agent_selector.get_value
        return Container(
            [
                agent_selector_field,
                #   cuda_device
            ]
        )

    @property
    def task_history_btn(self) -> Button:
        if not hasattr(self, "_task_history_btn"):
            self._task_history_btn = Button(
                "Tasks History",
                icon="zmdi zmdi-format-list-bulleted",
                button_size="mini",
                plain=True,
                button_type="text",
            )

            @self._task_history_btn.click
            def show_task_history():
                self.task_history_modal.show()

        return self._task_history_btn

    @property
    def run_btn(self) -> Button:
        if not hasattr(self, "_run_btn"):
            self._run_btn = Button(
                "Run",
                icon="zmdi zmdi-play",
                plain=True,
                button_type="text",
                button_size="mini",
            )

            @self._run_btn.click
            def run_cb():
                self._run_btn.disable()
                self.run()
                self._run_btn.enable()

        return self._run_btn

    @property
    def toggle_automation_btn(self) -> Button:
        if not hasattr(self, "_toggle_automation_btn"):
            self._toggle_automation_btn = Button(
                "Enable Automation",
                icon="zmdi zmdi-settings",
                button_size="mini",
                plain=True,
                button_type="text",
            )

            @self._toggle_automation_btn.click
            def toggle_automation():
                self.automation_enabled = not self.automation_enabled
                self._update_tooltip_properties()
                if self.automation_enabled:
                    self._toggle_automation_btn.text = "Disable Automation"
                else:
                    self._toggle_automation_btn.text = "Enable Automation"

        return self._toggle_automation_btn

    @property
    def evaluation_settings_btn(self) -> Button:
        if not hasattr(self, "_evaluation_settings_btn"):
            self._evaluation_settings_btn = Button(
                "Evaluation Settings",
                icon="zmdi zmdi-settings",
                button_size="mini",
                plain=True,
                button_type="text",
            )

            @self._evaluation_settings_btn.click
            def show_evaluation_settings():
                self.evaluation_settings_modal.show()

        return self._evaluation_settings_btn

    @property
    def model(self):
        # if not hasattr(self, "_model"):
        #     self._deploy_model()
        if not hasattr(self, "_model"):
            raise RuntimeError("Model is not deployed.")
        return self._model

    @timeit
    def _deploy_model(self):
        try:
            self._model = self.api.nn.deploy(
                model=self._model_path,
                device="cpu",  # for now
                workspace_id=self.project.workspace_id,
                agent_id=self._get_agent(),
                task_name="Solution: " + str(self.api.task_id),
            )
        except TimeoutError as e:
            # TimeoutError: Task 48446 is not ready for API calls after 100 seconds.
            import re

            msg = str(e)
            match = re.search(r"Task (\d+) is not ready", msg)
            if match:
                task_id = int(match.group(1))
                self.api.task.stop(task_id)
                logger.error(f"Deployment task (id: {task_id}) timed out after 100 seconds.")
            else:
                logger.error(f"Model deployment timed out: {msg}")
            raise

    @property
    def eval_session_info(self) -> int:
        # if not hasattr(self, "_eval_session_info"):
        #     self._start_evaluator_session()
        if not hasattr(self, "_eval_session_info"):
            raise RuntimeError("Evaluation session info is not available.")
        return self._eval_session_info

    @timeit
    def _start_evaluator_session(self):
        module_id = self.api.app.get_ecosystem_module_id(self.APP_SLUG)
        task_info_json = self.api.task.start(
            agent_id=self._get_agent(),
            workspace_id=self.project.workspace_id,
            description="Solution: " + str(self.api.task_id),
            module_id=module_id,
        )
        task_id = task_info_json["id"]
        current_time = time.time()
        while self.api.task.get_status(task_id) != self.api.task.Status.STARTED:
            time.sleep(5)
            if time.time() - current_time > 300:
                break
        ready = self.api.app.wait_until_ready_for_api_calls(
            task_id=task_id, attempts=50, attempt_delay_sec=2
        )
        if not ready:
            self.api.task.stop(task_id)
            raise RuntimeError(
                f"Evaluator session (task id: {task_id}) did not start successfully after 100 seconds."
            )
        self._eval_session_info = task_info_json

    def run(self):
        if not hasattr(self, "_model_path"):
            logger.warning(
                "Model path is not set. Please set the model path before running the evaluation."
            )
            return
        if not hasattr(self, "_eval_session_info") and not hasattr(self, "_model"):
            # create threads for deployment and evaluation sessions and start them concurrently
            deploy_thread = threading.Thread(target=self._deploy_model)
            eval_thread = threading.Thread(target=self._start_evaluator_session)
            deploy_thread.start()
            eval_thread.start()

            # wait for both threads to finish
            deploy_thread.join()
            eval_thread.join()

        # send the evaluation request in a new thread
        thread = threading.Thread(target=self._send_evaluation_request, daemon=True)
        thread.start()

    def _send_evaluation_request(self):
        session_info = self.eval_session_info
        response = self.api.task.send_request(
            session_info["id"],
            self.EVALUATION_ENDPOINT,
            data={
                "session_id": self.model.task_id,
                "project_id": self.project.id,
                "dataset_ids": self.dataset_ids,
            },
        )
        session_info["taskId"] = self.eval_session_info["id"]
        session_info["sessionId"] = self.model.task_id
        session_info["modelPath"] = self._model_path
        # @TODO:
        session_info["collectionName"] = None
        self.task_history.add_task(session_info)

        error = response.get("error")
        res_dir = response.get("data", {}).get("res_dir", None)
        if error:
            logger.error(f"Error during evaluation: {error}")
        elif res_dir:
            for cb in self._finish_callbacks:
                cb(res_dir)

    def on_finish(self, fn):
        self._finish_callbacks.append(fn)
        return fn

    def set_model_path(self, model_path: str):
        self._model_path = model_path

    def _create_card(self) -> SolutionCard:
        return SolutionCard(
            title="Re-evaluate on new validation dataset",
            tooltip=self._create_tooltip(),
            tooltip_position=self.tooltip_position,
            width=320,
            icon=self.icon,
        )

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        return SolutionCard.Tooltip(
            description="Re-evaluate the best model on a new validation dataset.",
            content=[
                self.run_btn,
                self.evaluation_settings_btn,
                self.toggle_automation_btn,
                self.task_history_btn,
            ],
            properties=[
                {
                    "key": "Auto model re-evaluation",
                    "value": "disabled" if not self.automation_enabled else "enabled",
                    "highlight": True,
                    "link": False,
                },
            ],
        )

    def _update_tooltip_properties(self) -> None:
        if self.automation_enabled:
            self.node.show_automation_badge()
        else:
            self.node.hide_automation_badge()
        new_props = [
            {
                "key": "Auto model re-evaluation",
                "value": "disabled" if not self.automation_enabled else "enabled",
                "highlight": True,
                "link": False,
            },
        ]
        for prop in new_props:
            self.card.update_property(**prop)
