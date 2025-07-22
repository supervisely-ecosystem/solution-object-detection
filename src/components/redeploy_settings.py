# здесь будет класс, которые будет отвечать за деплой модели, показывать информацию о ней


from typing import List, Literal, Optional

from supervisely.app.content import DataJson
from supervisely.app.exceptions import show_dialog
from supervisely.app.widgets import (
    AgentSelector,
    Button,
    Checkbox,
    Container,
    Dialog,
    Field,
    Flexbox,
    Icons,
    Input,
    SolutionCard,
    Text,
    Widget,
)
from supervisely.io.env import team_id as env_team_id
from supervisely.solution.base_node import SolutionCardNode, SolutionElement


class RedeploySettingsGUI(Widget):
    def __init__(
        self,
        team_id: Optional[int] = None,
        widget_id: Optional[str] = None,
    ):
        self.team_id = team_id
        self.model = None
        super().__init__(widget_id=widget_id)
        self.content = self._init_gui()

    def _init_gui(self):
        return Container(
            widgets=[
                Container(
                    widgets=[
                        self.checkbox_field,
                        self.select_agent_field,
                        self.save_button_container,
                    ],
                    gap=20,
                ),
            ],
        )

    @property
    def checkbox_field(self):
        if not hasattr(self, "_checkbox_field"):
            self._checkbox_field = Field(
                title="Enable best Model Deployment",
                description="If enabled, the best model will be automatically deployed after comparing models.",
                content=self.checkbox,
            )
        return self._checkbox_field

    @property
    def checkbox(self):
        if not hasattr(self, "_checkbox"):
            self._checkbox = Checkbox(content="enable", checked=False)
        return self._checkbox

    @property
    def select_agent(self):
        if not hasattr(self, "_select_agent"):
            self._select_agent = AgentSelector(team_id=self.team_id, compact=True)
        return self._select_agent

    @property
    def select_agent_field(self):
        if not hasattr(self, "_select_agent_field"):
            self._select_agent_field = Field(
                title="Select Agent",
                content=self.select_agent_container,
                description="Select an agent to deploy the model.",
            )
        return self._select_agent_field

    @property
    def select_agent_container(self):
        if not hasattr(self, "_select_agent_container"):
            self._select_agent_container = Flexbox(
                [self.select_agent],
                vertical_alignment="center",
                gap=15,
                # style="padding-top: 10px;",
                # direction="horizontal",
            )
        return self._select_agent_container

    @property
    def save_button(self):
        if not hasattr(self, "_save_button"):
            self._save_button = Button(text="Save")
        return self._save_button

    @property
    def save_button_container(self):
        if not hasattr(self, "_save_button_container"):
            self._save_button_container = Container(
                widgets=[self.save_button],
                direction="horizontal",
                overflow="wrap",
                style="display: flex; justify-content: flex-end;",
                widgets_style="display: flex; flex: none;",
            )
        return self._save_button_container

    def get_json_data(self) -> dict:
        return {
            "enabled": self.checkbox.is_checked(),
            "agent_id": self.select_agent.get_value(),
        }

    def get_json_state(self) -> dict:
        return {}

    def save_settings(self, enabled: bool, agent_id: Optional[int] = None):
        DataJson()[self.widget_id]["redeploy_settings"] = {
            "enabled": enabled,
            "agent_id": agent_id,
        }
        DataJson().send_changes()

    def load_settings(self):
        data = DataJson().get(self.widget_id, {}).get("redeploy_settings", {})
        enabled = data.get("enabled")
        agent_id = data.get("agent_id")
        self.update_widgets(enabled, agent_id)

    def update_widgets(self, enabled: bool, agent_id: Optional[int] = None):
        """Set re-deploy settings."""
        if enabled is True:
            self.checkbox.check()
        elif enabled is False:
            self.checkbox.uncheck()
        else:
            pass  # do nothing, keep current state
        if agent_id is not None:
            self.select_agent.set_value(agent_id)


class RedeploySettingsNode(SolutionElement):

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        *args,
        **kwargs,
    ):
        self.main_widget = RedeploySettingsGUI(team_id=env_team_id())

        @self.main_widget.save_button.click
        def _on_save_button_click():
            self.settings_modal.hide()
            self.save()

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.settings_modal]
        super().__init__(*args, **kwargs)

    def _create_card(self) -> SolutionCard:
        card = SolutionCard(
            title="Re-deploy Best Model",
            tooltip=self._create_tooltip(),
            width=250,
            icon=Icons(
                class_name="zmdi zmdi-wrench",
                color="#1976D2",
                bg_color="#E3F2FD",
            ),
            tooltip_position="right",
        )

        @card.click
        def _on_card_click():
            self.settings_modal.show()

        return card

    def _create_tooltip(self):
        return SolutionCard.Tooltip(
            description="Specify settings for re-deploying the best model. After each training and models comparison (previous best vs new trained), if new model is better, it will be automatically deployed (if enabled).",
            properties=[],
        )

    @property
    def settings_modal(self) -> Widget:
        if not hasattr(self, "_settings_modal"):
            self._settings_modal = self._create_settings_modal()
        return self._settings_modal

    def _create_settings_modal(self) -> Dialog:
        return Dialog(
            title="Deploy Settings",
            content=self.main_widget.content,
            size="tiny",
        )

    def update_properties(self, enable: bool):
        """Update node properties with current re-deploy settings."""
        value = "enabled" if enable else "disabled"
        self.node.update_property("Re-deploy the best model", value, highlight=enable)
        if enable:
            self.node.show_automation_badge()
        else:
            self.node.hide_automation_badge()

    def save(self, enabled: Optional[bool] = None, agent_id: Optional[int] = None):
        """Save re-deploy settings."""
        if enabled is None:
            enabled = self.main_widget.checkbox.is_checked()
        if agent_id is None:
            agent_id = self.main_widget.select_agent.get_value()

        self.main_widget.save_settings(enabled, agent_id)
        self.update_properties(enabled)

    def load_settings(self):
        """Load re-deploy settings from DataJson."""
        self.main_widget.load_settings()
        self.update_properties(self.main_widget.checkbox.is_checked())
        self.save()

    def is_enabled(self) -> bool:
        """Check if re-deploy is enabled."""
        return self.main_widget.checkbox.is_checked()

    def get_agent_id(self) -> Optional[int]:
        """Get selected agent ID for re-deploy."""
        return self.main_widget.select_agent.get_value()
