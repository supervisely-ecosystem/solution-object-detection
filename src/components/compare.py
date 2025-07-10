import datetime
import time
from typing import Any, Callable, Dict, List, Literal, Optional, Union
from uuid import uuid4

import supervisely as sly
from supervisely.app.content import DataJson
from supervisely.app.widgets import (
    Button,
    Container,
    Field,
    Icons,
    InputNumber,
    NotificationBox,
    SolutionCard,
    Switch,
)
from supervisely.app.widgets.dialog.dialog import Dialog
from supervisely.app.widgets.tasks_history.tasks_history import TasksHistory
from supervisely.solution.base_node import Automation, SolutionCardNode, SolutionElement


class ComparisonTasksHistory(TasksHistory):
    def __init__(self, api: sly.Api, widget_id: str = None):
        super().__init__(api, widget_id=widget_id)
        self._table_columns = [
            "ID",
            "App Name",
            "Started At",
            "Status",
        ]
        self._columns_keys = [
            ["id"],
            ["meta", "app", "name"],
            ["started_at"],
            ["status"],
        ]

    def _taskinfo_to_dict(self, task_info: Dict[str, Any]) -> Dict[str, Any]:
        task_status_to_badge = {
            "started": "Started ⚡",
            "error": "Error ❌",
            "finished": "Finished ✅",
            "stopped": "Stopped ⏹️",
        }

        return {
            "id": task_info["id"],
            "name": task_info["meta"]["app"]["name"],
            "started_at": task_info["startedAt"],
            "status": task_status_to_badge.get(
                task_info["status"], task_info["status"].capitalize()
            ),
        }

    def update(self):
        self.table.clear()
        for task in self.get_tasks():
            task_info = self.api.task.get_info_by_id(task["id"])
            self.table.insert_row(list(self._taskinfo_to_dict(task_info).values()))

    def add_task(self, task: Dict[str, Any]):
        super().add_task(task)
        self.update()


class ComparisonItem:
    def __init__(
        self,
        comparison_id: int,
        task_id: int,
        input_evals: Union[List[str], str],
        result_folder: str,
        best_checkpoint: str,
        created_at: str = None,
    ):
        """
        Initialize a comparison item with task ID, input evaluations, result folder, best checkpoint, and creation time.
        """
        self.comparison_id = comparison_id
        self.task_id = task_id
        self.input_evals = input_evals if isinstance(input_evals, list) else [input_evals]
        self.result_folder = result_folder
        self.best_checkpoint = best_checkpoint
        self.created_at = created_at or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_json(self) -> Dict[str, Any]:
        """Convert the comparison item to a JSON serializable format."""
        return {
            "id": self.comparison_id,
            "created_at": self.created_at,
            "task_id": self.task_id,
            "input_evals": ", ".join(self.input_evals),
            "result_folder": self.result_folder,
            "best_checkpoint": self.best_checkpoint,
        }


class ComparisonHistory(TasksHistory):
    def __init__(
        self,
        widget_id: str = None,
    ):
        super().__init__(widget_id=widget_id)
        self._remove_unused_args()
        self._table_columns = [
            "ID",
            "Created At",
            "Task ID",
            "Input Evaluations",
            "Result Folder",
            "Best checkpoint",
        ]
        self._columns_keys = [
            ["id"],
            ["created_at"],
            ["task_id"],
            ["input_evals"],
            ["result_folder"],
            ["best_checkpoint"],
        ]

    def update(self):
        self.table.clear()
        for comparison in self.get_tasks():
            self.table.insert_row(list(comparison.values()))

    def add_task(self, task: Union[ComparisonItem, Dict[str, Any]]) -> int:
        if isinstance(task, ComparisonItem):
            task = task.to_json()
        super().add_task(task)
        self.update()

    def _remove_unused_args(self):
        """
        Removes unused arguments from the class to avoid confusion.
        """
        unused_args = [
            "api",
            "_stop_autorefresh",
            "_refresh_thread",
            "_refresh_interval",
        ]
        for arg in unused_args:
            if hasattr(self, arg):
                delattr(self, arg)

        unused_fns = [
            "_autorefresh",
            "stop_autorefresh",
            "start_autorefresh",
        ]
        notimplemented_text = "Method not implemented in %s.".format(self.__class__.__name__)
        for fn in unused_fns:
            setattr(self, fn, lambda *args, **kwargs: sly.logger.error(notimplemented_text))


class ComparisonAutomation(Automation):
    """
    Automation for running model comparison evaluations.
    """

    def __init__(self, func: Callable):
        super().__init__()
        self.job_id = f"compare_models_{uuid4()}"
        self.func = func

    def apply(self, sec: int, *args) -> None:
        self.scheduler.add_job(
            self.func, interval=sec, job_id=self.job_id, replace_existing=True, *args
        )
        sly.logger.info(
            f"Scheduled model comparison job with ID {self.job_id} every {sec} seconds."
        )

    def remove(self):
        if self.scheduler.is_job_scheduled(self.job_id):
            self.scheduler.remove_job(self.job_id)
            sly.logger.info(f"Removed scheduled job: {self.job_id}")
        else:
            sly.logger.warning(f"Job {self.job_id} is not scheduled, cannot remove it.")

    @property
    def is_scheduled(self) -> bool:
        """
        Check if the automation job is scheduled.
        """
        return self.scheduler.is_job_scheduled(self.job_id)


class CompareNode(SolutionElement):
    APP_SLUG = "supervisely-ecosystem/model-benchmark"
    COMPARISON_ENDPOINT = "run_comparison"

    def __init__(
        self,
        api: sly.Api,
        project_info: sly.ProjectInfo,
        title: str,
        description: str,
        width: int = 250,
        x: int = 0,
        y: int = 0,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        agent_id: Optional[int] = None,
        evaluation_dirs: Optional[list[str]] = None,
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
        self.icon = icon or self._get_default_icon()
        super().__init__(*args, **kwargs)

        self.tooltip_position = tooltip_position
        self.eval_dirs = evaluation_dirs

        self.result_comparison_dir = None
        self.result_comparison_link = None
        self.result_best_checkpoint = None

        self.agent_id = agent_id or self.get_available_agent_id()
        if self.agent_id is None:
            raise ValueError("No available agent found. Please check your agents.")

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [
            self.automation_modal,
            self.comparison_history_modal,
            self.tasks_history_modal,
            self.tasks_history.logs_modal,
        ]

        self._finish_callbacks = []

    @property
    def is_automated(self) -> bool:
        """
        Returns whether the comparison is automated.
        """
        return DataJson()[self.widget_id].get("automation_settings", {}).get("is_automated", False)

    @property
    def automation_interval(self) -> int:
        """
        Returns the automation interval in seconds.
        """
        return (
            DataJson()[self.widget_id]
            .get("automation_settings", {})
            .get("automation_interval", 600)
        )

    @property
    def evaluation_dirs(self) -> list[str]:
        """
        Returns the list of evaluation directories.
        """
        return self.eval_dirs

    @evaluation_dirs.setter
    def evaluation_dirs(self, value: list[str]):
        """
        Sets the evaluation directories and enables the run button if directories are provided.
        """
        self.eval_dirs = value
        if value:
            self._run_btn.enable()
        else:
            self._run_btn.disable()

        # self.show_warning = self.eval_dirs is None or len(self.eval_dirs) < 2
        # self.warning.show() if self.show_warning else self.warning.hide()

    @property
    def automation_modal(self) -> Dialog:
        """
        Returns the automation modal dialog.
        """
        if not hasattr(self, "_automation_modal"):
            self._automation_modal = self._init_automation_modal()
        return self._automation_modal

    @property
    def automation(self) -> ComparisonAutomation:
        """
        Returns the automation instance for periodic comparison.
        """
        if not hasattr(self, "_automation"):
            self._automation = ComparisonAutomation(self.send_comparison_request)
        return self._automation

    @property
    def comparison_history_modal(self) -> Dialog:
        """
        Returns the comparison history modal dialog.
        """
        if not hasattr(self, "_comparison_history_modal"):
            self._comparison_history_modal = Dialog(
                "Comparison History", self.comparison_history, "small"
            )
        return self._comparison_history_modal

    @property
    def comparison_history(self) -> ComparisonHistory:
        """
        Returns the comparison history instance.
        """
        if not hasattr(self, "_comparison_history"):
            self._comparison_history = ComparisonHistory()
        return self._comparison_history

    @property
    def tasks_history_modal(self) -> Dialog:
        """
        Returns the task history modal dialog.
        """
        if not hasattr(self, "_tasks_history_modal"):
            self._tasks_history_modal = Dialog("Tasks History", self.tasks_history, "small")
        return self._tasks_history_modal

    @property
    def tasks_history(self) -> ComparisonTasksHistory:
        """
        Returns the tasks history instance.
        """
        if not hasattr(self, "_tasks_history"):
            self._tasks_history = ComparisonTasksHistory(self.api)
        return self._tasks_history

    def _init_automation_modal(self) -> Dialog:
        automation_switch = Switch(False)
        self._get_automation_switch_value = automation_switch.is_switched
        automation_periodic_input = InputNumber(600, min=60, max=3600, step=15)
        self._get_automation_interval = automation_periodic_input.get_value
        automation_periodic_input.disable()
        interval_field = Field(
            automation_periodic_input,
            "Interval (seconds)",
            "Set the interval for periodic comparison.",
        )
        apply_btn = Button(
            "Apply settings",
            button_type="primary",
        )
        apply_btn.disable()
        automation_modal_layout = Container(
            [
                Field(
                    automation_switch,
                    "Periodic comparison",
                    "Configure whether you want to automate the comparison process.",
                ),
                interval_field,
                apply_btn,
                Field(Container(), "Conditional comparison", "Not implemented yet."),
            ]
        )
        automation_modal = Dialog("Automation Settings", automation_modal_layout, "tiny")

        @automation_switch.value_changed
        def automation_switch_change_cb(is_on: bool):
            if is_on:
                automation_periodic_input.enable()
                apply_btn.enable()
            else:
                automation_periodic_input.disable()
                apply_btn.disable()
                if self.automation.is_scheduled:
                    self.automation.remove()
                    sly.logger.info("Periodic comparison automation disabled.")
                self.save()
                self.hide_automated_badge()
                self._update_properties()

        @apply_btn.click
        def enable_automation():
            sec = automation_periodic_input.get_value()
            self.automation.apply(sec)
            sly.logger.info(f"Scheduled periodic comparison every {sec} seconds.")
            self.save()
            self._update_properties()
            self.show_automated_badge()
            automation_modal.hide()

        return automation_modal

    def save(self) -> None:
        """
        Saves the current state of the CompareNode.
        """
        DataJson()[self.widget_id]["automation_settings"][
            "is_automated"
        ] = self._get_automation_switch_value()
        DataJson()[self.widget_id]["automation_settings"][
            "automation_interval"
        ] = self._get_automation_interval()
        DataJson().send_changes()

    def _create_card(self) -> SolutionCard:
        """
        Creates and returns the SolutionCard for the Compare widget.
        """
        # content = [self.warning, self.failed_notification]
        return SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            # content=content,
            width=self.width,
            icon=self.icon,
            tooltip_position=self.tooltip_position,
        )

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        properties = [
            {
                "key": "Best model",
                "value": "Unknown",
                "highlight": True,
                "link": False,
            },
            {"key": "Automatic re-deployment", "value": "✖", "highlight": False, "link": False},
        ]
        return SolutionCard.Tooltip(
            description=self.description, content=self._get_buttons(), properties=properties
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
                self.send_comparison_request()
                self._run_btn.enable()

        if not hasattr(self, "_automate_btn"):
            self._automate_btn = Button(
                "Automate",
                icon="zmdi zmdi-settings",
                button_size="mini",
                plain=True,
                button_type="text",
            )
            self._automate_btn.click(self.automation_modal.show)
        if not hasattr(self, "_comparison_history_btn"):
            self._comparison_history_btn = Button(
                "Comparison history (reports)",
                icon="zmdi zmdi-format-list-bulleted",
                button_size="mini",
                plain=True,
                button_type="text",
            )
            self._comparison_history_btn.click(self.comparison_history_modal.show)
        if not hasattr(self, "_tasks_history_btn"):
            self._tasks_history_btn = Button(
                "Tasks history (logs)",
                icon="zmdi zmdi-format-list-bulleted",
                button_size="mini",
                plain=True,
                button_type="text",
            )
            self._tasks_history_btn.click(self.tasks_history_modal.show)
        return [
            self._automate_btn,
            self._run_btn,
            self._comparison_history_btn,
            self._tasks_history_btn,
        ]

    def _get_first_available_session(self, module_id: int) -> Optional[Dict[str, Any]]:
        """
        Returns the first available session for the Model Benchmark Evaluator.
        If no session is available, returns None.
        """
        sessions = self.api.app.get_sessions(
            self.team_id, module_id, statuses=[self.api.task.Status.STARTED]
        )
        return next(iter(sessions), None)

    def _taskinfo_to_dict(self, task_info: Dict[str, Any]) -> Dict[str, Any]:
        task_status_to_badge = {
            "started": "Started ⚡",
            "error": "Error ❌",
            "finished": "Finished ✅",
            "stopped": "Stopped ⏹️",
        }

        return {
            "id": task_info["id"],
            "name": task_info["meta"]["app"]["name"],
            "started_at": task_info["startedAt"],
            "status": task_status_to_badge.get(
                task_info["status"], task_info["status"].capitalize()
            ),
        }

    def run_evaluator_session_if_needed(self):
        module_id = self.api.app.get_ecosystem_module_id(self.APP_SLUG)
        available_session = self._get_first_available_session(module_id)
        if available_session is not None:
            sly.logger.info("Model Benchmark Evaluator session is already running, skipping start.")
            task_info = self.api.task.get_info_by_id(available_session.task_id)
            self.tasks_history.add_task(self._taskinfo_to_dict(task_info))
            return available_session.task_id

        sly.logger.info("Starting Model Benchmark Evaluator task...")
        task_info_json = self.api.task.start(
            agent_id=self.agent_id,
            app_id=None,
            workspace_id=self.workspace_id,
            description=f"Solutions: {self.api.task_id}",
            module_id=module_id,
        )
        if task_info_json is None:
            raise RuntimeError("Failed to start the evaluation task.")
        self.tasks_history.add_task(self._taskinfo_to_dict(task_info))
        task_id = task_info_json["taskId"]

        current_time = time.time()
        while task_status := self.api.task.get_status(task_id) != self.api.task.Status.STARTED:
            sly.logger.info("Waiting for the evaluation task to start... Status: %s", task_status)
            time.sleep(5)
            if time.time() - current_time > 300:  # 5 minutes timeout
                sly.logger.warning(
                    "Timeout reached while waiting for the evaluation task to start."
                )
                break

        return task_id

    def send_comparison_request(self):
        """
        Sends a request to the backend to start the evaluation process.
        """
        # self.warning.hide()
        self.hide_failed_badge()
        self.hide_running_badge()
        self.hide_finished_badge()
        if not self.eval_dirs or len(self.eval_dirs) < 2:
            sly.logger.warning("Not enough evaluation directories provided for comparison.")
            self.show_failed_badge()
            # self.warning.show()
            return
        self.show_running_badge()
        try:
            # raise RuntimeError("This is a test error to check error handling.")
            task_id = self.run_evaluator_session_if_needed()
            response = self.api.task.send_request(
                task_id, self.COMPARISON_ENDPOINT, data={"eval_dirs": self.eval_dirs}
            )
            if "error" in response:
                raise RuntimeError(f"Error in evaluation request: {response['error']}")
            sly.logger.info("Evaluation request sent successfully.")
            self.result_comparison_dir = response.get("data")
            self.result_comparison_link = self._get_url_from_lnk_path(
                self.result_comparison_dir + "/Model Comparison Report.lnk"
            )
            # @todo: find the best checkpoint from the evaluation results
            # self._update_properties()
            comparison_id = int(self.result_comparison_link.split("id=")[-1])
            comparison = ComparisonItem(
                comparison_id,
                task_id,
                self.eval_dirs,
                self.result_comparison_dir,
                self.result_best_checkpoint,
            )
            self.comparison_history.add_task(comparison)
            for cb in self._finish_callbacks:
                cb(self.result_comparison_dir, self.result_comparison_link)
            self.show_finished_badge()
            self.hide_running_badge()
        except:
            sly.logger.error("Evaluation failed.", exc_info=True)
            self.show_failed_badge()
            self.hide_running_badge()

    def get_available_agent_id(self) -> int:
        agents = self.api.agent.get_list_available(self.team_id, True)
        return agents[0].id if agents else None

    def on_finish(self, fn):
        """
        Decorator to register a callback to be called with result_dir when comparison finishes.
        """
        self._finish_callbacks.append(fn)
        return fn

    def _get_url_from_lnk_path(self, remote_lnk_path) -> str:
        if not self.api.file.exists(self.team_id, remote_lnk_path):
            sly.logger.warning(
                f"Link file {remote_lnk_path} does not exist in the benchmark directory."
            )
            return ""

        self.api.file.download(self.team_id, remote_lnk_path, "./model_evaluation_report.lnk")
        with open("./model_evaluation_report.lnk", "r") as file:
            base_url = file.read().strip()

        sly.fs.silent_remove("./model_evaluation_report.lnk")

        return sly.utils.abs_url(base_url)

    def show_running_badge(self):
        """
        Updates the card to show that the evaluation is running.
        """
        self.card.update_badge_by_key(
            key="In Progress", label="⚡", plain=True, badge_type="warning"
        )
        self._run_btn.disable()

    def hide_running_badge(self):
        """
        Hides the running badge from the card.
        """
        self.card.remove_badge_by_key(key="In Progress")
        self._run_btn.enable()

    def show_finished_badge(self):
        """
        Updates the card to show that the comparison is finished.
        """
        self.card.update_badge_by_key(key="Finished", label="✅", plain=True, badge_type="success")
        self._run_btn.disable()

    def hide_finished_badge(self):
        """
        Hides the finished badge from the card.
        """
        self.card.remove_badge_by_key(key="Finished")
        self._run_btn.enable()

    def show_failed_badge(self):
        """
        Updates the card to show that the comparison has failed.
        """
        self.card.update_badge_by_key(key="Failed", label="❌", plain=True, badge_type="error")
        # self.failed_notification.show()

    def hide_failed_badge(self):
        """
        Hides the failed badge from the card.
        """
        self.card.remove_badge_by_key(key="Failed")
        # self.failed_notification.hide()

    def show_automated_badge(self):
        """
        Updates the card to show that the comparison is automated.
        """
        self.card.update_badge_by_key(key="Automated", label="🤖", plain=True, badge_type="success")

    def hide_automated_badge(self):
        """
        Hides the automated badge from the card.
        """
        self.card.remove_badge_by_key(key="Automated")

    def _get_default_icon(self) -> Icons:
        icon_color, bg_color = self._random_pretty_color()
        return Icons(
            class_name="zmdi zmdi-compare",
            color=icon_color,
            bg_color=bg_color,
        )

    def _random_pretty_color(self) -> str:
        import colorsys
        import random

        icon_color_hsv = (random.random(), random.uniform(0.6, 0.9), random.uniform(0.4, 0.7))
        icon_color_rgb = colorsys.hsv_to_rgb(*icon_color_hsv)
        icon_color_hex = "#{:02X}{:02X}{:02X}".format(*[int(c * 255) for c in icon_color_rgb])

        bg_color_hsv = (
            icon_color_hsv[0],
            icon_color_hsv[1] * 0.3,
            min(icon_color_hsv[2] + 0.4, 1.0),
        )
        bg_color_rgb = colorsys.hsv_to_rgb(*bg_color_hsv)
        bg_color_hex = "#{:02X}{:02X}{:02X}".format(*[int(c * 255) for c in bg_color_rgb])

        return icon_color_hex, bg_color_hex

    def _update_properties(self):
        new_propetries = [
            {
                "key": "Best model",
                "value": self.result_best_checkpoint or "Unknown",
                "highlight": True,
                "link": False,
            },
            {
                "key": "Automatic re-deployment",
                "value": "✔️" if self.is_automated else "✖",
                "highlight": False,
                "link": False,
            },
        ]
        for prop in new_propetries:
            self.card.update_property(**prop)
