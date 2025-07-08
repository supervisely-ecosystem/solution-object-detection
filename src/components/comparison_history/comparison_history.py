import datetime
from typing import Any, Dict, List, Union

from supervisely.app import DataJson
from supervisely.app.widgets.fast_table.fast_table import FastTable
from supervisely.app.widgets.widget import Widget


class ComparisonItem:
    def __init__(
        self,
        task_id: str,
        input_evals: Union[List[str], str],
        result_folder: str,
        best_checkpoint: str,
        created_at: str = None,
    ):
        """
        Initialize a comparison item with task ID, input evaluations, result folder, best checkpoint, and creation time.
        """
        self.task_id = task_id
        self.input_evals = input_evals if isinstance(input_evals, list) else [input_evals]
        self.result_folder = result_folder
        self.best_checkpoint = best_checkpoint
        self.created_at = created_at or datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    def to_json(self) -> Dict[str, Any]:
        """Convert the comparison item to a JSON serializable format."""
        return {
            "created_at": self.created_at,
            "task_id": self.task_id,
            "input_evals": ", ".join(self.input_evals),
            "result_folder": self.result_folder,
            "best_checkpoint": self.best_checkpoint,
        }


class ComparisonHistory(Widget):
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
                "Task ID",
                "Input Evaluations",
                "Result Folder",
                "Best checkpoint",
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
                ["task_id"],
                ["input_evals"],
                ["result_folder"],
                ["best_checkpoint"],
            ]
        return self._columns_keys

    @columns_keys.setter
    def columns_keys(self, value: List[List[str]]):
        self._columns_keys = value

    def update_table(self):
        self.table.clear()
        for comparison in self.get_comparison_items():
            if not isinstance(comparison, dict):
                raise TypeError("Each comparison must be a dictionary")
            self.table.insert_row(list(comparison.values()))

    def get_comparison_items(self) -> List[Dict[str, Any]]:
        """Get the list of notifications from the state JSON."""
        notifications = DataJson()[self.widget_id].get("notifications", [])
        if not isinstance(notifications, list):
            raise TypeError("notifications must be a list")
        return notifications

    def add_comparison(self, comparison: Union[ComparisonItem, Dict[str, Any]]) -> int:
        """Add a comparison to the comparisons list in the state JSON."""

        if isinstance(comparison, ComparisonItem):
            comparison = comparison.to_json()

        if not isinstance(comparison, dict):
            raise TypeError("comparison must be a dictionary")
        comparisons = self.get_comparison_items()
        comparisons.append(comparison)
        DataJson()[self.widget_id]["comparisons"] = comparisons
        DataJson().send_changes()
        self.update_table()

    def update_comparison_status(self, comparison_idx: int, status: str):
        comparisons = self.get_comparison_items()
        for idx, n in enumerate(comparisons):
            if idx == comparison_idx:
                n["status"] = status
                DataJson()[self.widget_id]["comparisons"] = comparisons
                DataJson().send_changes()
                self.update_table()
                return
        raise KeyError(f"Comparison not found in the table.")

    def _get_table_data(self) -> List[List[Any]]:
        data = []
        for comparison in self.get_comparison_items():
            row = [
                self._get_task_item(col, comparison, default="unknown") for col in self.columns_keys
            ]
            data.append(row)
        return data

    def _create_comparison_history_table(self):
        columns = self.table_columns
        return FastTable(columns=columns, sort_column_idx=0, fixed_columns=1, sort_order="desc")

    @property
    def table(self):
        if not hasattr(self, "_comparison_table"):
            self._comparison_table = self._create_comparison_history_table()

            @self._comparison_table.row_click
            def on_row_click(clicked_row: FastTable.ClickedRow):
                # @TODO
                # self.logs.set_task_id(clicked_row.row[0])
                # self.logs_modal.show()
                pass

        return self._comparison_table

    def get_json_data(self):
        return {"comparisons": []}

    def get_json_state(self):
        return {}

    def to_html(self):
        return self.table.to_html()
