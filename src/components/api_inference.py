from typing import Literal, Optional

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
        content = open(markdown_path, "r", encoding="utf-8").read()
        super().__init__(
            content=content,
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
