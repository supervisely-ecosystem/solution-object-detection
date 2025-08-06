from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional

from src.components.team_workspace_select.team_workspace_select import (
    TeamWorkspaceSelect,
)
from supervisely.api.api import SERVER_ADDRESS, Api
from supervisely.api.dataset_api import DatasetInfo
from supervisely.api.module_api import ApiField
from supervisely.api.project_api import ProjectInfo
from supervisely.app.widgets.selectable_fast_table import SelectableFastTable
from supervisely.project import ProjectType


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
        def on_team_workspace_change():
            self._team_id = self.team_workspace_select.get_selected_team_id()
            self._workspace_id = self.team_workspace_select.get_selected_workspace_id()
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

    def project_selection_changed(
        self, func: Callable[[Optional[ProjectInfo]], Any]
    ) -> Callable[[], None]:
        """Decorator for function that handles project selection change events.

        :param func: Function that handles project selection change, receives selected ProjectInfo or None
        :type func: Callable[[Optional[ProjectInfo]], Any]
        :return: Decorated function
        :rtype: Callable[[], None]
        """

        @self.selection_changed
        def _on_selection_changed(selected_row):
            selected_project = self.get_selected_project()
            func(selected_project)

        return _on_selection_changed


# @ TODO: Autoselect all datasets on init
class DatasetTable(SelectableFastTable):
    def __init__(
        self,
        project_id: int = None,
        sort_by: Literal["id", "name", "created_at", "items"] = "id",
        sort_order: Literal["asc", "desc"] = "asc",
        page_size: int = 10,
        width: str = "auto",
        widget_id: Optional[str] = None,
    ):
        self._api = Api()
        self._project_id = project_id
        self._datasets = []
        self._dataset_id_to_info = {}

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

        table_data = self._get_table_data() if project_id else []
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

    def set_project(self, project_id: int):
        """Sets the project ID and refreshes the dataset table."""
        self._project_id = project_id
        table_data = self._get_table_data()
        self._source_data = self._prepare_input_data(table_data)
        (
            self._parsed_source_data,
            self._sliced_data,
            self._parsed_active_data,
        ) = self._prepare_working_data()
        self._filter_changed()

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

        self._datasets = datasets
        self._dataset_id_to_info = {d.id: d for d in datasets}

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

    def get_selected_datasets(self) -> List[DatasetInfo]:
        """Returns the selected datasets info.

        :return: List of selected dataset info objects
        :rtype: List[DatasetInfo]
        """
        selected_rows = self.get_selected_rows()
        if not selected_rows:
            return []

        selected_datasets = []
        for row in selected_rows:
            dataset_id = row.row[1]
            dataset_info = self._dataset_id_to_info.get(dataset_id)
            if dataset_info:
                selected_datasets.append(dataset_info)

        return selected_datasets

    def dataset_selection_changed(
        self, func: Callable[[List[DatasetInfo]], Any]
    ) -> Callable[[], None]:
        """Decorator for function that handles dataset selection change events.

        :param func: Function that handles dataset selection change, receives list of selected DatasetInfo
        :type func: Callable[[List[DatasetInfo]], Any]
        :return: Decorated function
        :rtype: Callable[[], None]
        """

        @self.selection_changed
        def _on_selection_changed(selected_rows):
            selected_datasets = self.get_selected_datasets()
            func(selected_datasets)

        return _on_selection_changed
