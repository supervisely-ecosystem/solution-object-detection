from dataclasses import dataclass
from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional

from supervisely import logger
from supervisely.api.api import Api
from supervisely.api.project_api import ProjectInfo
from supervisely.app import DataJson
from supervisely.app.content import StateJson
from supervisely.app.widgets import Container, Empty, FastTable, Select, Widget
from supervisely.app.widgets_context import JinjaWidgets
from supervisely.project import ProjectType


class ProjectTable(Widget):
    class Routes:
        ROW_CLICKED = "row_clicked_cb"
        SELECTION_CHANGED = "selection_changed_cb"
        UPDATE_DATA = "update_data_cb"

    @dataclass
    class ClickedRow:
        row: List
        row_index: int = None

    @dataclass
    class ColumnData:
        name: str
        is_widget: bool = False
        widget: Optional[Widget] = None

        @property
        def widget_html(self) -> str:
            html = self.widget.to_html()
            html = html.replace(f".{self.widget.widget_id}", "[JSON.parse(cellValue).widget_id]")
            html = html.replace(
                f"/{self.widget.widget_id}", "/' + JSON.parse(cellValue).widget_id + '"
            )
            if hasattr(self.widget, "_widgets"):
                for i, widget in enumerate(self.widget._widgets):
                    html = html.replace(
                        f".{widget.widget_id}", f"[JSON.parse(cellValue).widgets[{i}]]"
                    )
                    html = html.replace(
                        f"/{widget.widget_id}", f"/' + JSON.parse(cellValue).widgets[{i}] + '"
                    )
            return html

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

        self._team_select = self._init_team_selector()
        self._workspace_select = self._init_workspace_selector()
        self._header_left_content = Container(
            [self._team_select, self._workspace_select], direction="horizontal"
        )

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
            if isinstance(col, str):
                self._columns_first_idx.append(col)
                self._columns_data.append(self.ColumnData(name=col))
            elif isinstance(col, tuple):
                self._columns_first_idx.append(col[0])
                self._columns_data.append(
                    self.ColumnData(name=col[0], is_widget=True, widget=col[1])
                )
            else:
                raise TypeError(f"Column name must be a string or a tuple, got {type(col)}")

        self._width = width
        self._show_header = True

        self._selected_rows = []
        self._selected_cell = None
        self._checked_rows = []

        self._project_id_to_info = {}

        self._allowed_project_types = allowed_project_types
        if isinstance(self._allowed_project_types, list):
            if all(isinstance(pt, ProjectType) for pt in self._allowed_project_types):
                self._allowed_project_types = [pt.value for pt in self._allowed_project_types]
        super().__init__(widget_id=widget_id, file_path=__file__)
        script_path = "./static/script.js"
        JinjaWidgets().context["__widget_scripts__"][self.__class__.__name__] = script_path

        if self._workspace_id:
            self._refresh_table()

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

    def _init_team_selector(self):
        team_select = Select(items=[], widget_id="team_selector")

        @team_select.value_changed
        def on_team_changed(team_id: int):
            self.team_id = team_id

        team_infos = self._api.team.get_list()

        self._teams = team_infos
        items = [Select.Item(info.id, info.name) for info in team_infos]
        team_select.set(items)
        if self._team_id is not None and self._team_id in [info.id for info in team_infos]:
            team_select.set_value(self._team_id)
        elif self._team_id is None and items:
            self._team_id = items[0].value
            team_select.set_value(self._team_id)

        return team_select

    def _init_workspace_selector(self):
        workspace_select = Select(items=[], widget_id="workspace_selector")

        @workspace_select.value_changed
        def on_workspace_changed(workspace_id: int):
            self.workspace_id = workspace_id

        if self._team_id:
            workspace_infos = self._api.workspace.get_list(self.team_id)
            items = [Select.Item(info.id, info.name) for info in workspace_infos]
            workspace_select.set(items)
            if self._workspace_id is not None and self._workspace_id in [
                info.id for info in workspace_infos
            ]:
                workspace_select.set_value(self._workspace_id)
            elif items and self._workspace_id is None:
                self._workspace_id = items[0].value
                workspace_select.set_value(self._workspace_id)

        return workspace_select

    @property
    def team_selector(self):
        """Get the team selector widget for template rendering."""
        return self._team_select

    @property
    def workspace_selector(self):
        """Get the workspace selector widget for template rendering."""
        return self._workspace_select

    @property
    def team_id(self) -> int:
        return self._team_id

    @team_id.setter
    def team_id(self, value: int):
        self._team_id = value
        self._refresh_workspace_select()

    def _refresh_workspace_select(self):
        workspace_infos = self._api.workspace.get_list(self.team_id)
        self._workspaces = workspace_infos
        items = [Select.Item(info.id, info.name) for info in workspace_infos]
        self._workspace_select.set(items)

    @property
    def workspace_id(self) -> int:
        return self._workspace_id

    @workspace_id.setter
    def workspace_id(self, value: int):
        self._workspace_id = value
        self._refresh_table()

    def _refresh_table(self):
        projects = self._api.project.get_list(self.workspace_id)
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
        self._data = table_data
        DataJson()[self.widget_id]["data"] = table_data
        DataJson().send_changes()

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
            "pageSize": self._page_size,
            "showHeader": self._show_header,
            "selectionChangedHandled": self._selection_changed_handled,
        }

    def get_json_state(self) -> Dict[str, Any]:
        """Returns dictionary with widget state.
        Dictionary contains the following fields:
            - search: search string
            - selectedRow: selected row
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
            "checkedRows": self._checked_rows,
            "page": self._active_page,
            "sort": {
                "column": self._sort_by,
                "order": self._sort_order,
            },
        }

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

    def get_selected_row(self) -> ClickedRow:
        """Returns the selected row.

        :return: Selected row
        :rtype: ClickedRow
        """
        row_data = StateJson()[self.widget_id]["selectedRow"]
        row_index = row_data["idx"]
        row = row_data["row"]
        if row_index is None or row is None:
            return None
        return self.ClickedRow(row, row_index)

    def get_selected_project(self) -> Optional[ProjectInfo]:
        """Returns the selected project info.

        :return: Selected project info or None if no project is selected
        :rtype: Optional[ProjectInfo]
        """
        selected_row = StateJson()[self.widget_id].get("selectedRow")
        if not selected_row:
            return None
        project_id = selected_row["row"].get("id")
        return self._project_id_to_info.get(project_id)

    def row_click(self, func: Callable[[ClickedRow], Any]) -> Callable[[], None]:
        """Decorator for function that handles row click event.

        :param func: Function that handles row click event
        :type func: Callable[[ClickedRow], Any]
        :return: Decorated function
        :rtype: Callable[[], None]
        """
        row_clicked_route_path = self.get_route_path(self.Routes.ROW_CLICKED)
        server = self._sly_app.get_server()

        self._row_click_handled = True

        @server.post(row_clicked_route_path)
        def _click():
            try:
                clicked_row = self.get_selected_row()
                if clicked_row is None:
                    return
                func(clicked_row)
            except Exception as e:
                logger.error(str(e), exc_info=True, extra={"exc_str": str(e)})
                raise e

        return _click

    def row_selected(self, func: Callable[[List[ClickedRow]], Any]) -> Callable[[], None]:
        """Decorator for function that handles row selection change event.

        :param func: Function that handles row selection change event
        :type func: Callable[[List[ClickedRow]], Any]
        :return: Decorated function
        :rtype: Callable[[], None]
        """
        selection_changed_route_path = self.get_route_path(self.Routes.SELECTION_CHANGED)
        server = self._sly_app.get_server()

        self._selection_changed_handled = True

        @server.post(selection_changed_route_path)
        def _selection_changed():
            try:
                selected_rows = StateJson()[self.widget_id].get("selectedRows", [])
                clicked_rows = [self.ClickedRow(row["row"], row["idx"]) for row in selected_rows]
                func(clicked_rows)
            except Exception as e:
                logger.error(str(e), exc_info=True, extra={"exc_str": str(e)})
                raise e

        return _selection_changed
