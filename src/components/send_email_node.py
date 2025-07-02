from typing import List, Literal, Optional, Union

from apscheduler.triggers.cron import CronTrigger

import supervisely as sly
from src.components.send_email.send_email import SendEmail
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
from supervisely.solution.scheduler import TasksScheduler


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

        self.email_username = credentials.username

        self.tooltip_position = tooltip_position

        self.task_scheduler = TasksScheduler()

        # * Card buttons for modals

        self._settings_btn = Button(
            "Notifications Settings",
            icon="zmdi zmdi-settings",
            plain=True,
            button_type="text",
            button_size="mini",
        )
        self._automate_btn = Button(
            "Automate",
            icon="zmdi zmdi-settings",
            button_size="mini",
            plain=True,
            button_type="text",
        )
        self._history_btn = Button(
            "Notification History",
            icon="zmdi zmdi-format-subject",
            plain=True,
            button_type="text",
            button_size="mini",
        )

        # * Notification settings modal

        self._email_subject: str = None
        self._email_body: str = None
        self._target_addresses: List[str] = None

        send_email = SendEmail()
        self.settings_modal = Dialog("Notification Settings", send_email, size="tiny")
        self.run_fn = lambda: send_email.send_email(credentials)

        @send_email.apply_button.click
        def apply_settings_cb():
            self._email_subject = send_email.get_subject()
            self._email_body = send_email.get_body()
            self._target_addresses = send_email.get_target_addresses()
            self.settings_modal.hide()

        @self._settings_btn.click
        def settings_click_cb():
            self.settings_modal.show()

        # * History modal

        self.history_modal = self._init_history_modal()

        self._history_btn.disable()  # until implemented

        @self._history_btn.click
        def history_click_cb():
            self.history_modal.show()

        # * Automation modal

        self._automation_use_daily: bool = False
        self._automation_daily_time: str = "09:00"
        self._automation_run_after_comparison: bool = False

        automation_modal = self._init_automation_modal()
        self.automation_modal = automation_modal

        @self._automate_btn.click
        def automation_click_cb():
            self.automation_modal.show()

        self.card = self._create_card()
        self._update_properties()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.settings_modal, self.automation_modal, self.history_modal]
        super().__init__(*args, **kwargs)

    def _init_history_modal(self):
        history_modal = Dialog(
            title="Notification History",
            content=Container(
                [
                    Field(
                        "History",
                        "This feature is not implemented yet.",
                    ),
                ]
            ),
            size="tiny",
        )
        return history_modal

    def _init_automation_modal(self):
        use_daily_switch = Switch(False)
        daily_time_picker = TimePicker(self._automation_daily_time)
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

        @apply_button.click
        def apply_automation_settings():
            self._automation_use_daily = use_daily_switch.is_switched()
            self._automation_daily_time = daily_time_picker.get_value()
            self._automation_run_after_comparison = after_comparison.is_checked()
            self._update_properties()
            self.update_scheduler()
            automation_modal.hide()

        return automation_modal

    @property
    def run_after_comparison(self) -> bool:
        """
        Returns whether the email should be sent after each comparison.
        """
        return self._automation_run_after_comparison

    @run_after_comparison.setter
    def run_after_comparison(self, value: bool) -> None:
        """
        Sets whether the email should be sent after each comparison.
        """
        if not isinstance(value, bool):
            raise ValueError("run_after_comparison must be a boolean value.")
        self._automation_run_after_comparison = value

    @property
    def body(self) -> str:
        """
        Returns the body of the email.
        """
        return self._body

    @body.setter
    def body(self, value: str) -> None:
        """
        Sets the body of the email.
        """
        if not isinstance(value, str):
            raise ValueError("Email body must be a string.")
        self._body = value

    def _update_properties(self):
        use_daily = self._automation_use_daily
        use_after_comparison = self._automation_run_after_comparison
        if use_daily and use_after_comparison:
            send_value = "every day / after comparison"
        elif use_daily and not use_after_comparison:
            send_value = "every day"
        elif use_after_comparison and not use_daily:
            send_value = "after comparison"
        else:
            send_value = "never"
        new_propetries = [
            {
                "key": "Send",
                "value": send_value,
                "link": False,
                "highlight": True,
            },
            {
                "key": "Total",
                "value": "0 notifications",
                "link": False,
                "highlight": False,
            },
            {
                "key": "Email",
                "value": self.email_username,
                "link": True,
                "highlight": False,
            },
        ]
        for prop in new_propetries:
            self.card.update_property(**prop)

    def update_scheduler(self):
        use_daily = self._automation_use_daily
        if not use_daily:
            if self.task_scheduler.is_job_scheduled(self.JOB_ID):
                self.task_scheduler.remove_job(self.JOB_ID)
                sly.logger.info("[SCHEDULER]: Daily email job is disabled.")
            return

        time = self._automation_daily_time
        hour, minute = map(int, time.split(":"))
        tigger = CronTrigger(hour=hour, minute=minute, second=0)
        job = self.task_scheduler.scheduler.add_job(
            self.run_fn,
            tigger,
            id=self.JOB_ID,
            replace_existing=True,
        )
        self.task_scheduler.jobs[job.id] = job
        sly.logger.info(
            f"[SCHEDULER]: Job '{job.id}' scheduled to send emails at {time} every day."
        )

    def _create_card(self) -> SolutionCard:
        """
        Creates and returns the SolutionCard for the SendEmailNode.
        """
        return SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            # content=[self.error_nofitication],
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
            content=[self._settings_btn, self._automate_btn, self._history_btn],
            properties=[],
        )

    def show_finished_badge(self):
        """
        Updates the card to show that the evaluation is finished.
        """
        self.card.update_badge_by_key(key="Finished", label="✅", plain=True, badge_type="success")

    def hide_finished_badge(self):
        """
        Hides the finished badge from the card.
        """
        self.card.remove_badge_by_key(key="Finished")

    def show_running_badge(self):
        """
        Updates the card to show that the evaluation is running.
        """
        self.card.update_badge_by_key(key="Sending", label="⚡", plain=True, badge_type="warning")

    def hide_running_badge(self):
        """
        Hides the running badge from the card.
        """
        self.card.remove_badge_by_key(key="Sending")

    def show_failed_badge(self):
        """
        Updates the card to show that the evaluation has failed.
        """
        self.card.update_badge_by_key(key="Failed", label="❌", plain=True, badge_type="error")
        # self.error_nofitication.show()

    def hide_failed_badge(self):
        """
        Hides the failed badge from the card.
        """
        self.card.remove_badge_by_key(key="Failed")
        # self.error_nofitication.hide()

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
        """
        Returns a default icon for the SendEmailNode.
        """
        color, bg_color = self._random_pretty_color()
        return Icons(class_name="zmdi zmdi-email", color=color, bg_color=bg_color)

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
