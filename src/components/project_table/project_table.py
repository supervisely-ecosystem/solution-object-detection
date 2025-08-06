from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from supervisely import env
from supervisely.api.api import SERVER_ADDRESS, Api
from supervisely.api.module_api import ApiField
from supervisely.api.project_api import ProjectInfo
from supervisely.app.content import DataJson, StateJson
from supervisely.app.widgets import Container, Empty, Select, Text
from supervisely.app.widgets.selectable_fast_table import SelectableFastTable
from supervisely.app.widgets.widget import Widget
from supervisely.project import ProjectType


class TeamWorkspaceSelect(Widget):
    class Routes:
        VALUE_CHANGED = "value_changed"

    def __init__(
        self,
        show_label: bool = True,
        direction: Literal["horizontal", "vertical"] = "vertical",
        default_team_id: Optional[int] = None,
        default_workspace_id: Optional[int] = None,
        size: Literal["large", "small", "mini"] = None,
        widget_id=None,
    ):
        self._api = Api()
        self._direction = direction
        self._show_label = show_label
        self._size = size
        self._team_id = default_team_id
        self._workspace_id = default_workspace_id
        if self._team_id is None and self._workspace_id is None:
            self._team_id = env.team_id()
            self._workspace_id = self._api.workspace.get_list(self._team_id)[0].id
        elif self._team_id is None and self._workspace_id is not None:
            self._team_id = self._api.workspace.get_info_by_id(self._workspace_id).team_id
        elif self._team_id is not None and self._workspace_id is not None:
            actual_workspace_team_id = self._api.workspace.get_info_by_id(
                self._workspace_id
            ).team_id
            if self._team_id != actual_workspace_team_id:
                raise ValueError(
                    f"Provided team_id {self._team_id} does not match the team of the workspace {self._workspace_id}."
                )
        self.team_selector.set_value(self._team_id)
        self.workspace_selector.set_value(self._workspace_id)
        self._style = (
            "justify-content: center; align-items: center;" if direction == "horizontal" else ""
        )
        self._gap = 15 if direction == "horizontal" else 10
        self._changes_handled = False
        super().__init__(widget_id=widget_id, file_path=__file__)

    @property
    def _content(self):
        return Container(
            [
                self.team_label,
                self.team_selector,
                self.workspace_label,
                self.workspace_selector,
            ],
            direction=self._direction,
            style=self._style,
            gap=self._gap,
        )

    @property
    def team_selector(self):
        if not hasattr(self, "_team_selector"):
            items = [Select.Item(team.id, team.name) for team in self._api.team.get_list()]
            select = Select(items=items, size=self._size)

            @select.value_changed
            def on_team_change(value: int):
                self._team_id = value
                self._update_workspace_selector()

                if hasattr(self, "_value_change_callback") and self._value_change_callback:
                    result = {"teamId": self._team_id, "workspaceId": self._workspace_id}
                    self._value_change_callback(result)

            self._team_selector = select
        return self._team_selector

    @property
    def workspace_selector(self):
        if not hasattr(self, "_workspace_selector"):
            items = [
                Select.Item(ws.id, ws.name) for ws in self._api.workspace.get_list(self._team_id)
            ]
            select = Select(items=items, size=self._size)

            @select.value_changed
            def on_workspace_change(value: int):
                self._workspace_id = value
                StateJson()[self.widget_id]["workspaceId"] = value
                StateJson().send_changes()

                if hasattr(self, "_workspace_change_callback") and self._workspace_change_callback:
                    result = {"teamId": self._team_id, "workspaceId": value}
                    self._workspace_change_callback(result)

            self._workspace_selector = select
        return self._workspace_selector

    @property
    def team_label(self):
        if not hasattr(self, "_team_label"):
            if self._show_label:
                self._team_label = Text(text="Team")
            else:
                self._team_label = Empty()
        return self._team_label

    @property
    def workspace_label(self):
        if not hasattr(self, "_workspace_label"):
            if self._show_label:
                self._workspace_label = Text(text="Workspace")
            else:
                self._workspace_label = Empty()
        return self._workspace_label

    def get_selected_team_id(self) -> Optional[int]:
        return StateJson()[self.widget_id]["teamId"]

    def get_selected_workspace_id(self) -> Optional[int]:
        return StateJson()[self.widget_id]["workspaceId"]

    def _update_workspace_selector(self):
        items = [Select.Item(ws.id, ws.name) for ws in self._api.workspace.get_list(self._team_id)]
        self.workspace_selector.set(items)
        if self._workspace_id not in [item for item in items]:
            self.workspace_selector.set_value(items[0].value)
        else:
            self.workspace_selector.set_value(self._workspace_id)

    def get_json_data(self):
        return {}

    def get_json_state(self):
        return {"teamId": self._team_id, "workspaceId": self._workspace_id}

    def get_value(self):
        """Returns the current workspace selection info"""
        return {"teamId": self._team_id, "workspaceId": self._workspace_id}

    def value_changed(self, func):
        """Register a callback function to be called when team or workspace selection changes"""
        self._value_change_callback = func
        self._changes_handled = True
        self._workspace_change_callback = func

        return func


class ProjectTable(SelectableFastTable):
    """ProjectTable widget for displaying and selecting projects."""

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

        columns = ["Project", "ID", "Date Modified", "Type", "Assets"]

        sort_by_to_column_idx = {
            "name": 0,
            "date": 2,
            "assets": 4,
        }
        sort_column_idx = sort_by_to_column_idx.get(sort_by, 2)

        columns_options = [
            {"customCell": True},  # Project Name column
            {},  # ID column
            {},  # Date Modified column
            {},  # Type column
            {},  # Assets column
        ]

        @self.team_workspace_select.value_changed
        def on_team_workspace_change(value: Dict[str, int]):
            self._team_id, self._workspace_id = value.values()
            self.loading = True
            self._refresh_table()
            self.loading = False

        if self._team_id is None:
            self._team_id = self.team_workspace_select.get_selected_team_id()
        if self._workspace_id is None:
            self._workspace_id = self.team_workspace_select.get_selected_workspace_id()

        self._projects = []
        self._project_id_to_info = {}
        self._allowed_project_types = allowed_project_types
        if isinstance(self._allowed_project_types, list):
            if all(isinstance(pt, ProjectType) for pt in self._allowed_project_types):
                self._allowed_project_types = [pt.value for pt in self._allowed_project_types]

        table_data = self._get_table_data()
        super().__init__(
            data=table_data,
            columns=columns,
            columns_options=columns_options,
            page_size=page_size,
            sort_column_idx=sort_column_idx,
            sort_order=sort_order,
            width=width,
            widget_id=widget_id,
            show_header=True,
            is_selectable=True,
            header_left_content=self.team_workspace_select,
            max_selected_rows=1,
        )

    @property
    def team_workspace_select(self) -> TeamWorkspaceSelect:
        if not hasattr(self, "_team_workspace_select"):
            selector = TeamWorkspaceSelect(
                show_label=True,
                direction="horizontal",
                default_team_id=self._team_id,
                default_workspace_id=self._workspace_id,
            )
            self._team_workspace_select = selector
        return self._team_workspace_select

    def _get_table_data(self) -> List[List[Any]]:
        """Refresh the table with current workspace projects."""
        if not self._workspace_id:
            return []
        projects = self._api.project.get_list(
            self._workspace_id,
            fields=[
                ApiField.ID,
                ApiField.NAME,
                ApiField.TYPE,
                ApiField.CREATED_AT,
                ApiField.IMAGES_COUNT,
                ApiField.REFERENCE_IMAGE_URL,
            ],
        )
        if self._allowed_project_types:
            projects = [p for p in projects if p.type in self._allowed_project_types]
        id_to_preview = {
            info.id: info.image_preview_url
            for info in projects
            if info.image_preview_url.rstrip("/") != SERVER_ADDRESS
        }

        self._projects = projects
        self._project_id_to_info = {p.id: p for p in projects}

        table_data = []
        for project in projects:
            row_data = [
                (
                    project.name,
                    id_to_preview.get(project.id, None),
                ),
                project.id,
                datetime.strptime(
                    project.created_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f"
                ).strftime("%d %b %Y %H:%M"),
                project.type.replace("_", " ").title(),
                project.items_count or 0,
            ]
            table_data.append(row_data)

        return table_data

    def _refresh_table(self):
        """Refresh the table with current workspace projects."""
        table_data = self._get_table_data()
        self._source_data = self._prepare_input_data(table_data)
        (
            self._parsed_source_data,
            self._sliced_data,
            self._parsed_active_data,
        ) = self._prepare_working_data()
        self._filter_changed()

    def get_selected_project(self) -> Optional[ProjectInfo]:
        """Returns the selected project info.

        :return: Selected project info or None if no project is selected
        :rtype: Optional[ProjectInfo]
        """
        selected_row = self.get_selected_row()
        if not selected_row:
            return None

        project_id = selected_row.row[1]
        return self._project_id_to_info.get(project_id)

    def refresh_projects(self):
        """Refresh the project list from the current workspace."""
        if self._workspace_id:
            self._refresh_table()

    def set_workspace(self, workspace_id: int):
        """Set the workspace and refresh the project list.

        :param workspace_id: ID of the workspace to display projects from
        :type workspace_id: int
        """
        self._workspace_id = workspace_id
        self.refresh_projects()

    def get_all_projects(self) -> List[ProjectInfo]:
        """Get all projects currently displayed in the table.

        :return: List of all project info objects
        :rtype: List[ProjectInfo]
        """
        return self._projects

    # def project_selection_changed(
    #     self, func: Callable[[Optional[ProjectInfo]], Any]
    # ) -> Callable[[], None]:
    #     """Decorator for function that handles project selection change events.

    #     :param func: Function that handles project selection change, receives selected ProjectInfo or None
    #     :type func: Callable[[Optional[ProjectInfo]], Any]
    #     :return: Decorated function
    #     :rtype: Callable[[], None]
    #     """

    #     @self.selection_changed
    #     def _on_selection_changed(selected_row):
    #         selected_project = self.get_selected_project()
    #         func(selected_project)

    #     return _on_selection_changed


# @ TODO: Autoselect all datasets on init
class DatasetTable(SelectableFastTable):
    def __init__(
        self,
        project_id: int,
        sort_by: Literal["id", "name", "created_at", "items"] = "id",
        sort_order: Literal["asc", "desc"] = "asc",
        page_size: int = 10,
        width: str = "auto",
        widget_id: Optional[str] = None,
    ):
        self._api = Api()
        self._project_id = project_id

        columns = ["Dataset", "ID", "Created At", "Items"]

        sort_by_to_column_idx = {
            "name": 0,
            "id": 1,
            "created_at": 2,
            "items": 3,
        }
        sort_column_idx = sort_by_to_column_idx.get(sort_by, 1)

        columns_options = [
            {"customCell": True},  # Dataset Name column
            {},  # ID column
            {},  # Created at column
            {},  # Items column
        ]

        table_data = self._get_table_data()
        super().__init__(
            data=table_data,
            columns=columns,
            columns_options=columns_options,
            page_size=page_size,
            sort_column_idx=sort_column_idx,
            sort_order=sort_order,
            width=width,
            widget_id=widget_id,
            show_header=True,
            is_selectable=True,
            header_left_content=None,
        )

    def _get_table_data(self) -> List[List[Any]]:
        """Refresh the table with current project datasets."""
        datasets = []
        id_to_image_preview = {}
        id_to_full_name = {}
        for parents, dataset_info in self._api.dataset.tree(self._project_id):
            full_name = "/".join(parents + [dataset_info.name])
            id_to_full_name[dataset_info.id] = full_name
            id_to_image_preview[dataset_info.id] = dataset_info.image_preview_url
            datasets.append(dataset_info)

        table_data = []
        for dataset in datasets:
            row_data = [
                (
                    id_to_full_name.get(dataset.id, dataset.name),
                    id_to_image_preview.get(dataset.id, None),
                ),
                dataset.id,
                datetime.strptime(
                    dataset.created_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f"
                ).strftime("%d %b %Y %H:%M"),
                dataset.items_count or 0,
            ]
            table_data.append(row_data)

        return table_data
