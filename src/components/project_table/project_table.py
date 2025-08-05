from datetime import datetime
from typing import Any, Callable, Dict, List, Literal, Optional

import pandas as pd

from src.components.team_workspace_select.team_workspace_select import (
    TeamWorkspaceSelect,
)
from supervisely import logger
from supervisely._utils import abs_url
from supervisely.api.api import Api
from supervisely.api.project_api import ProjectInfo
from supervisely.app.widgets.selectable_fast_table.selectable_fast_table import (
    SelectableFastTable,
)
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
        self._allowed_project_types = allowed_project_types

        if isinstance(self._allowed_project_types, list):
            if all(isinstance(pt, ProjectType) for pt in self._allowed_project_types):
                self._allowed_project_types = [pt.value for pt in self._allowed_project_types]

        self._projects = []
        self._project_id_to_info = {}

        columns = ["Project Name", "ID", "Date Modified", "Type", "Assets"]

        sort_by_to_column_idx = {
            "name": 0,
            "date": 2,
            "assets": 4,
        }
        sort_column_idx = sort_by_to_column_idx.get(sort_by)

        columns_options = [
            {"customCell": True},  # Project Name column
            {},  # ID column
            {},  # Date Modified column
            {},  # Type column
            {},  # Assets column
        ]

        super().__init__(
            data=[],
            columns=columns,
            columns_options=columns_options,
            page_size=page_size,
            sort_column_idx=sort_column_idx,
            sort_order=sort_order,
            width=width,
            is_selectable=True,
            max_selected_rows=1,
            header_left_content=self.team_workspace_select,
            widget_id=widget_id,
        )

        if self._workspace_id:
            self._refresh_table()

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

    def _refresh_table(self):
        """Refresh the table with current workspace projects."""
        projects = self._api.project.get_list(self._workspace_id)
        if self._allowed_project_types:
            projects = [p for p in projects if p.type in self._allowed_project_types]

        self._projects = projects
        self._project_id_to_info = {p.id: p for p in projects}

        table_data = []
        for i, project in enumerate(projects):
            row_data = [
                (
                    project.name,
                    abs_url(project.reference_image_url),
                ),  # Tuple for image injection
                project.id,
                datetime.strptime(
                    project.created_at.replace("Z", ""), "%Y-%m-%dT%H:%M:%S.%f"
                ).strftime("%d %b %Y %H:%M"),
                project.type.replace("_", " ").title(),
                project.items_count,
            ]
            table_data.append(row_data)

        self.read_pandas(pd.DataFrame(table_data, columns=self._columns_first_idx))

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
