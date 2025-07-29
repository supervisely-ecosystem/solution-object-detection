from typing import Literal, Optional

import supervisely as sly
from supervisely._utils import abs_url, is_development
from supervisely.app.content import DataJson
from supervisely.app.widgets import Icons
from supervisely.io.env import team_id as env_team_id
from supervisely.solution.components.link_node import LinkNode


class EvaluationReportNode(LinkNode):
    def __init__(
        self,
        api: sly.Api,
        team_id: Optional[int] = None,
        benchmark_dir: Optional[str] = None,
        title: Optional[str] = "Evaluation Report",
        description: Optional[str] = None,
        width: int = 250,
        x: int = 0,
        y: int = 0,
        tooltip_position: Literal["left", "right"] = "right",
        *args,
        **kwargs,
    ):
        """A node that displays a model evaluation report."""
        self.api = api
        self.team_id = team_id or env_team_id()
        icon = Icons(class_name="zmdi zmdi-collection-text", color="#FF00A6", bg_color="#FFBCED")
        super().__init__(
            title=title,
            description=description,
            width=width,
            x=x,
            y=y,
            icon=icon,
            tooltip_position=tooltip_position,
            *args,
            **kwargs,
        )

        if benchmark_dir is not None:
            self.set_benchmark_dir(benchmark_dir or self.benchmark_dir)

    @property
    def benchmark_dir(self) -> str:
        """
        Returns the benchmark directory for the evaluation report.
        """
        self._benchmark_dir = DataJson()[self.widget_id].get("benchmark_dir", None)
        return self._benchmark_dir

    @benchmark_dir.setter
    def benchmark_dir(self, benchmark_dir: str):
        """
        Sets the benchmark directory for the evaluation report.
        """
        self._benchmark_dir = benchmark_dir
        DataJson()[self.widget_id]["benchmark_dir"] = benchmark_dir
        DataJson().send_changes()

    def set_benchmark_dir(self, benchmark_dir: str):
        """
        Sets the benchmark directory for the evaluation report.
        """
        if not benchmark_dir:
            self.benchmark_dir = None
            self.url = ""
            self.markdown_overview = None
            self.card.link = ""
            return

        self.benchmark_dir = benchmark_dir
        lnk_path = f"{self._benchmark_dir.rstrip('/')}/visualizations/Model Evaluation Report.lnk"
        self.url = self._get_url_from_lnk_path(lnk_path)
        self.markdown_overview = self._get_overview_markdown()
        self.card.link = self.url

    def _get_url_from_lnk_path(self, remote_lnk_path) -> str:
        if not remote_lnk_path:
            sly.logger.warning("Remote link path is empty.")
            return ""

        file_info = self.api.storage.get_info_by_path(self.team_id, remote_lnk_path)
        if not file_info:
            sly.logger.warning(f"File info not found for path: {remote_lnk_path}")
            return ""
        report_path = f"/model-benchmark?id={file_info.id}"
        return abs_url(report_path) if is_development() else report_path

    def _get_overview_markdown(self) -> str:
        """
        Returns the overview markdown for the evaluation report.
        """
        from tempfile import TemporaryDirectory

        if not self.benchmark_dir:
            sly.logger.warning("Benchmark directory is not set.")
            return None

        vis_data_dir = "{}visualizations/data/".format(self.benchmark_dir)
        for filepath in self.api.file.listdir(self.team_id, vis_data_dir):
            if "markdown_overview_markdown" in filepath:
                with TemporaryDirectory() as temp_dir:
                    local_path = f"{temp_dir}/markdown_overview.md"
                    self.api.file.download(self.team_id, filepath, local_path)
                    with open(local_path, "r") as f:
                        lines = f.readlines()
                        return "".join(lines[:-1]) if len(lines) > 1 else ""

        sly.logger.warning("No overview markdown found in the benchmark directory.")
        return None

    def _property_from_md(self):
        """
        Extracts properties from the markdown overview.
        """
        if not self.markdown_overview:
            return {}

        keys_to_ignore = [
            "Task type",
            "Ground Truth project",
            "Training dashboard",
            "Averaging across IoU thresholds",
            "Checkpoint file",
        ]

        def remove_href_from_value(value: str) -> str:
            """
            Removes any href links from the value string.
            """
            if "<a" not in value:
                return value.strip()

            start = value.find("<a")
            return value[:start].strip().rstrip(",")

        properties = []
        lines = self.markdown_overview.split("\n")
        for line in lines:
            if line.strip() == "":
                continue
            if ":" in line:
                key, value = line.split(":", 1)
                key = key.replace("**", "").replace("-", "").strip()
                if key in keys_to_ignore:
                    continue
                value = remove_href_from_value(value)
                properties.append({"key": key, "value": value, "link": False, "highlight": False})

        return properties

    def show_new_report_badge(self):
        """Shows a badge indicating that a new evaluation report is available."""
        self.card.update_badge_by_key(key="📋", label="new report", badge_type="success")

    def hide_new_report_badge(self):
        """Hides the new report badge."""
        self.card.remove_badge_by_key("📋")
