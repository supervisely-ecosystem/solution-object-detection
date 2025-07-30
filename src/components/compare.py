import datetime
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

import supervisely.io.env as sly_env
from supervisely._utils import abs_url
from supervisely.api.api import Api
from supervisely.app.content import DataJson
from supervisely.app.widgets import (
    AgentSelector,
    Button,
    Container,
    Field,
    Icons,
    InputNumber,
    SolutionCard,
    Switch,
    Widget,
)
from supervisely.app.widgets.dialog.dialog import Dialog
from supervisely.app.widgets.tasks_history.tasks_history import TasksHistory
from supervisely.io.fs import silent_remove
from supervisely.sly_logger import logger
from supervisely.solution.base_node import Automation, SolutionCardNode, SolutionElement


class ComparisonHistory(TasksHistory):

    def __init__(
        self,
        widget_id: str = None,
    ):
        super().__init__(widget_id=widget_id)
        self._table_columns = [
            "Task ID",
            "Created At",
            # "Input Evaluations",
            "Comparison Report",
            "Best checkpoint",
        ]
        self._columns_keys = [
            ["id"],
            ["created_at"],
            # ["evaluation_dirs"],
            ["result_link"],
            ["best_checkpoint"],
        ]

    def update(self):
        self.table.clear()
        for task in self._get_table_data():
            self.table.insert_row(task)

    def add_task(self, task: Dict[str, Any]) -> int:
        super().add_task(task)
        self.update()


class ComparisonGUI(Widget):
    def __init__(
        self,
        team_id: Optional[int] = None,
        widget_id: Optional[str] = None,
    ):
        self.team_id = team_id or sly_env.team_id()
        super().__init__(widget_id=widget_id)
        self.content = self._init_gui()

    @property
    def agent_selector(self) -> AgentSelector:
        if not hasattr(self, "_agent_selector"):
            self._agent_selector = AgentSelector(self.team_id)
        return self._agent_selector

    @property
    def automation_switch(self) -> Switch:
        if not hasattr(self, "_automation_switch"):
            self._automation_switch = Switch(switched=True)
        return self._automation_switch

    def _init_gui(self):
        agent_selector_field = Field(
            self.agent_selector,
            title="Select Agent to run task",
            description="Select the agent to run the model comparison task. GPU is not required.",
            icon=Field.Icon(
                zmdi_class="zmdi zmdi-storage",
                color_rgb=(21, 101, 192),
                bg_color_rgb=(227, 242, 253),
            ),
        )

        automation_field = Field(
            self.automation_switch,
            title="Enable Automation",
            description="Enable or disable automatic model comparison after each evaluation.",
            icon=Field.Icon(
                zmdi_class="zmdi zmdi-settings",
                color_rgb=(21, 101, 192),
                bg_color_rgb=(227, 242, 253),
            ),
        )

        return Container([agent_selector_field, automation_field], gap=20)

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
        """Set the state of widgets based on the provided parameters."""
        if enabled is True:
            self.automation_switch.on()
        elif enabled is False:
            self.automation_switch.off()
        else:
            pass  # do nothing, keep current state
        if agent_id is not None:
            self.agent_selector.set_value(agent_id)


class CompareNode(SolutionElement):
    APP_SLUG = "supervisely-ecosystem/model-benchmark"
    COMPARISON_ENDPOINT = "run_comparison"

    def __init__(
        self,
        api: Api,
        title: str,
        description: str,
        width: int = 250,
        x: int = 0,
        y: int = 0,
        team_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        *args,
        **kwargs,
    ):
        """A node for comparing evaluation reports of different models in Supervisely."""
        self.api = api
        self.team_id = team_id or sly_env.team_id()
        self.workspace_id = workspace_id or sly_env.workspace_id()
        self.title = title
        self.description = description
        self.width = width
        self.tooltip_position = tooltip_position
        self.icon = icon or Icons(
            class_name="zmdi zmdi-compare",
            color="#1976D2",
            bg_color="#E3F2FD",
        )
        super().__init__(*args, **kwargs)

        self._eval_dirs = []  # List of directories to compare

        self.result_dir = None
        self.result_link = None
        self.result_best_checkpoint = None

        self.tasks_history = ComparisonHistory()
        self.main_widget = ComparisonGUI(team_id=self.team_id)

        @self.main_widget.automation_switch.value_changed
        def on_automation_switch_change(value: bool):
            self.save(enabled=value)

        @self.main_widget.agent_selector.value_changed
        def on_agent_selector_change(value: int):
            self.save(agent_id=value)

        self.tasks_modal = Dialog(title="Comparison History", content=self.tasks_history)
        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.tasks_modal, self.settings_modal]
        self._finish_callbacks = []

        self._update_properties(self.main_widget.automation_switch.is_switched())

    @property
    def evaluation_dirs(self) -> List[str]:
        """
        Returns the list of evaluation directories.
        """
        return self._eval_dirs

    @evaluation_dirs.setter
    def evaluation_dirs(self, value: List[str]):
        """
        Sets the evaluation directories and enables the run button if directories are provided.
        """
        self._eval_dirs = value
        if value:
            self._run_btn.enable()
        else:
            self._run_btn.disable()

    @property
    def settings_modal(self) -> Dialog:
        """
        Returns the settings modal dialog for the Compare widget.
        """
        if not hasattr(self, "_settings_modal"):
            self._settings_modal = Dialog(
                title="Settings",
                content=self.main_widget.content,
                size="tiny",
            )
        return self._settings_modal

    def _create_card(self) -> SolutionCard:
        """
        Creates and returns the SolutionCard for the Compare widget.
        """
        card = SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            width=self.width,
            icon=self.icon,
            tooltip_position=self.tooltip_position,
        )

        @card.click
        def _on_card_click():
            self.settings_modal.show()

        return card

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        return SolutionCard.Tooltip(
            description=self.description, content=[self.run_btn, self.history_btn]
        )

    @property
    def run_btn(self) -> Button:
        if not hasattr(self, "_run_btn"):
            self._run_btn = Button(
                "Run manually",
                icon="zmdi zmdi-play",
                button_size="mini",
                plain=True,
                button_type="text",
            )

            @self._run_btn.click
            def run_comparison():
                self._run_btn.disable()
                self.run()
                self._run_btn.enable()

        return self._run_btn

    @property
    def history_btn(self) -> Button:
        if not hasattr(self, "_history_btn"):
            self._history_btn = Button(
                "History",
                icon="zmdi zmdi-format-list-bulleted",
                button_size="mini",
                plain=True,
                button_type="text",
            )

            @self._history_btn.click
            def show_history():
                self.tasks_modal.show()

        return self._history_btn

    def run_evaluator_session(self) -> Optional[Dict[str, Any]]:
        module_id = self.api.app.get_ecosystem_module_id(self.APP_SLUG)

        logger.info("Starting Model Benchmark Evaluator task...")
        task_info_json = self.api.task.start(
            agent_id=self.main_widget.agent_selector.get_value(),
            app_id=None,
            workspace_id=self.workspace_id,
            description=f"Solutions: {self.api.task_id}",
            module_id=module_id,
        )
        task_id = task_info_json["id"]

        current_time = time.time()
        while (task_status := self.api.task.get_status(task_id)) != self.api.task.Status.STARTED:
            logger.info("Waiting for the evaluation task to start... Status: %s", task_status)
            time.sleep(5)
            if time.time() - current_time > 300:  # 5 minutes timeout
                logger.warning("Timeout reached while waiting for the evaluation task to start.")
                break

        ready = self.api.app.wait_until_ready_for_api_calls(task_id, attempts=50)
        if not ready:
            raise RuntimeError(f"Task {task_id} is not ready for API calls.")

        return task_info_json

    def run(
        self,
    ):
        """
        Sends a request to the backend to start the evaluation process.
        """
        try:
            self.node.show_in_progress_badge("Comparison")
            if not self.evaluation_dirs:
                logger.warning("Not enough evaluation directories provided for comparison.")
            elif len(self.evaluation_dirs) == 1:
                logger.warning(
                    "Only one evaluation directory provided. Cannot compare. Using the single directory for results."
                )
                self.result_dir = self.evaluation_dirs[0]
                self.result_link = self._get_url_from_lnk_path(self.result_dir)
            else:
                task_info = self.run_evaluator_session()
                if task_info is None:
                    raise RuntimeError("Failed to start the evaluation task.")
                task_info["evaluation_dirs"] = self.evaluation_dirs
                task_id = task_info["id"]
                response = self.api.task.send_request(
                    task_id, self.COMPARISON_ENDPOINT, data={"eval_dirs": self.evaluation_dirs}
                )
                if "error" in response:
                    task_info["status"] = self.api.task.Status.ERROR
                    self.tasks_history.add_task(task_info)
                    raise RuntimeError(f"Error in evaluation request: {response['error']}")
                logger.info("Evaluation request sent successfully.")
                self.result_dir = response.get("data")
                self.result_link = self._get_url_from_lnk_path(self.result_dir)
                # @ todo: find the best checkpoint from the evaluation results
                # self._update_properties()
                task_info["status"] = "completed"
                task_info["result_dir"] = self.result_dir
                task_info["result_link"] = abs_url(self.result_link)
                self.tasks_history.add_task(task_info)
                self.api.task.stop(task_id)
                logger.info(f"Evaluation completed successfully. Task ID: {task_id}")
        except Exception as e:
            logger.error(f"Evaluation failed. {e}", exc_info=True)
        finally:
            self.node.hide_in_progress_badge("Comparison")
            for cb in self._finish_callbacks:
                try:
                    cb(self.result_dir, self.result_link)
                except Exception as e:
                    logger.error(f"Error in finish callback: {e}", exc_info=True)

    def get_available_agent_id(self) -> Optional[int]:
        agents = self.api.agent.get_list_available(self.team_id, True)
        return agents[0].id if agents else None

    def on_finish(self, fn):
        """
        Decorator to register a callback to be called with result_dir when comparison finishes.
        """
        self._finish_callbacks.append(fn)
        return fn

    def _get_url_from_lnk_path(self, remote_lnk_dir: str) -> str:
        remote_lnk_path = remote_lnk_dir + "/Model Comparison Report.lnk"
        if not self.api.file.exists(self.team_id, remote_lnk_path):
            logger.warning(
                f"Link file {remote_lnk_path} does not exist in the benchmark directory."
            )
            return ""

        self.api.file.download(self.team_id, remote_lnk_path, "./model_evaluation_report.lnk")
        with open("./model_evaluation_report.lnk", "r") as file:
            base_url = file.read().strip()

        silent_remove("./model_evaluation_report.lnk")

        return base_url

    def _update_properties(self, enable: bool):
        """Update node properties with current settings."""
        value = "enabled" if enable else "disabled"
        self.node.update_property("Compare models", value, highlight=enable)
        if enable:
            self.node.show_automation_badge()
        else:
            self.node.hide_automation_badge()

    def is_new_model_better(self, primary_metric: str) -> bool:
        """
        Compares the primary metrics of two checkpoints.
        Returns "better", "worse", or "equal".
        """
        if not primary_metric:
            raise ValueError("Primary metric must be provided for comparison.")

        if len(self.evaluation_dirs) != 2:
            # raise ValueError("Evaluation directories not set or not enough for comparison.")
            logger.warning(f"Evaluation directories != 2: {self.evaluation_dirs}")
            if len(self.evaluation_dirs) < 2:
                logger.warning("Not enough evaluation directories provided for comparison.")
                return False

        metric_old, _ = self._get_info_from_experiment(primary_metric, self.evaluation_dirs[0])
        metric_new, new_checkpoint_path = self._get_info_from_experiment(
            primary_metric, self.evaluation_dirs[-1]
        )
        if metric_old is None or metric_new is None:
            raise ValueError(f"Primary metric '{primary_metric}' not found in evaluation results.")

        # Compare metrics (assuming higher is better)
        new_model_better = metric_new > metric_old
        if new_model_better:
            logger.info(f"{primary_metric} of new model is better: {metric_new} > {metric_old}")
            if new_checkpoint_path:
                logger.info(f"New best checkpoint path: {new_checkpoint_path}")
                self.result_best_checkpoint = str(new_checkpoint_path)
                self.evaluation_dirs = [self.evaluation_dirs[-1]]
        else:
            logger.info(f"{primary_metric} of new model is worse: {metric_new} <= {metric_old}")
            self.result_best_checkpoint = None
            self.evaluation_dirs = [self.evaluation_dirs[0]]
        return new_model_better

    def _get_experiments_path(self, path: str) -> str:
        """
        Returns the experiments path for the given evaluation directory.

        from "/model-benchmark/73_sample COCO/7958_Train YOLO v8 - v12/"
        to "/experiments/73_sample COCO/7958_YOLO/experiment_info.json"
        """
        parts = path.strip("/").split("/")
        if len(parts) < 3:
            raise ValueError(f"Invalid evaluation directory path: {path}")
        project_name = parts[1]
        experiment_name = parts[2].replace("Train ", "").split(" ")[0]
        return f"/experiments/{project_name}/{experiment_name}/experiment_info.json"

    def _get_info_from_experiment(
        self, metric_name: str, evaluation_dir: str
    ) -> Tuple[Optional[float], Optional[str]]:
        """
        Returns the value of the specified metric from the evaluation results.
        """
        data_path = self._get_experiments_path(evaluation_dir)
        if not self.api.storage.exists(self.team_id, data_path):
            raise ValueError(f"Not found experiment_info: {data_path}")

        temp_file = tempfile.NamedTemporaryFile(mode="w+", suffix=".json", delete=False)
        metric, best_checkpoint_path = None, None
        try:
            self.api.storage.download(self.team_id, data_path, temp_file.name)
            with open(temp_file.name, "r") as f:
                data = json.load(f)
                metric = data.get("evaluation_metrics", {}).get(metric_name, None)
                artifacts_dir = data.get("artifacts_dir")
                best_checkpoint = data.get("best_checkpoint")
                if artifacts_dir and best_checkpoint:
                    best_checkpoint_path = Path(artifacts_dir) / "checkpoints" / best_checkpoint
        finally:
            if os.path.exists(temp_file.name):
                silent_remove(temp_file.name)
        return metric, best_checkpoint_path

    def save(self, enabled: Optional[bool] = None, agent_id: Optional[int] = None):
        """Save re-deploy settings."""
        if enabled is None:
            enabled = self.main_widget.automation_switch.is_switched()
        if agent_id is None:
            agent_id = self.main_widget.agent_selector.get_value()

        self.main_widget.save_settings(enabled, agent_id)
        self._update_properties(enabled)

    def load_settings(self):
        """Load re-deploy settings from DataJson."""
        self.main_widget.load_settings()
        self._update_properties(self.main_widget.automation_switch.is_switched())

    def is_enabled(self) -> bool:
        """Check if re-deploy is enabled."""
        return self.main_widget.automation_switch.is_switched()
