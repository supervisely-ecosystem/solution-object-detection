import os
import tarfile
from tempfile import TemporaryDirectory
from typing import Literal, Optional

import supervisely as sly
import supervisely.io.fs as fs
from supervisely import logger
from supervisely.app.widgets import Dialog, Icons, Markdown, SolutionCard
from supervisely.solution.base_node import SolutionCardNode, SolutionElement


class MarkdownNode(SolutionElement):
    def __init__(
        self,
        content: str,
        title: str,
        description: str,
        width: int = 250,
        x: int = 0,
        y: int = 0,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        markdown_title: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """A node that displays a markdown content."""
        self.title = title
        self.description = description
        self.width = width
        self.icon = icon
        self.tooltip_position = tooltip_position

        self._markdown_content = content
        self._markdown_title = markdown_title

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.md_modal]
        self.card.click(self.md_modal.show)
        super().__init__(*args, **kwargs)

    @property
    def md_modal(self) -> Dialog:
        if not hasattr(self, "_md_modal"):
            self._md_modal = Dialog(
                title=self._markdown_title,
                content=Markdown(self._markdown_content, show_border=False),
            )
        return self._md_modal

    def _create_card(self) -> SolutionCard:
        """
        Creates and returns the SolutionCard.
        """
        return SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            width=self.width,
            tooltip_position=self.tooltip_position,
            icon=self.icon,
        )

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        """
        Creates a tooltip for the card.
        """
        return SolutionCard.Tooltip(self.description)


class OverviewNode(MarkdownNode):
    def __init__(
        self,
        api: sly.Api,
        app_slug: str,
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
        """A node that displays an overview."""
        self._api = api
        self._module_info = self._api.app.get_ecosystem_module_info(slug=app_slug)
        super().__init__(
            content=self._get_app_md(),
            # markdown_title=self._module_info.name,
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

    def _get_app_md(self) -> str:
        """
        Returns the markdown content for the overview.
        """

        eco_item_id = self._module_info.id
        eco_item_ver = self._module_info.get_latest_release()["version"]

        with TemporaryDirectory() as temp_dir:
            path = os.path.join(temp_dir, "repo.tar.gz")
            self._api.app.download_git_archive(eco_item_id, None, eco_item_ver, path)
            with tarfile.open(path) as archive:
                archive.extractall(temp_dir)

            markdowns = fs.list_files_recursively(temp_dir, [".md"], None, True)
            if not markdowns:
                logger.warning(
                    f"No markdown files found in the app {self._module_info.name} archive."
                )

            return open(markdowns[0], "r").read() if markdowns else ""
