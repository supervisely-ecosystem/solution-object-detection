import datetime
from typing import Any, Dict, List, Union

from supervisely.app import DataJson
from supervisely.app.widgets.fast_table.fast_table import FastTable
from supervisely.app.widgets.widget import Widget


class Notification:
    class Status:
        SENT = "Sent ✅"
        FAILED = "Failed ❌"
        PENDING = "Pending ⏳"

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
            "sent_to": ", ".join(self.sent_to) if isinstance(self.sent_to, list) else self.sent_to,
            "origin": self.origin,
            "status": self.status,
        }


class NotificationHistory(Widget):
    def __init__(
        self,
        widget_id: str = None,
    ):
        super().__init__(widget_id=widget_id)

    @property
    def table_columns(self) -> List[str]:
        if not hasattr(self, "_table_columns"):
            self._table_columns = [
                "Created At",
                "Sent To",
                "Origin",
                "Status",
            ]
        return self._table_columns

    @table_columns.setter
    def table_columns(self, value: List[str]):
        self._table_columns = value

    @property
    def columns_keys(self) -> List[List[str]]:
        if not hasattr(self, "_columns_keys"):
            self._columns_keys = [
                ["created_at"],
                ["sent_to"],
                ["origin"],
                ["status"],
            ]
        return self._columns_keys

    @columns_keys.setter
    def columns_keys(self, value: List[List[str]]):
        self._columns_keys = value

    def update_table(self):
        self.table.clear()
        for notification in self.get_notifications():
            if not isinstance(notification, dict):
                raise TypeError("Each notification must be a dictionary")
            self.table.insert_row(list(notification.values()))

    def get_notifications(self) -> List[Dict[str, Any]]:
        """Get the list of notifications from the state JSON."""
        notifications = DataJson().get(self.widget_id, {}).get("notifications", [])
        if not isinstance(notifications, list):
            raise TypeError("notifications must be a list")
        return notifications

    def add_notification(self, notification: Dict[str, Any]) -> int:
        """Add a notification to the notifications list in the state JSON."""
        if not isinstance(notification, dict):
            raise TypeError("Notification must be a dictionary")
        notifications = self.get_notifications()
        notifications.append(notification)
        notification_idx = len(notifications) - 1
        DataJson()[self.widget_id]["notifications"] = notifications
        DataJson().send_changes()
        self.update_table()
        return notification_idx

    def update_notification_status(self, notification_idx: int, status: str):
        notifications = self.get_notifications()
        for idx, n in enumerate(notifications):
            if idx == notification_idx:
                n["status"] = status
                DataJson()[self.widget_id]["notifications"] = notifications
                DataJson().send_changes()
                self.update_table()
                return
        raise KeyError(f"Notification not found in the table.")

    def _get_table_data(self) -> List[List[Any]]:
        data = []
        for notification in self.get_notifications():
            row = [
                self._get_task_item(col, notification, default="unknown")
                for col in self.columns_keys
            ]
            data.append(row)
        return data

    def _create_notification_history_table(self):
        columns = self.table_columns
        return FastTable(columns=columns, sort_column_idx=0, fixed_columns=1, sort_order="desc")

    @property
    def table(self):
        if not hasattr(self, "_notification_table"):
            self._notification_table = self._create_notification_history_table()

            @self._notification_table.row_click
            def on_row_click(clicked_row: FastTable.ClickedRow):
                # self.logs.set_task_id(clicked_row.row[0])
                # self.logs_modal.show()
                pass

        return self._notification_table

    def get_json_data(self):
        return {"notifications": []}

    def get_json_state(self):
        return {}

    def to_html(self):
        return self.table.to_html()
