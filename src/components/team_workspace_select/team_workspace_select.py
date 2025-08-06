from typing import Literal, Optional

from supervisely import env
from supervisely.api.api import Api
from supervisely.app.content import StateJson
from supervisely.app.widgets import Container, Empty, Select, Text, Widget


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
