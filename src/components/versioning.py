from datetime import datetime as dt

from src.components.empty import EmptyNode
from supervisely.api.api import Api
from supervisely.app.widgets import Icons


class DataVersioningNode(EmptyNode):
    """
    Versioning node for managing model versions and their metadata.
    It is used to track different versions of models and their associated data.
    """

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        api: Api = None,
        project_id: int = 0,
        tooltip_position: str = "right",
    ) -> None:
        self.api = api
        self.project_id = project_id
        super().__init__(
            title="Data Versioning",
            description="Versioning allows you to track changes in your datasets over time. Each version is a snapshot of the dataset at a specific point in time, enabling you to revert to previous versions if needed.",
            width=250,
            x=x,
            y=y,
            tooltip_position=tooltip_position,
            icon=Icons(class_name="zmdi zmdi-time-restore", color="#1976D2", bg_color="#E3F2FD"),
        )
        self.refresh()

    def _update_properties(self) -> None:
        versions = self.api.project.version.get_list(self.project_id)
        link = self.api.project.url(self.project_id).replace("datasets", "versions")
        self.node.update_property("Number of Versions", f"{len(versions)} (view all ↗)", link=link)
        if versions:
            latest_version = versions[-1]
            created_at: str = latest_version.created_at  # str
            created_at = dt.fromisoformat(created_at).strftime("%Y/%B/%d %H:%M")

            self.node.update_property("Latest Version", latest_version.name)
            self.node.update_property("Created At", created_at)
        else:
            self.node.remove_property_by_key("Latest Version")
            self.node.remove_property_by_key("Created At")

    def refresh(self) -> None:
        """
        Refreshes the versioning node to update its properties.
        This method is called to ensure the node displays the latest version information.
        """
        self._update_properties()
