from typing import Literal, Optional

from supervisely import env
from supervisely.api.api import Api
from supervisely.app import widgets as w
from supervisely.app.content import DataJson, StateJson


class TeamWorkspaceSelect(w.Widget):
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
        self._team_id = default_team_id or env.team_id()
        self._workspace_id = default_workspace_id or env.workspace_id()
        self._style = (
            "justify-content: center; align-items: center;" if direction == "horizontal" else ""
        )
        self._gap = 15 if direction == "horizontal" else 10
        self._changes_handled = False
        super().__init__(widget_id=widget_id, file_path=__file__)

    @property
    def _content(self):
        return w.Container(
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
            items = [w.Select.Item(team.id, team.name) for team in self._api.team.get_list()]
            select = w.Select(items=items, size=self._size)

            @select.value_changed
            def on_team_change(value: int):
                self._team_id = value
                self._update_workspace_selector()

            self._team_selector = select
        return self._team_selector

    @property
    def workspace_selector(self):
        if not hasattr(self, "_workspace_selector"):
            items = [
                w.Select.Item(ws.id, ws.name) for ws in self._api.workspace.get_list(self._team_id)
            ]
            select = w.Select(items=items, size=self._size)

            @select.value_changed
            def on_workspace_change(value: int):
                self._workspace_id = value
                # Update state
                StateJson()[self.widget_id]["workspaceId"] = value
                StateJson().send_changes()

                # Call the callback directly if it exists
                if hasattr(self, "_workspace_change_callback") and self._workspace_change_callback:
                    result = {"teamId": self._team_id, "workspaceId": value}
                    self._workspace_change_callback(result)

            self._workspace_selector = select
        return self._workspace_selector

    @property
    def team_label(self):
        if not hasattr(self, "_team_label"):
            if self._show_label:
                self._team_label = w.Text(text="Team")
            else:
                self._team_label = w.Empty()
        return self._team_label

    @property
    def workspace_label(self):
        if not hasattr(self, "_workspace_label"):
            if self._show_label:
                self._workspace_label = w.Text(text="Workspace")
            else:
                self._workspace_label = w.Empty()
        return self._workspace_label

    def get_selected_team_id(self) -> Optional[int]:
        return StateJson()[self.widget_id]["teamId"]

    def get_selected_workspace_id(self) -> Optional[int]:
        return StateJson()[self.widget_id]["workspaceId"]

    def _update_workspace_selector(self):
        items = [
            w.Select.Item(ws.id, ws.name) for ws in self._api.workspace.get_list(self._team_id)
        ]
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
        return self.workspace_selector.value_changed(func)
