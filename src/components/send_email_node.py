import datetime
from typing import Any, Callable, Dict, List, Literal, Optional, Tuple, Union

from supervisely._utils import is_development
from supervisely.api.api import Api
from supervisely.app.content import DataJson
from supervisely.app.widgets import Button, Icons, SolutionCard
from supervisely.app.widgets.dialog.dialog import Dialog
from supervisely.app.widgets.tasks_history.tasks_history import TasksHistory
from supervisely.sly_logger import logger
from supervisely.solution.base_node import SolutionCardNode, SolutionElement

from src.components.send_email.send_email import SendEmail


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
            res = {
                "sent_to": self.sent_to if isinstance(self.sent_to, list) else [self.sent_to],
            }
            if self.status:
                res["status"] = self.status
            if self.created_at:
                res["created_at"] = self.created_at
            return res

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._table_columns = [
            "ID",
            "Created At",
            "Sent To",
            "Status",
        ]
        self._columns_keys = [
            ["id"],
            ["created_at"],
            ["sent_to"],
            ["status"],
        ]

    def update(self):
        self.table.clear()
        for task in self._get_table_data():
            self.table.insert_row(task)

    def add_task(self, task: Union["SendEmailHistory.Item", Dict[str, Any]]):
        if isinstance(task, SendEmailHistory.Item):
            task = task.to_json()
        task["id"] = len(self.get_tasks()) + 1  # Assign a new ID
        super().add_task(task)
        self.update()
        return task["created_at"]

    def update_task(
        self,
        time: datetime.datetime,
        task: Union["SendEmailHistory.Item", Dict[str, Any]],
    ):
        if isinstance(task, SendEmailHistory.Item):
            task = task.to_json()
        tasks = self.get_tasks()
        for row in tasks:
            if row["created_at"] == time:
                row.update(task)
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
        x: int = 0,
        y: int = 0,
        credentials: SendEmail.Credentials = None,
        width: int = 250,
        tooltip_position: Literal["left", "right"] = "right",
        *args,
        **kwargs,
    ):
        self.width = width
        self.tooltip_position = tooltip_position
        super().__init__(*args, **kwargs)

        self.credentials = credentials or SendEmail.Credentials.from_env()
        self.main_widget = SendEmail(
            default_subject="Supervisely Solution Notification",
            default_body="""
<html>
<head>
    <style>
        body {{
            font-family: Arial, sans-serif;
            line-height: 1.6;
        }}
        .highlight {{
            color: #1976D2;
            font-weight: bold;
        }}
    </style>
</head>
<body>
    <p>Hello,</p>
    <p>This is a notification from the Supervisely Solution.</p><br><br>
    {message}<br><br>
    <p>Supervisely Solution</p>
</body>
</html>
""",
            show_body=False,
        )
        self.task_history = SendEmailHistory()
        self.tasks_modal = Dialog(title="Notification History", content=self.task_history)

        if is_development():
            self._debug_add_dummy_notification()  # For debugging purposes, delete in production

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)

        self.modals = [
            self.settings_modal,
            self.tasks_modal,
        ]

        @self.main_widget.apply_button.click
        def apply_settings_cb():
            self.settings_modal.hide()
            self._update_properties()

        @self.card.click
        def on_card_click():
            self.settings_modal.show()

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

    def run(self, text: str) -> None:
        """
        Runs the SendEmailNode, sending an email with the configured settings.
        """
        notification = SendEmailHistory.Item(self.main_widget.get_target_addresses())
        n_idx = self.task_history.add_task(notification)
        self._update_properties()
        try:
            message = self.main_widget.get_body()
            if text:
                message = message.format(message=text)
            self.main_widget.send_email(self.credentials, message=message)
            self.task_history.update_task(n_idx, {"status": SendEmailHistory.Item.Status.SENT})
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            self.task_history.update_task(n_idx, {"status": SendEmailHistory.Item.Status.FAILED})

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
            description="Automatically send email notifications after each model comparison. You can configure the recipients and subject of the email.",
            content=[self.history_btn],
            properties=[],
        )

    @property
    def history_btn(self) -> Button:
        if not hasattr(self, "_history_btn"):
            self._history_btn = Button(
                "Notification History",
                icon="zmdi zmdi-format-list-bulleted",
                plain=True,
                button_type="text",
                button_size="mini",
            )

            @self._history_btn.click
            def show_tasks_history():
                self.tasks_modal.show()

        return self._history_btn

    @property
    def is_email_sending_enabled(self) -> bool:
        """
        Returns whether the email should be sent after each comparison.
        """
        return self.main_widget.is_email_sending_enabled

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
