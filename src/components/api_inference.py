import re
from typing import Literal, Optional

from supervisely.app.widgets import Dialog, Icons, Markdown, SolutionCard
from supervisely.sly_logger import logger
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

        self._markdown_title = markdown_title

        self.markdown = Markdown(content=content, show_border=False)

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.md_modal]
        super().__init__(*args, **kwargs)

    @property
    def md_modal(self) -> Dialog:
        if not hasattr(self, "_md_modal"):
            self._md_modal = Dialog(
                title=self._markdown_title,
                content=self.markdown,
            )
        return self._md_modal

    def _create_card(self) -> SolutionCard:
        """
        Creates and returns the SolutionCard.
        """
        card = SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            width=self.width,
            tooltip_position=self.tooltip_position,
            icon=self.icon,
        )

        @card.click
        def _on_card_click():
            self.md_modal.show()

        return card

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        """
        Creates a tooltip for the card.
        """
        return SolutionCard.Tooltip(self.description)


class ApiInferenceNode(MarkdownNode):
    def __init__(
        self,
        markdown_path: str,
        x: int = 0,
        y: int = 0,
        tooltip_position: Literal["left", "right"] = "right",
        markdown_title: Optional[str] = None,
        *args,
        **kwargs,
    ):
        """A node that displays API inference documentation."""
        self.content = open(markdown_path, "r", encoding="utf-8").read()
        super().__init__(
            content=self.content,
            title="API Inference",
            description="Documentation on how to interact with the deployed model using Supervisely API.",
            width=200,
            x=x,
            y=y,
            icon=Icons("zmdi zmdi-code", color="#1976D2", bg_color="#E3F2FD"),
            tooltip_position=tooltip_position,
            markdown_title=markdown_title,
            *args,
            **kwargs,
        )

    def set_task_id(self, task_id: int):
        """
        Sets the task ID for the API inference documentation.
        This method can be used to update the task ID dynamically.
        """
        if not isinstance(task_id, int):
            logger.error("Task ID must be an integer.")
            return

        updated_content = re.sub(r"task_id=\d+", f"task_id={task_id}", self.content)
        updated_content = re.sub(r"task_id=None", f"task_id={task_id}", updated_content)
        self.content = updated_content
        self.markdown.set_content(updated_content)
