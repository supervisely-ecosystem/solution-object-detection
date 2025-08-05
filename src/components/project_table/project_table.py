from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional

from supervisely import logger
from supervisely._utils import abs_url
from supervisely.api.api import Api
from supervisely.api.project_api import ProjectInfo
from supervisely.app import DataJson
from supervisely.app.content import StateJson
from supervisely.app.widgets import Container, Empty, FastTable, Select, Widget
from supervisely.app.widgets_context import JinjaWidgets
from supervisely.project import ProjectType

from src.components.team_workspace_select.team_workspace_select import (
    TeamWorkspaceSelect,
)


class ProjectTable(Widget):
    class Routes:
        ROW_CLICKED = "row_clicked_cb"
        SELECTION_CHANGED = "selection_changed_cb"
        UPDATE_DATA = "update_data_cb"

    @dataclass
    class ClickedRow:
        row: List
        row_index: int = None

    def __init__(
        self,
        sort_by: Literal["name", "date", "assets"] = "date",
        sort_order: Literal["asc", "desc"] = "desc",
        page_size: int = 10,
        width: str = "auto",
        allowed_project_types: Optional[List[ProjectType]] = None,
        team_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        widget_id: Optional[str] = None,
    ):
        self._api = Api()
        self._team_id = team_id
        self._workspace_id = workspace_id

        self._row_click_handled = False
        self._cell_click_handled = False
        self._selection_changed_handled = False

        self._max_selected_rows = 1

        self._data = []
        self._filtered_data = []

        self._search_str = ""
        self._active_page = 1
        self._page_size = page_size
        self._columns = ["Project Name", "ID", "Date Modified", "Type", "Assets"]
        self._sort_by = self._columns.index(sort_by) if sort_by in self._columns else 3
        self._sort_order = sort_order

        self._columns_data = []
        self._columns_first_idx = []
        for col in self._columns:
            self._columns_first_idx.append(col)
            self._columns_data.append(col)

        self._width = width
        self._show_header = True
        self._header_left_content = self.team_workspace_select

        self._selected_rows = None
        self._selected_cell = None
        self._checked_rows = []
        self._row_special_data = {}

        self._project_id_to_info = {}

        self._allowed_project_types = allowed_project_types
        if isinstance(self._allowed_project_types, list):
            if all(isinstance(pt, ProjectType) for pt in self._allowed_project_types):
                self._allowed_project_types = [pt.value for pt in self._allowed_project_types]

        self._columns_options = []

        super().__init__(widget_id=widget_id, file_path=__file__)
        script_path = "./static/script.js"
        JinjaWidgets().context["__widget_scripts__"][self.__class__.__name__] = script_path

        # if self._workspace_id:
        #     self._refresh_table()

        filter_changed_route_path = self.get_route_path(self.Routes.UPDATE_DATA)
        server = self._sly_app.get_server()

        @server.post(filter_changed_route_path)
        def _filter_changed():
            self._active_page = StateJson()[self.widget_id]["page"]
            self._sort_order = StateJson()[self.widget_id]["sort"]["order"]
            self._sort_by = StateJson()[self.widget_id]["sort"]["column"]
            search_value = StateJson()[self.widget_id]["search"]
            self._filtered_data = self.search(search_value)
            rows_total = len(self._filtered_data)

            if rows_total > 0 and self._active_page == 0:  # if previous filtered data was empty
                self._active_page = 1
                StateJson()[self.widget_id]["page"] = self._active_page

            DataJson()[self.widget_id]["data"] = self._filtered_data
            DataJson()[self.widget_id]["total"] = rows_total
            DataJson().send_changes()
            StateJson().send_changes()

    @property
    def team_workspace_select(self) -> TeamWorkspaceSelect:
        if not hasattr(self, "_team_workspace_select"):
            selector = TeamWorkspaceSelect(
                show_label=True,
                direction="horizontal",
                default_team_id=self._team_id,
                default_workspace_id=self._workspace_id,
            )

            @selector.value_changed
            def on_team_workspace_change(value: Dict[str, int]):
                self._team_id = selector.get_selected_team_id()
                self._workspace_id = selector.get_selected_workspace_id()
                self._refresh_table()

            self._team_workspace_select = selector
        return self._team_workspace_select

    # def _prepare_input_data(self, data: List) -> List:
    #     import copy

    #     prepared_data = []
    #     for i, row in enumerate(data):
    #         row = copy.deepcopy(row)
    #         if isinstance(row[0], (list, tuple)):
    #             self._row_special_data[i] = row[0]
    #             row = row[1]
    #         prepared_data.append(row)
    #     return prepared_data

    def _refresh_table(self):
        projects = self._api.project.get_list(self._workspace_id)
        if self._allowed_project_types:
            projects = [p for p in projects if p.type in self._allowed_project_types]
        self._projects = projects
        self._project_id_to_info = {p.id: p for p in projects}
        table_data = [
            [
                project.name,
                project.id,
                datetime.strptime(
                    project.created_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f"
                ).strftime("%d %b %Y %H:%M"),
                project.type.replace("_", " ").title(),
                project.items_count,
            ]
            for project in projects
        ]
        self._row_special_data = {
            i: abs_url(info.reference_image_url) for i, info in enumerate(projects)
        }
        self._data = table_data
        DataJson()[self.widget_id]["data"] = table_data
        DataJson().send_changes()

    def search(self, search_value: str) -> List[Dict]:
        if not search_value:
            return self._data

        filtered_data = []
        for row in self._data:
            if search_value.lower() in str(row).lower():
                filtered_data.append(row)
        return filtered_data

    def sort(self, sort_by: Literal["assets", "date", "name"], sort_order: Literal["asc", "desc"]):
        self._sort_by = sort_by
        self._sort_order = sort_order
        if self._sort_by is not None:
            StateJson()[self.widget_id]["sort"]["column"] = self._sort_by
        if self._sort_order is not None:
            StateJson()[self.widget_id]["sort"]["order"] = self._sort_order
        self._filtered_data = self.search(self._search_str)

        DataJson()[self.widget_id]["data"] = self._filtered_data
        DataJson()[self.widget_id]["total"] = len(self._filtered_data)
        StateJson().send_changes()

    def get_selected_rows(self) -> List[ClickedRow]:
        """Returns the selected rows.

        :return: Selected rows
        :rtype: List[ClickedRow]
        """
        selected_rows = StateJson()[self.widget_id]["selectedRows"]
        if selected_rows is None or len(selected_rows) == 0:
            return None
        if len(selected_rows) > 1:
            raise ValueError("Multiple rows selected, but only one is expected.")
        row = selected_rows[0]
        row_index = row["idx"]
        row = row.get("row", row.get("items", None))
        if row_index is None or row is None:
            return None
        return self.ClickedRow(row, row_index)

    def get_selected_project(self) -> Optional[ProjectInfo]:
        """Returns the selected project info.

        :return: Selected project info or None if no project is selected
        :rtype: Optional[ProjectInfo]
        """
        selected_rows = StateJson()[self.widget_id].get("selectedRows")
        if not selected_rows or len(selected_rows) == 0:
            return None
        project_id = selected_rows[0]["row"].get("id")
        return self._project_id_to_info.get(project_id)

    # def row_click(self, func: Callable[[ClickedRow], Any]) -> Callable[[], None]:
    #     """Decorator for function that handles row click event.

    #     :param func: Function that handles row click event
    #     :type func: Callable[[ClickedRow], Any]
    #     :return: Decorated function
    #     :rtype: Callable[[], None]
    #     """
    #     row_clicked_route_path = self.get_route_path(self.Routes.ROW_CLICKED)
    #     server = self._sly_app.get_server()

    #     self._row_click_handled = True

    #     @server.post(row_clicked_route_path)
    #     def _click():
    #         try:
    #             clicked_row = self.get_selected_row()
    #             if clicked_row is None:
    #                 return
    #             func(clicked_row)
    #         except Exception as e:
    #             logger.error(str(e), exc_info=True, extra={"exc_str": str(e)})
    #             raise e

    #     return _click

    # def row_selected(self, func: Callable[[List[ClickedRow]], Any]) -> Callable[[], None]:
    #     """Decorator for function that handles row selection change event.

    #     :param func: Function that handles row selection change event
    #     :type func: Callable[[List[ClickedRow]], Any]
    #     :return: Decorated function
    #     :rtype: Callable[[], None]
    #     """
    #     selection_changed_route_path = self.get_route_path(self.Routes.SELECTION_CHANGED)
    #     server = self._sly_app.get_server()

    #     self._selection_changed_handled = True

    #     @server.post(selection_changed_route_path)
    #     def _selection_changed():
    #         try:
    #             selected_rows = StateJson()[self.widget_id].get("selectedRows", [])
    #             clicked_rows = [self.ClickedRow(row["row"], row["idx"]) for row in selected_rows]
    #             func(clicked_rows)
    #         except Exception as e:
    #             logger.error(str(e), exc_info=True, extra={"exc_str": str(e)})
    #             raise e

    #     return _selection_changed

    def get_json_data(self) -> Dict[str, Any]:
        """Returns dictionary with widget data, which defines the appearance and behavior of the widget.
        Dictionary contains the following fields:
            - data: table data
            - columns: list of column names
            - total: total number of rows
            - pageSize: number of rows per page

        :return: Dictionary with widget data
        :rtype: Dict[str, Any]
        """
        return {
            "data": self._data,
            "columns": self._columns,
            "total": len(self._data),
            "columnsOptions": self._columns_options,
            "options": {
                "isRowClickable": False,
                "isCellClickable": False,
                "fixColumns": None,
                "isSelectable": True,
                "maxSelectedRows": self._max_selected_rows,
            },
            "pageSize": self._page_size,
            "showHeader": self._show_header,
            "selectionChangedHandled": self._selection_changed_handled,
        }

    def get_json_state(self) -> Dict[str, Any]:
        """Returns dictionary with widget state.
        Dictionary contains the following fields:
            - search: search string
            - selectedRows: selected rows
            - page: active page
            - sort: sorting options with the following fields:
                - column: index of the column to sort by
                - order: sorting order

        :return: Dictionary with widget state
        :rtype: Dict[str, Any]
        """
        return {
            "search": self._search_str,
            "selectedRows": self._selected_rows,
            "selectedCell": self._selected_cell,
            "page": self._active_page,
            "sort": {
                "column": self._sort_by,
                "order": self._sort_order,
            },
        }
