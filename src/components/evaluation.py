import threading
import time
from typing import Any, Dict, Literal, Optional, Union

from supervisely import logger, timeit
from supervisely.api.api import Api
from supervisely.api.project_api import ProjectInfo
from supervisely.app.widgets import (
    AgentSelector,
    Button,
    Container,
    Dialog,
    FastTable,
    Field,
    Icons,
    Switch,
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

    @property
    def table(self):
        if not hasattr(self, "_tasks_table"):
            self._tasks_table = self._create_tasks_history_table()

            @self._tasks_table.cell_click
            def on_cell_click(clicked_cell: FastTable.ClickedCell):
                if clicked_cell.column_index == 4:  # Session ID
                    col_idx = 4
                else:
                    col_idx = 0
                self.logs.set_task_id(clicked_cell.row[col_idx])
                logger.debug("Showing logs for task ID: %s", self.logs.get_task_id())
                self.logs_modal.show()

        return self._tasks_table


class EvaluationNode(SolutionElement):
    APP_SLUG = "supervisely-ecosystem/model-benchmark"
    EVALUATION_ENDPOINT = "run_evaluation"

    def __init__(
        self,
        api: Api,
        project: Union[int, ProjectInfo],
        dataset_ids: Optional[list[int]] = None,
        collection: Union[int, str] = None,
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
        self.project = (
            project if isinstance(project, ProjectInfo) else api.project.get_info_by_id(project)
        )
        if not bool(dataset_ids) ^ bool(collection):
            raise ValueError("Either dataset_ids or collection must be provided, but not both.")
        self.dataset_ids = dataset_ids
        self.collection = None
        try:
            if isinstance(collection, str):
                self.collection = api.entities_collection.get_info_by_name(project.id, collection)
            elif isinstance(collection, int):
                self.collection = api.entities_collection.get_info_by_id(collection)
            else:
                raise TypeError("Collection must be either a string (name) or an integer (ID).")
        except Exception as e:
            logger.warning(f"Failed to get collection info: {e}")

        self._finish_callbacks = []

        self.task_history = EvaluationTaskHistory()
        self.modals = [self.task_history_modal, self.settings_modal, self.task_history.logs_modal]
        self.card = self._create_card()

        @self.card.click
        def show_settings():
            self.settings_modal.show()

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
    def settings_modal(self) -> Dialog:
        if not hasattr(self, "_settings_modal"):
            self._settings_modal = Dialog(
                title="Settings", content=self._init_settings_layout(), size="tiny"
            )
        return self._settings_modal

    def _init_settings_layout(self) -> Container:
        agent_selector = AgentSelector(self.project.team_id)
        agent_selector_field = Field(
            agent_selector,
            title="Select Agent for Evaluation",
            description="Select the agent to deploy the model on.",
            icon=Field.Icon(
                zmdi_class="zmdi zmdi-cloud", color_rgb=(21, 101, 192), bg_color_rgb=(227, 242, 253)
            ),
        )
        automation_switch = Switch()
        automation_field = Field(
            automation_switch,
            title="Enable Automation",
            description="Enable or disable automatic model re-evaluation after training.",
            icon=Field.Icon(
                zmdi_class="zmdi zmdi-settings",
                color_rgb=(21, 101, 192),
                bg_color_rgb=(227, 242, 253),
            ),
        )
        self._get_agent = agent_selector.get_value

        @automation_switch.value_changed
        def on_automation_switch_change(value: bool):
            self.automation_enabled = value
            self._update_tooltip_properties()

        return Container([agent_selector_field, automation_field], gap=20)

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
                self.node.hide_finished_badge()
                self.node.hide_failed_badge()
                self.show_in_progress_badge()
                self._run_btn.disable()
                self.run()

        return self._run_btn

    @property
    def model(self):
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
        except Exception as e:
            logger.error(f"Failed to deploy model: {e}")
            self._model = None

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
            task_name="Solution: " + str(self.api.task_id),
            module_id=module_id,
            is_branch=True,  # ! remove
            app_version="add-collections",  # ! remove
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

        if not hasattr(self, "_model"):
            deploy_thread = threading.Thread(target=self._deploy_model)
            deploy_thread.start()

        eval_thread = threading.Thread(target=self._start_evaluator_session)
        eval_thread.start()

        # wait for both threads to finish
        eval_thread.join()
        deploy_thread.join()

        # send the evaluation request in a new thread
        thread = threading.Thread(target=self._send_evaluation_request, daemon=True)
        thread.start()

    def _send_evaluation_request(self):
        session_info = self.eval_session_info
        data = {
            "session_id": self.model.task_id,
            "project_id": self.project.id,
        }
        if self.dataset_ids:
            data["dataset_ids"] = self.dataset_ids
        elif self.collection:
            data["collection_id"] = self.collection.id
        response = self.api.task.send_request(
            session_info["id"], self.EVALUATION_ENDPOINT, data=data
        )
        session_info["taskId"] = self.eval_session_info["id"]
        session_info["sessionId"] = self.model.task_id
        session_info["modelPath"] = self._model_path
        session_info["collectionName"] = self.collection.name

        error = response.get("error")
        res_dir = response.get("data")
        session_info["status"] = "Success" if not error else "Failed"
        self.task_history.add_task(session_info)
        if error:
            logger.error(f"Error during evaluation: {error}")
            self.node.show_failed_badge()
        elif res_dir:
            self.node.show_finished_badge()
            for cb in self._finish_callbacks:
                cb(res_dir)

        self._run_btn.enable()
        self.hide_in_progress_badge()

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

    def show_in_progress_badge(self) -> None:
        badge = self.card.Badge("🏃‍♂️", "Evaluation...", "info", True)
        self.card.add_badge(badge)

    def hide_in_progress_badge(self) -> None:
        self.card.remove_badge_by_key("Evaluation...")
