import datetime
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

from supervisely._utils import abs_url
from supervisely.api.api import Api
from supervisely.api.project_api import ProjectInfo
from supervisely.app.content import DataJson
from supervisely.app.widgets import (
    Button,
    Container,
    Field,
    Icons,
    InputNumber,
    SolutionCard,
    Switch,
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


class ComparisonAutomation(Automation):
    """
    Automation for running model comparison evaluations.
    """

    def __init__(self, func: Callable):
        super().__init__()
        self.func = func
        self.widget = self._create_widget()
        self.job_id = self.widget.widget_id

    def get_automation_details(self) -> Tuple[bool, int]:
        """
        Returns the automation status and interval.
        """
        automation_settings = DataJson()[self.widget_id].get("automation_settings", {})
        is_automated = automation_settings.get("is_automated", False)
        automation_interval = automation_settings.get("automation_interval", 600)
        return is_automated, automation_interval

    def _create_widget(self) -> Container:
        self.automation_switch = Switch(False)
        self.automation_periodic_input = InputNumber(600, min=60, max=3600, step=15)
        self.automation_periodic_input.disable()
        interval_field = Field(
            self.automation_periodic_input,
            "Interval (seconds)",
            "Set the interval for periodic comparison.",
        )
        self.apply_btn = Button("Save")
        automation_modal_layout = Container(
            [
                Field(
                    self.automation_switch,
                    "Periodic comparison",
                    "Configure whether you want to automate the comparison process.",
                ),
                interval_field,
                self.apply_btn,
                Field(Container(), "Conditional comparison", "Not implemented yet."),
            ]
        )

        @self.automation_switch.value_changed
        def automation_switch_change_cb(is_on: bool):
            if is_on:
                self.automation_periodic_input.enable()
            else:
                self.automation_periodic_input.disable()

        return automation_modal_layout

    @property
    def modal(self) -> Dialog:
        """
        Returns the automation modal dialog.
        """
        if not hasattr(self, "_automation_modal"):
            self._automation_modal = Dialog("Automation Settings", self.widget, "tiny")
        return self._automation_modal

    def apply(self, sec: int, *args) -> None:
        self.scheduler.add_job(
            self.func, interval=sec, job_id=self.job_id, replace_existing=True, *args
        )
        logger.info(f"Scheduled model comparison job with ID {self.job_id} every {sec} seconds.")

    def remove(self):
        if self.scheduler.is_job_scheduled(self.job_id):
            self.scheduler.remove_job(self.job_id)
            logger.info(f"Removed scheduled job: {self.job_id}")
        else:
            logger.warning(f"Job {self.job_id} is not scheduled, cannot remove it.")

    @property
    def is_scheduled(self) -> bool:
        """
        Check if the automation job is scheduled.
        """
        return self.scheduler.is_job_scheduled(self.job_id)

    def save(self) -> None:
        """
        Save the current state of the automation settings.
        """
        DataJson()[self.widget_id]["automation_settings"] = {
            "is_automated": self._get_automation_switch_value(),
            "automation_interval": self._get_automation_interval(),
        }
        DataJson().send_changes()
        logger.info("Automation settings saved.")


class CompareNode(SolutionElement):
    APP_SLUG = "supervisely-ecosystem/model-benchmark"
    COMPARISON_ENDPOINT = "run_comparison"

    def __init__(
        self,
        api: Api,
        project_info: ProjectInfo,
        title: str,
        description: str,
        width: int = 250,
        x: int = 0,
        y: int = 0,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        agent_id: Optional[int] = None,
        *args,
        **kwargs,
    ):
        """A node for comparing evaluation reports of different models in Supervisely."""
        self.api = api
        self.project = project_info
        self.team_id = project_info.team_id
        self.workspace_id = project_info.workspace_id
        self.title = title
        self.description = description
        self.width = width
        self.icon = icon or Icons(
            class_name="zmdi zmdi-compare",
            color="#1976D2",
            bg_color="#E3F2FD",
        )
        super().__init__(*args, **kwargs)

        self.tooltip_position = tooltip_position
        self._eval_dirs = []  # List of directories to compare

        self.result_dir = None
        self.result_link = None
        self.result_best_checkpoint = None

        self.agent_id = agent_id or self.get_available_agent_id()
        if self.agent_id is None:
            raise ValueError("No available agent found. Please check your agents.")

        self.automation = ComparisonAutomation(self.run)
        self.tasks_history = ComparisonHistory()
        self.tasks_modal = Dialog(title="Comparison History", content=self.tasks_history)
        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.tasks_modal, self.automation.modal]

        self._finish_callbacks = []

        @self.automation.apply_btn.click
        def enable_automation():
            self.automation_modal.hide()
            enabled, sec = self.automation.get_automation_details()
            if not enabled:
                logger.info("Periodic comparison automation disabled.")
                self.automation.scheduler.remove_job(self.job_id)
                self.node.hide_automation_badge()
            else:
                self.automation.apply(sec)
                logger.info(f"Scheduled periodic comparison every {sec} seconds.")
            self.node.show_automation_badge()

            self.automation.save()

    @property
    def is_automated(self) -> bool:
        """
        Returns whether the comparison is automated.
        """
        is_automated, _ = self.automation.get_automation_details()
        return is_automated

    @property
    def automation_interval(self) -> int:
        """
        Returns the automation interval in seconds.
        """
        _, automation_interval = self.automation.get_automation_details()
        return automation_interval

    @property
    def evaluation_dirs(self) -> list[str]:
        """
        Returns the list of evaluation directories.
        """
        return self._eval_dirs

    @evaluation_dirs.setter
    def evaluation_dirs(self, value: list[str]):
        """
        Sets the evaluation directories and enables the run button if directories are provided.
        """
        self._eval_dirs = value
        if value:
            self._run_btn.enable()
        else:
            self._run_btn.disable()

    def _create_card(self) -> SolutionCard:
        """
        Creates and returns the SolutionCard for the Compare widget.
        """
        return SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            width=self.width,
            icon=self.icon,
            tooltip_position=self.tooltip_position,
        )

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        return SolutionCard.Tooltip(
            description=self.description, content=self._get_buttons()
        )

    def _get_buttons(self):
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

        if not hasattr(self, "_automate_btn"):
            self._automate_btn = Button(
                "Automate",
                icon="zmdi zmdi-settings",
                button_size="mini",
                plain=True,
                button_type="text",
            )
            self._automate_btn.click(self.automation.modal.show)
        if not hasattr(self, "_tasks_history_btn"):
            self._tasks_history_btn = Button(
                "Tasks History",
                icon="zmdi zmdi-format-list-bulleted",
                button_size="mini",
                plain=True,
                button_type="text",
            )
            self._tasks_history_btn.click(self.tasks_modal.show)
        return [
            self._run_btn,
            self._automate_btn,
            self._tasks_history_btn,
        ]

    def run_evaluator_session(self) -> Optional[int]:
        module_id = self.api.app.get_ecosystem_module_id(self.APP_SLUG)

        logger.info("Starting Model Benchmark Evaluator task...")
        task_info_json = self.api.task.start(
            agent_id=self.agent_id,
            app_id=None,
            workspace_id=self.workspace_id,
            description=f"Solutions: {self.api.task_id}",
            module_id=module_id,
        )
        task_id = task_info_json["id"]

        current_time = time.time()
        while task_status := self.api.task.get_status(task_id) != self.api.task.Status.STARTED:
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
        if len(self.evaluation_dirs) < 2:
            logger.warning("Not enough evaluation directories provided for comparison.")
            return
        try:
            task_info = self.run_evaluator_session()
            task_info["evaluation_dirs"] = self.evaluation_dirs
            if task_info is None:
                task_info["status"] = self.api.task.Status.ERROR
                self.tasks_history.add_task(task_info)
                raise RuntimeError("Failed to start the evaluation task.")
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
            for cb in self._finish_callbacks:
                cb(self.result_dir, self.result_link)
            self.api.task.stop(task_id)
            logger.info(f"Evaluation completed successfully. Task ID: {task_id}")
        except Exception as e:
            logger.error(f"Evaluation failed. {e}", exc_info=True)

    def get_available_agent_id(self) -> int:
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

    def _update_properties(self):
        pass

    def is_new_model_better(self, primary_metric: str) -> bool:
        """
        Compares the primary metrics of two checkpoints.
        Returns "better", "worse", or "equal".
        """
        if not primary_metric:
            raise ValueError("Primary metric must be provided for comparison.")

        if len(self.evaluation_dirs) != 2:
            raise ValueError("Evaluation directories not set or not enough for comparison.")

        metric_old, _ = self._get_info_from_experiment(primary_metric, self.evaluation_dirs[0])
        metric_new, new_checkpoint_path = self._get_info_from_experiment(
            primary_metric, self.evaluation_dirs[1]
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
