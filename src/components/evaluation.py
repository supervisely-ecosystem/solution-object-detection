import threading
import time
from typing import Any, Dict, List, Literal, Optional, Union

from supervisely import logger, timeit
from supervisely.api.api import Api

# from supervisely.api.task_api import KubernetesSettings
from supervisely.api.entities_collection_api import EntitiesCollectionInfo
from supervisely.api.project_api import ProjectInfo
from supervisely.app.content import DataJson
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
    Widget,
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


class EvaluationReportGUI(Widget):

    def __init__(self, team_id: int, widget_id: Optional[str] = None):
        self.team_id = team_id
        super().__init__(widget_id=widget_id)
        self.content = self._init_gui()

    def _init_gui(self):
        agent_selector_field = Field(
            self.agent_selector,
            title="Select Agent for Evaluation",
            description="Select the agent to deploy the model on.",
            icon=Field.Icon(
                zmdi_class="zmdi zmdi-storage",
                color_rgb=(21, 101, 192),
                bg_color_rgb=(227, 242, 253),
            ),
        )
        automation_field = Field(
            self.automation_switch,
            title="Enable Automation",
            description="Enable or disable automatic model re-evaluation after training.",
            icon=Field.Icon(
                zmdi_class="zmdi zmdi-settings",
                color_rgb=(21, 101, 192),
                bg_color_rgb=(227, 242, 253),
            ),
        )

        return Container([agent_selector_field, automation_field], gap=20)

    @property
    def automation_switch(self) -> Switch:
        if not hasattr(self, "_automation_switch"):
            self._automation_switch = Switch(switched=True)
        return self._automation_switch

    @property
    def agent_selector(self) -> AgentSelector:
        if not hasattr(self, "_agent_selector"):
            self._agent_selector = AgentSelector(self.team_id)
        return self._agent_selector

    def get_json_data(self) -> dict:
        return {
            "enabled": self.automation_switch.is_switched(),
            "agent_id": self.agent_selector.get_value(),
        }

    def get_json_state(self) -> dict:
        return {}

    def save_settings(self, enabled: bool, agent_id: Optional[int] = None):
        DataJson()[self.widget_id]["settings"] = {
            "enabled": enabled,
            "agent_id": agent_id if agent_id is not None else self.agent_selector.get_value(),
        }
        DataJson().send_changes()

    def load_settings(self):
        data = DataJson().get(self.widget_id, {}).get("settings", {})
        enabled = data.get("enabled")
        agent_id = data.get("agent_id")
        self.update_widgets(enabled, agent_id)

    def update_widgets(self, enabled: bool, agent_id: Optional[int] = None):
        if enabled is True:
            self.automation_switch.on()
        elif enabled is False:
            self.automation_switch.off()
        else:
            pass  # do nothing, keep current state
        if agent_id is not None:
            self.agent_selector.set_value(agent_id)


class EvaluationNode(SolutionElement):
    APP_SLUG = "supervisely-ecosystem/model-benchmark"
    EVALUATION_ENDPOINT = "run_evaluation"

    def __init__(
        self,
        api: Api,
        project: Union[int, ProjectInfo],
        dataset_ids: Optional[List[int]] = None,
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
            if isinstance(collection, int):
                self.collection = api.entities_collection.get_info_by_id(collection)
            elif isinstance(collection, EntitiesCollectionInfo):
                self.collection = collection
            else:
                raise TypeError(
                    "Collection must be either an integer (ID) or EntitiesCollectionInfo."
                )
        except Exception as e:
            logger.warning(f"Failed to get collection info: {e}")

        self._start_callbacks = []
        self._finish_callbacks = []
        self.res_dir = None

        self.task_history = EvaluationTaskHistory()
        self.main_widget = EvaluationReportGUI(team_id=self.project.team_id)

        @self.main_widget.automation_switch.value_changed
        def on_automation_switch_change(value: bool):
            self.save(enabled=value)

        @self.main_widget.agent_selector.value_changed
        def on_agent_selector_change(value: int):
            self.save(agent_id=value)

        self.modals = [self.task_history_modal, self.settings_modal, self.task_history.logs_modal]
        self.card = self._create_card()

        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self._update_properties(self.main_widget.automation_switch.is_switched())

    @property
    def automation_enabled(self) -> bool:
        return self.main_widget.automation_switch.is_switched()

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
                title="Settings",
                content=self.main_widget.content,
                size="tiny",
            )
        return self._settings_modal

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
                self.run()

        return self._run_btn

    def save(self, enabled: Optional[bool] = None, agent_id: Optional[int] = None):
        """Save settings."""
        if enabled is None:
            enabled = self.main_widget.automation_switch.is_switched()
        if agent_id is None:
            agent_id = self.main_widget.agent_selector.get_value()

        self.main_widget.save_settings(enabled, agent_id)
        self._update_properties(enabled)

    def load_settings(self):
        """Load settings from DataJson."""
        self.main_widget.load_settings()
        self._update_properties(self.main_widget.automation_switch.is_switched())

    @property
    def model(self):
        if not hasattr(self, "_model"):
            raise RuntimeError("Model is not deployed.")
        return self._model

    @timeit
    def _deploy_model(self):
        try:
            agent_id = self.main_widget.agent_selector.get_value()
            if not agent_id:
                raise ValueError("Agent ID is not set. Please select an agent.")
            # agent_info = self.api.agent.get_info_by_id(agent_id)
            # kubernetes_settings = None
            # if agent_info.type == "kubernetes":
            #     kubernetes_settings = KubernetesSettings(limit_gpu_memory_mb=10000) # Example setting

            self._model = self.api.nn.deploy(
                model=self._model_path,
                workspace_id=self.project.workspace_id,
                agent_id=agent_id,
                task_name="Solution: " + str(self.api.task_id),
                # kubernetes_settings=kubernetes_settings,
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
    def eval_session_info(self) -> dict:
        if not hasattr(self, "_eval_session_info"):
            raise RuntimeError("Evaluation session info is not available.")
        return self._eval_session_info

    @timeit
    def _start_evaluator_session(self):
        module_id = self.api.app.get_ecosystem_module_id(self.APP_SLUG)
        task_info_json = self.api.task.start(
            agent_id=self.main_widget.agent_selector.get_value(),
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

    def run(self, skip_cb: bool = False):
        """
        Starts the evaluation process by deploying the model and starting the evaluator session.
        :param skip_cb: If True, skips the finish callbacks.
        """
        try:
            for cb in self._start_callbacks:
                try:
                    cb()
                except Exception as e:
                    logger.error(f"Error in start callback: {e}", exc_info=True)
            self.node.show_in_progress_badge("Evaluation")
            if not hasattr(self, "_model_path"):
                logger.warning(
                    "Model path is not set. Please set the model path before running the evaluation."
                )
                return
            # create threads for deployment and evaluation sessions and start them concurrently
            deploy_thread = threading.Thread(target=self._deploy_model)
            eval_thread = threading.Thread(target=self._start_evaluator_session)
            deploy_thread.start()
            eval_thread.start()

            # wait for both threads to finish
            deploy_thread.join()
            eval_thread.join()

            # send the evaluation request in a new thread
            thread = threading.Thread(target=self._run_evaluation, daemon=True)
            thread.start()
            thread.join()

            # # stop the evaluation and deployment tasks
            # self.api.task.stop(self.eval_session_info["id"])
            # self.api.task.stop(self.model.task_id)
        except Exception as e:
            logger.error(f"Failed to run evaluation: {e}", exc_info=True)
        finally:
            try:
                if hasattr(self, "_model"):
                    self.model.shutdown()
                    self._model = None
                    # self.api.task.stop(self.model.task_id)
            except Exception as e:
                logger.error(f"Failed to shutdown model: {e}", exc_info=True)

            try:
                if hasattr(self, "_eval_session_info"):
                    self.api.task.stop(self.eval_session_info["id"])
                    self._eval_session_info = {}
            except Exception as e:
                logger.error(f"Failed to stop evaluation session: {e}", exc_info=True)
            self.node.hide_in_progress_badge("Evaluation")
            if not skip_cb:
                for cb in self._finish_callbacks:
                    if not callable(cb):
                        logger.error(f"Finish callback {cb} is not callable.")
                        continue
                    try:
                        if cb.__code__.co_argcount == 1:
                            cb(self.res_dir)
                        else:
                            cb()
                    except Exception as e:
                        logger.error(f"Error in finish callback: {e}", exc_info=True)

    def _run_evaluation(self):
        self.res_dir = None
        if not hasattr(self, "_model") or not self._model:
            logger.error("Model is not deployed. Cannot run evaluation.")
            return
        if not hasattr(self, "_eval_session_info") or not self._eval_session_info:
            logger.error("Evaluation session info is not available. Cannot run evaluation.")
            return
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
        session_info["collectionName"] = self.collection.name if self.collection else "Unknown"

        error = response.get("error")
        res_dir = response.get("data")
        session_info["status"] = "Success" if not error else "Failed"
        self.task_history.add_task(session_info)
        if error:
            logger.error(f"Error during evaluation: {error}")
        elif res_dir:
            self.res_dir = res_dir

    def on_start(self, fn):
        """
        Decorator to register a callback function that will be called when the evaluation starts.
        """
        self._start_callbacks.append(fn)
        return fn

    def on_finish(self, fn):
        """
        Decorator to register a callback function that will be called when the evaluation finishes.
        """
        self._finish_callbacks.append(fn)
        return fn

    def set_model_path(self, model_path: str):
        self._model_path = model_path

    def _create_card(self) -> SolutionCard:
        card = SolutionCard(
            title="Re-evaluate on new validation dataset",
            tooltip=self._create_tooltip(),
            tooltip_position=self.tooltip_position,
            width=320,
            icon=self.icon,
        )

        @card.click
        def show_settings():
            self.settings_modal.show()

        return card

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        return SolutionCard.Tooltip(
            description="Re-evaluate the best model on a new validation dataset.",
            content=[self.run_btn, self.task_history_btn],
        )

    def _update_properties(self, enable: bool):
        """Update node properties with current settings."""
        value = "enabled" if enable else "disabled"
        self.node.update_property("Re-evaluate the best model", value, highlight=enable)
        if enable:
            self.node.show_automation_badge()
        else:
            self.node.hide_automation_badge()
