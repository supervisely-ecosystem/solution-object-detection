import threading
import time
from typing import Any, Dict, Literal, Optional

from supervisely import logger
from supervisely.api.api import Api
from supervisely.api.project_api import ProjectInfo
from supervisely.app.widgets import Button, Dialog, Icons, TasksHistory
from supervisely.solution.base_node import (
    SolutionCard,
    SolutionCardNode,
    SolutionElement,
)


class ReevaluateTaskHistory(TasksHistory):
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


class ReevaluateNode(SolutionElement):
    APP_SLUG = "supervisely-ecosystem/model-benchmark"
    EVALUATION_ENDPOINT = "run_evaluation"

    def __init__(
        self,
        api: Api,
        model_path: str,
        project_info: ProjectInfo,
        dataset_ids: Optional[list[int]] = None,
        # title: str,
        # description: str,
        # width: int = 400,
        x: int = 0,
        y: int = 0,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        *args,
        **kwargs,
    ):
        self.tooltip_position = tooltip_position
        self.icon = icon
        super().__init__(*args, **kwargs)

        self.api = api
        self.project = project_info
        self.dataset_ids = dataset_ids
        self.model_path = model_path
        self.agent_id = self._get_agent()
        self._finish_callbacks = []

        self.modals = [self.task_history_modal]
        self.card = self._create_card()
        self._update_tooltip_properties()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)

    @property
    def automation_enabled(self) -> bool:
        if not hasattr(self, "_automation_enabled"):
            self._automation_enabled = False
        return self._automation_enabled

    @automation_enabled.setter
    def automation_enabled(self, value: bool):
        self._automation_enabled = value

    @property
    def task_history(self) -> ReevaluateTaskHistory:
        if not hasattr(self, "_task_history"):
            self._task_history = ReevaluateTaskHistory()
        return self._task_history

    @property
    def task_history_modal(self) -> Dialog:
        if not hasattr(self, "_task_history_modal"):
            self._task_history_modal = Dialog(
                title="",
                content=self.task_history,
            )
        return self._task_history_modal

    @property
    def task_history_btn(self) -> Button:
        if not hasattr(self, "_task_history_btn"):
            self._task_history_btn = Button(
                "Task History",
                icon=Icons("zmdi zmdi-history"),
            )

            @self._task_history_btn.click
            def show_task_history():
                self.task_history.show()

        return self._task_history_btn

    @property
    def run_btn(self) -> Button:
        if not hasattr(self, "_run_btn"):
            self._run_btn = Button(
                "Run",
                icon=Icons("zmdi zmdi-play"),
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
                icon=Icons("zmdi zmdi-automation"),
            )

            @self._toggle_automation_btn.click
            def toggle_automation():
                self.automation_enabled = not self.automation_enabled
                self._update_tooltip_properties()
                if self.automation_enabled:
                    self._toggle_automation_btn.text("Disable Automation")
                else:
                    self._toggle_automation_btn.text("Enable Automation")

        return self._toggle_automation_btn

    @property
    def model(self):
        if not hasattr(self, "_model"):
            self._deploy_model()
        return self._model

    def _deploy_model(self):
        self._model = self.api.nn.deploy(
            model="",
            agent_id=self.agent_id,
            workspace_id=self.project.workspace_id,
            description="Solution: " + self.api.task_id,
        )

    @property
    def eval_session_info(self) -> int:
        if not hasattr(self, "_eval_session_info"):
            self._start_evaluator_session()
        return self._eval_session_info

    def _start_evaluator_session(self):
        module_id = self.api.app.get_ecosystem_module_id(self.APP_SLUG)
        task_info_json = self.api.task.start(
            agent_id=self.agent_id,
            workspace_id=self.project.workspace_id,
            description=f"Solution: {self.api.task_id}",
            module_id=module_id,
        )
        task_id = task_info_json["id"]
        current_time = time.time()
        while self.api.task.get_status(task_id) != self.api.task.Status.STARTED:
            time.sleep(5)
            if time.time() - current_time > 300:
                break
        ready = self.api.app.wait_until_ready_for_api_calls(task_id)
        if not ready:
            raise RuntimeError(f"Task {task_id} did not start successfully.")
        self._eval_session_info = task_info_json

    def run(self):
        if not hasattr(self, "_eval_session_info") and not hasattr(self, "_model"):
            # create threads for deployment and evaluation sessions and start them concurrently
            deploy_thread = threading.Thread(target=self._deploy_model)
            eval_thread = threading.Thread(target=self._start_evaluator_session)
            deploy_thread.start()
            eval_thread.start()

            # wait for both threads to finish
            deploy_thread.join()
            eval_thread.join()

        # start the evaluation request in a thread
        thread = threading.Thread(target=self._send_evaluation_request)
        thread.daemon = True
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
        session_info["modelPath"] = self.model_path
        # @TODO:
        session_info["collectionName"] = None
        if response.error:
            logger.error(f"Error during evaluation: {response.error}")
        else:
            res_dir = response.data.get("res_dir", "")
        self.task_history.add_task(session_info)
        for cb in self._finish_callbacks:
            cb(res_dir)

    def on_finish(self, fn):
        self._finish_callbacks.append(fn)
        return fn

    def _create_card(self) -> SolutionCard:
        return SolutionCard(
            title="Re-evaluate on new validation dataset",
            tooltip=self._create_tooltip(),
            tooltip_position=self.tooltip_position,
            width=400,
            icon=self.icon,
        )

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        return SolutionCard.Tooltip(
            description="Re-evaluate the best model on a new validation dataset.",
            content=[self.run_btn, self.toggle_automation_btn, self.task_history_btn],
            properties=[
                {
                    "key": "Re-evaluate models automatically",
                    "value": "disabled" if not self.automation_enabled else "enabled",
                    "highlight": True,
                    "link": False,
                },
            ],
        )

    def _update_tooltip_properties(self) -> None:
        new_props = [
            {
                "key": "Re-evaluate models automatically",
                "value": "disabled" if not self.automation_enabled else "enabled",
                "highlight": True,
                "link": False,
            },
        ]
        for prop in new_props:
            self.card.update_property(**prop)

    def _get_agent(self) -> int:
        return self.api.nn._deploy_api._find_agent(self.project.team_id)
