import datetime
from typing import Any, Dict, List, Literal, Optional, Union

from apscheduler.triggers.cron import CronTrigger

from src.components.send_email.send_email import SendEmail
from supervisely.sly_logger import logger
from supervisely.app.content import DataJson
from supervisely.app.widgets import (
    Button,
    CheckboxField,
    Container,
    Field,
    Icons,
    SolutionCard,
    Switch,
    TimePicker,
)
from supervisely.app.widgets.dialog.dialog import Dialog
from supervisely.solution.base_node import SolutionCardNode, SolutionElement
from supervisely.solution.components.tasks_history import TasksHistory
from supervisely.solution.scheduler import TasksScheduler


class SendEmailHistory(TasksHistory):

    class Item:
        class Status:
            SENT = "Sent"
            FAILED = "Failed"
            PENDING = "Pending"

        def __init__(
            self,
            sent_to: Union[List, str],
            origin: str,
            status: str = None,
            created_at: str = None,
        ):
            """
            Initialize a notification with the recipient, origin, status, and creation time.
            """
            self.sent_to = sent_to
            self.origin = origin
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
                "origin": self.origin,
                "status": self.status,
            }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._table_columns = [
            "Created At",
            "Sent To",
            "Origin",
            "Status",
        ]
        self._columns_keys = [
            ["created_at"],
            ["sent_to"],
            ["origin"],
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
        if not hasattr(self, "_notification_table"):
            self._notification_table = self._create_tasks_history_table()
        return self._notification_table


class SendEmailNode(SolutionElement):
    JOB_ID = "send_email_daily"

    def __init__(
        self,
        credentials: SendEmail.EmailCredentials,
        title: str = "Send Email",
        description: str = "Send an email notification.",
        width: int = 250,
        x: int = 0,
        y: int = 0,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        *args,
        **kwargs,
    ):
        self.title = title
        self.description = description
        self.width = width
        self.icon = icon or self._get_default_icon()
        self.tooltip_position = tooltip_position
        super().__init__(*args, **kwargs)

        self.credentials = credentials
        self.task_scheduler = TasksScheduler()

        self._debug_add_dummy_notification()  # For debugging purposes, delete in production

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self._update_properties()
        self.modals = [self.settings_modal, self.automation_modal, self.history_modal]

    def _debug_add_dummy_notification(self):
        """
        Adds a dummy notification to the history for debugging purposes.
        """
        dummy_notification = SendEmailHistory.Item(
            ["someuser123@example.com", "dummy228@yahoo.com"], SendEmailHistory.Item.Status.SENT
        )
        self.notification_history.add_task(dummy_notification.to_json())

    @property
    def settings_modal(self) -> Dialog:
        """
        Returns the settings modal for email notifications.
        """
        if not hasattr(self, "_settings_modal"):
            self._settings_modal = self._init_settings_modal()
        return self._settings_modal

    @property
    def automation_modal(self) -> Dialog:
        """
        Returns the automation settings modal.
        """
        if not hasattr(self, "_automation_modal"):
            self._automation_modal = self._init_automation_modal()
        return self._automation_modal

    @property
    def history_modal(self) -> Dialog:
        """
        Returns the notification history modal.
        """
        if not hasattr(self, "_history_modal"):
            self._history_modal = self._init_history_modal()
        return self._history_modal

    @property
    def notification_history(self) -> SendEmailHistory:
        """
        Returns the notification history instance.
        """
        if not hasattr(self, "_notification_history"):
            self._notification_history = SendEmailHistory()
        return self._notification_history

    def _init_history_modal(self) -> Dialog:
        history_modal = Dialog(
            title="Notification History",
            content=self.notification_history,
            size="large",
        )
        return history_modal

    def _init_settings_modal(self) -> Dialog:
        send_email = SendEmail()
        settings_modal = Dialog("Notification Settings", send_email, size="tiny")

        @send_email.apply_button.click
        def apply_settings_cb():
            self.save()
            settings_modal.hide()

        def send_email_fn():
            self.hide_failed_badge()
            notification_origin = "Daily" if self.use_daily else "Comparison"
            notification = SendEmailHistory.Item(
                self.target_addresses, notification_origin
            ).to_json()
            n_idx = self.notification_history.add_notification(notification)
            try:
                send_email.send_email(self.credentials)
                self.show_finished_badge()
                self.hide_running_badge()
                self.notification_history.update_notification_status(
                    n_idx, SendEmailHistory.Item.Status.SENT
                )
            except:
                self.show_failed_badge()
                self.hide_running_badge()
                self.notification_history.update_notification_status(
                    n_idx, SendEmailHistory.Item.Status.FAILED
                )

        self.run_fn = send_email_fn
        self._get_email_widget_values = lambda: {
            "subject": send_email.get_subject(),
            "body": send_email.get_body(),
            "target_addresses": send_email.get_target_addresses(),
        }
        return settings_modal

    def _init_automation_modal(self):
        use_daily_switch = Switch(False)
        daily_time_picker = TimePicker(self.daily_time)
        after_comparison = CheckboxField(
            "After Comparison", "Enable to send an email after each comparison.", False
        )
        apply_button = Button("Apply")
        automation_modal = Dialog(
            title="Automation Settings",
            content=Container(
                [
                    Field(
                        use_daily_switch,
                        "Daily Notifications",
                        "Enable to send email notifications every day at a specified time.",
                    ),
                    Field(
                        daily_time_picker,
                        "Time of Day",
                        "Specify the time of day to send daily notifications.",
                    ),
                    after_comparison,
                    apply_button,
                ]
            ),
            size="tiny",
        )

        self._get_automation_widget_values = lambda: {
            "use_daily": use_daily_switch.is_switched(),
            "daily_time": daily_time_picker.get_value(),
            "run_after_comparison": after_comparison.is_checked(),
        }

        @apply_button.click
        def apply_automation_settings():
            self.save()
            self._update_properties()
            self.update_scheduler()
            automation_modal.hide()

        return automation_modal

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
            self._automate_btn.click(self.automation_modal.show)
        if not hasattr(self, "_history_btn"):
            self._history_btn = Button(
                "Notification History",
                icon="zmdi zmdi-format-subject",
                plain=True,
                button_type="text",
                button_size="mini",
            )
            self._history_btn.click(self.history_modal.show)
        return [
            self._settings_btn,
            self._automate_btn,
            self._history_btn,
        ]

    @property
    def body(self) -> str:
        """
        Returns the body of the email.
        """
        return DataJson()[self.widget_id].get("email_config", {}).get("body", "")

    @property
    def subject(self) -> str:
        """
        Returns the subject of the email.
        """
        return DataJson()[self.widget_id].get("email_config", {}).get(["email_subject"], "")

    @property
    def target_addresses(self) -> List[str]:
        """
        Returns the list of target email addresses.
        """
        return DataJson()[self.widget_id].get("email_config", {}).get("target_addresses", [])

    @property
    def use_daily(self) -> bool:
        """
        Returns whether the email should be sent daily.
        """
        return DataJson()[self.widget_id].get("automation_settings", {}).get("use_daily", False)

    @property
    def daily_time(self) -> str:
        """
        Returns the time of day when the email should be sent if daily notifications are enabled.
        """
        return DataJson()[self.widget_id].get("automation_settings", {}).get("daily_time", "09:00")

    @property
    def run_after_comparison(self) -> bool:
        """
        Returns whether the email should be sent after each comparison.
        """
        return (
            DataJson()[self.widget_id]
            .get("automation_settings", {})
            .get("run_after_comparison", False)
        )

    def save(self) -> None:
        """
        Saves the current state of the SendEmailNode.
        """
        DataJson()[self.widget_id]["automation_settings"] = self._get_automation_widget_values()
        DataJson()[self.widget_id]["email_config"] = self._get_email_widget_values()
        DataJson().send_changes()

    def _update_properties(self):
        use_daily = self.use_daily
        use_after_comparison = self.run_after_comparison
        if use_daily and use_after_comparison:
            send_value = "every day / after comparison"
            self.node.show_automation_badge()
        elif use_daily and not use_after_comparison:
            send_value = "every day"
            self.node.show_automation_badge()
        elif use_after_comparison and not use_daily:
            send_value = "after comparison"
            self.node.show_automation_badge()
        else:
            send_value = "never"
            self.node.hide_automation_badge()
        new_propetries = [
            {
                "key": "Send",
                "value": send_value,
                "link": False,
                "highlight": True,
            },
            {
                "key": "Total",
                "value": "{} notifications".format(
                    len(self.notification_history.get_tasks())
                ),
                "link": False,
                "highlight": False,
            },
            {
                "key": "Email",
                "value": self.credentials.username,
                "link": True,
                "highlight": False,
            },
        ]
        for prop in new_propetries:
            self.card.update_property(**prop)

    def update_scheduler(self):
        use_daily = self.use_daily
        if not use_daily:
            if self.task_scheduler.is_job_scheduled(self.JOB_ID):
                self.task_scheduler.remove_job(self.JOB_ID)
                logger.info("[SCHEDULER]: Daily email job is disabled.")
            return

        time = self.daily_time
        hour, minute = map(int, time.split(":"))
        tigger = CronTrigger(hour=hour, minute=minute, second=0)
        job = self.task_scheduler.scheduler.add_job(
            self.run_fn,
            tigger,
            id=self.JOB_ID,
            replace_existing=True,
        )
        self.task_scheduler.jobs[job.id] = job
        logger.info(
            f"[SCHEDULER]: Job '{job.id}' scheduled to send emails at {time} every day."
        )

    def _create_card(self) -> SolutionCard:
        """
        Creates and returns the SolutionCard for the SendEmailNode.
        """
        return SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            width=self.width,
            tooltip_position=self.tooltip_position,
            icon=self.icon,
        )

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        """
        Creates and returns the tooltip for the SendEmailNode.
        """
        return SolutionCard.Tooltip(
            description=self.description,
            content=self._get_buttons(),
            properties=[],
        )

    def _get_default_icon(self) -> Icons:
        """
        Returns a default icon for the SendEmailNode.
        """
        return Icons(
            class_name="zmdi zmdi-email",
            color="#1976D2",
            bg_color="#E3F2FD",
        )
