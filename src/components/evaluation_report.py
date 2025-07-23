from typing import Literal, Optional

import supervisely as sly
from supervisely.app.content import DataJson
from supervisely.app.widgets import Icons, SolutionCard
from supervisely.solution.base_node import SolutionCardNode, SolutionElement


class EvaluationReportNode(SolutionElement):
    def __init__(
        self,
        api: sly.Api,
        project_info: sly.ProjectInfo,
        benchmark_dir: str,
        title: str,
        description: str,
        width: int = 250,
        x: int = 0,
        y: int = 0,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        *args,
        **kwargs,
    ):
        """A node that displays a model evaluation report."""
        self.api = api
        self.project = project_info
        self.team_id = project_info.team_id
        self.title = title
        self.description = description
        self.width = width
        self.icon = icon or Icons(
            class_name="zmdi zmdi-open-in-new",
            color="#FF00A6",
            bg_color="#FFBCED",
        )
        self.tooltip_position = tooltip_position
        super().__init__(*args, **kwargs)

        self.set_benchmark_dir(self.benchmark_dir or benchmark_dir)
        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)

    def _create_card(self) -> SolutionCard:
        """
        Creates and returns the SolutionCard.
        """
        return SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            width=self.width,
            tooltip_position=self.tooltip_position,
            link=self.url,
            icon=self.icon,
        )

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
            if hasattr(self, "card"):
                self.card.link = ""
            return

        self.benchmark_dir = benchmark_dir
        lnk_path = f"{self._benchmark_dir.rstrip('/')}/visualizations/Model Evaluation Report.lnk"
        self.url = self._get_url_from_lnk_path(lnk_path)
        self.markdown_overview = self._get_overview_markdown()
        if hasattr(self, "card"):
            self.card.link = self.url

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        """
        Creates and returns the tooltip for the Manual Import widget.
        """
        return SolutionCard.Tooltip(
            description=self.description, properties=self._property_from_md()
        )

    def _get_url_from_lnk_path(self, remote_lnk_path) -> str:
        if not remote_lnk_path:
            sly.logger.warning("Remote link path is empty.")
            return ""
        if not self.api.file.exists(self.team_id, remote_lnk_path):
            sly.logger.warning(
                f"Link file {remote_lnk_path} does not exist in the benchmark directory."
            )
            return ""

        self.api.file.download(self.team_id, remote_lnk_path, "./model_evaluation_report.lnk")
        with open("./model_evaluation_report.lnk", "r") as file:
            base_url = file.read().strip()

        sly.fs.silent_remove("./model_evaluation_report.lnk")

        return sly.utils.abs_url(base_url)

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
