import datetime
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

from src.components.send_email.send_email import SendEmail
from supervisely._utils import is_development
from supervisely.api.api import Api
from supervisely.app.content import DataJson
from supervisely.app.widgets import (
    Button,
    CheckboxField,
    Container,
    Icons,
    SolutionCard,
)
from supervisely.app.widgets.dialog.dialog import Dialog
from supervisely.app.widgets.tasks_history.tasks_history import TasksHistory
from supervisely.sly_logger import logger
from supervisely.solution.base_node import Automation, SolutionCardNode, SolutionElement


class SendEmailAutomation(Automation):

    def __init__(self, func: Callable):
        super().__init__()
        self.func = func
        self.widget = self._create_widget()
        self.job_id = self.widget.widget_id
        self.modals = [self.modal]

    def _create_widget(self) -> Container:
        checkbox = CheckboxField(
            title="After Comparison",
            description="Enable to send an email after each comparison.",
            checked=False,
        )
        self.apply_button = Button("Apply")
        self.is_email_sending_enabled = lambda: checkbox.is_checked()

        return Container([checkbox, self.apply_button])

    @property
    def modal(self) -> Dialog:
        """
        Returns the automation modal dialog.
        """
        if not hasattr(self, "_automation_modal"):
            self._automation_modal = Dialog("Automation Settings", self.widget, "tiny")
        return self._automation_modal

    def save(self) -> None:
        """
        Save the current state of the automation settings.
        """
        DataJson()[self.widget_id]["is_email_sending_enabled"] = self.is_email_sending_enabled()
        DataJson().send_changes()
        logger.info("Automation settings saved.")


class SendEmailHistory(TasksHistory):

    class Item:
        class Status:
            SENT = "Sent"
            FAILED = "Failed"
            PENDING = "Pending"

        def __init__(
            self,
            sent_to: Union[List, str],
            status: str = None,
            created_at: str = None,
        ):
            """
            Initialize a notification with the recipient, origin, status, and creation time.
            """
            self.sent_to = sent_to
            self.status = status or self.Status.PENDING
            self.created_at = created_at or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        def to_json(self) -> Dict[str, Union[str, List[Dict[str, Any]]]]:
            """
            Convert the notification history to a JSON serializable format.
            """
            return {
                "created_at": self.created_at,
                "sent_to": (
                    ", ".join(self.sent_to) if isinstance(self.sent_to, list) else self.sent_to
                ),
                "status": self.status,
            }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._table_columns = [
            "Created At",
            "Sent To",
            "Status",
        ]
        self._columns_keys = [
            ["created_at"],
            ["sent_to"],
            ["status"],
        ]

    def update(self):
        self.table.clear()
        for task in self.get_tasks():
            self.table.insert_row(list(task.values()))

    def add_task(self, task: Union["SendEmailHistory.Item", Dict[str, Any]]):
        if isinstance(task, SendEmailHistory.Item):
            task = task.to_json()
        super().add_task(task)
        self.update()

    def update_task(
        self,
        time: datetime.datetime,
        task: Union["SendEmailHistory.Item", Dict[str, Any]],
    ):
        if isinstance(task, SendEmailHistory.Item):
            task = task.to_json()
        tasks = self.get_tasks()
        for task in tasks:
            if task["created_at"] == time:
                task.update(task)
                DataJson()[self.widget_id]["tasks"] = tasks
                DataJson().send_changes()
                return
        raise KeyError(f"Task with created_at {time} not found in the notification history.")

    @property
    def table(self):
        if not hasattr(self, "_tasks_table"):
            self._tasks_table = self._create_tasks_history_table()
        return self._tasks_table


class SendEmailNode(SolutionElement):
    JOB_ID = "send_email_daily"

    def __init__(
        self,
        credentials: SendEmail.EmailCredentials,
        x: int = 0,
        y: int = 0,
        width: int = 250,
        tooltip_position: Literal["left", "right"] = "right",
        *args,
        **kwargs,
    ):
        self.width = width
        self.tooltip_position = tooltip_position
        super().__init__(*args, **kwargs)

        self.credentials = credentials
        self.main_widget = SendEmail()
        self.task_history = SendEmailHistory()
        self.tasks_modal = Dialog(title="Notification History", content=self.task_history)
        self.automation = SendEmailAutomation(self.run)

        if is_development():
            self._debug_add_dummy_notification()  # For debugging purposes, delete in production

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)

        self.modals = [
            self.settings_modal,
            self.automation.modal,
            self.tasks_modal,
        ]

        @self.automation.apply_button.click
        def apply_automation_settings():
            self.automation.modal.hide()
            self.automation.save()
            self._update_properties()

        @self.main_widget.apply_button.click
        def apply_settings_cb():
            self.settings_modal.hide()

    def _debug_add_dummy_notification(self):
        """
        Adds a dummy notification to the history for debugging purposes.
        """
        dummy_notification = SendEmailHistory.Item(
            ["someuser123@example.com", "dummy228@yahoo.com"], SendEmailHistory.Item.Status.SENT
        )
        self.task_history.add_task(dummy_notification.to_json())

    @property
    def settings_modal(self) -> Dialog:
        """
        Returns the settings modal for email notifications.
        """
        if not hasattr(self, "_settings_modal"):
            self._settings_modal = Dialog("Notification Settings", self.main_widget, size="tiny")
        return self._settings_modal

    def run(self) -> None:
        """
        Runs the SendEmailNode, sending an email with the configured settings.
        """
        self.automation.save()
        self.node.hide_finished_badge()
        self.node.hide_failed_badge()
        notification = SendEmailHistory.Item(self.main_widget.get_target_addresses())
        n_idx = self.task_history.add_notification(notification)
        try:
            self.main_widget.send_email(self.credentials)
            self.show_finished_badge()
            self.task_history.update_notification_status(n_idx, SendEmailHistory.Item.Status.SENT)
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            self.show_failed_badge()
            self.task_history.update_notification_status(n_idx, SendEmailHistory.Item.Status.FAILED)

    def _get_email_widget_values(self) -> Dict[str, Union[str, List[str]]]:
        return {
            "subject": self.main_widget.get_subject(),
            "body": self.main_widget.get_body(),
            "target_addresses": self.main_widget.get_target_addresses(),
        }

    def _create_card(self) -> SolutionCard:
        """
        Creates and returns the SolutionCard for the SendEmailNode.
        """
        return SolutionCard(
            title="Send Email",
            tooltip=self._create_tooltip(),
            width=self.width,
            tooltip_position=self.tooltip_position,
            icon=Icons(class_name="zmdi zmdi-email", color="#1976D2", bg_color="#E3F2FD"),
        )

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        """
        Creates and returns the tooltip for the SendEmailNode.
        """
        return SolutionCard.Tooltip(
            description="Send email notifications to specified addresses.",
            content=self._get_buttons(),
            properties=[],
        )

    def _get_buttons(self):
        if not hasattr(self, "_settings_btn"):
            self._settings_btn = Button(
                "Notifications Settings",
                icon="zmdi zmdi-settings",
                plain=True,
                button_type="text",
                button_size="mini",
            )
            self._settings_btn.click(self.settings_modal.show)
        if not hasattr(self, "_automate_btn"):
            self._automate_btn = Button(
                "Automate",
                icon="zmdi zmdi-settings",
                button_size="mini",
                plain=True,
                button_type="text",
            )
            self._automate_btn.click(self.automation.modal.show)
        if not hasattr(self, "_history_btn"):
            self._history_btn = Button(
                "Notification History",
                icon="zmdi zmdi-format-subject",
                plain=True,
                button_type="text",
                button_size="mini",
            )
            self._history_btn.click(self.tasks_modal.show)
        return [
            self._settings_btn,
            self._automate_btn,
            self._history_btn,
        ]

    @property
    def is_email_sending_enabled(self) -> bool:
        """
        Returns whether the email should be sent after each comparison.
        """
        return self.automation.is_email_sending_enabled()

    def _update_properties(self):
        if self.is_email_sending_enabled:
            self.node.show_automation_badge()
        else:
            self.node.hide_automation_badge()
        new_propetries = [
            {
                "key": "Send Notification",
                "value": "✔️" if self.is_email_sending_enabled else "✖",
                "link": False,
                "highlight": True,
            },
            {
                "key": "Total",
                "value": f"{(len(self.task_history.get_tasks()))} notifications",
                "link": False,
                "highlight": False,
            },
        ]
        for prop in new_propetries:
            self.card.update_property(**prop)
