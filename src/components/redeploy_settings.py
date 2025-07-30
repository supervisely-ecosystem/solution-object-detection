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
    Switch,
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
        agent_selector_field = Field(
            self.agent_selector,
            title="Select Agent to run task",
            description="Select the agent to deploy the model on.",
            icon=Field.Icon(
                zmdi_class="zmdi zmdi-storage",
                color_rgb=(21, 101, 192),
                bg_color_rgb=(227, 242, 253),
            ),
        )
        automation_field = Field(
            self.automation_switch,
            title="Enable Automation",
            description="Enable or disable automatic model deployment after training.",
            icon=Field.Icon(
                zmdi_class="zmdi zmdi-settings",
                color_rgb=(21, 101, 192),
                bg_color_rgb=(227, 242, 253),
            ),
        )

        return Container([agent_selector_field, automation_field], gap=20)

    @property
    def automation_switch(self) -> Switch:
        if not hasattr(self, "_automation_switch"):
            self._automation_switch = Switch(switched=True)
        return self._automation_switch

    @property
    def agent_selector(self) -> AgentSelector:
        if not hasattr(self, "_agent_selector"):
            self._agent_selector = AgentSelector(self.team_id)
        return self._agent_selector

    def get_json_data(self) -> dict:
        return {
            "enabled": self.automation_switch.is_switched(),
            "agent_id": self.agent_selector.get_value(),
        }

    def get_json_state(self) -> dict:
        return {}

    def save_settings(self, enabled: bool, agent_id: Optional[int] = None):
        DataJson()[self.widget_id]["settings"] = {
            "enabled": enabled,
            "agent_id": agent_id if agent_id is not None else self.agent_selector.get_value(),
        }
        DataJson().send_changes()

    def load_settings(self):
        data = DataJson().get(self.widget_id, {}).get("settings", {})
        enabled = data.get("enabled")
        agent_id = data.get("agent_id")
        self.update_widgets(enabled, agent_id)

    def update_widgets(self, enabled: bool, agent_id: Optional[int] = None):
        """Set re-deploy settings."""
        if enabled is True:
            self.automation_switch.on()
        elif enabled is False:
            self.automation_switch.off()
        else:
            pass  # do nothing, keep current state
        if agent_id is not None:
            self.agent_selector.set_value(agent_id)


class RedeploySettingsNode(SolutionElement):

    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        *args,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.main_widget = RedeploySettingsGUI(team_id=env_team_id())

        @self.main_widget.automation_switch.value_changed
        def on_automation_switch_change(value: bool):
            self.save(enabled=value)

        @self.main_widget.agent_selector.value_changed
        def on_agent_selector_change(value: int):
            self.save(agent_id=value)

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.settings_modal]

        self._update_properties(self.main_widget.automation_switch.is_switched())

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

    def _update_properties(self, enable: bool):
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
            enabled = self.main_widget.automation_switch.is_switched()
        if agent_id is None:
            agent_id = self.main_widget.agent_selector.get_value()

        self.main_widget.save_settings(enabled, agent_id)
        self._update_properties(enabled)

    def load_settings(self):
        """Load re-deploy settings from DataJson."""
        self.main_widget.load_settings()
        self._update_properties(self.main_widget.automation_switch.is_switched())

    def is_enabled(self) -> bool:
        """Check if re-deploy is enabled."""
        return self.main_widget.automation_switch.is_switched()

    def get_agent_id(self) -> Optional[int]:
        """Get selected agent ID for re-deploy."""
        return self.main_widget.agent_selector.get_value()
