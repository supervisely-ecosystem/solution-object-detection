from typing import List, Literal, Optional

from src.components.project_table.project_table import DatasetTable, ProjectTable
from supervisely.api.api import Api
from supervisely.app import DataJson
from supervisely.app.widgets import (
    Button,
    Container,
    Dialog,
    Empty,
    Flexbox,
    Icons,
    ReloadableArea,
    SolutionCard,
    Text,
    Widget,
)
from supervisely.project.project_type import ProjectType
from supervisely.solution.base_node import SolutionCardNode, SolutionElement


# @TODO: DataJson save/load methods
class TrainingDataGUI(Widget):
    class ActivePage:
        PROJECT = "project"
        DATASET = "dataset"
        SPLITS = "splits"

    def __init__(
        self,
        api: Api,
        team_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        widget_id: Optional[str] = None,
    ):
        self.api = api
        self.team_id = team_id
        self.workspace_id = workspace_id

        self._active_page = self.ActivePage.PROJECT

        super().__init__(widget_id=widget_id)

    @property
    def modal(self) -> Dialog:
        if not hasattr(self, "_modal"):
            desc = (
                "Skip the initial steps of data import and annotation "
                "by copying already labeled data from your existing projects to "
                "Training Project. Select a team, workspace, and project — and the "
                "app will automatically detect and split datasets using naming "
                "conventions (train/val) or your defined Train/Val Split settings. "
                "All selected data will be copied into your training project "
                "and organized into collections for immediate use."
            )
            self._modal = Dialog(
                title="Copy Training Data from existing projects",
                content=Container(
                    [
                        Text(desc),
                        Empty(style="height: 20px;"),
                        self.reloadable_area,
                        Flexbox([self.back_btn, self.next_btn, self.run_btn]),
                    ]
                ),
            )
        return self._modal

    @property
    def active_page(self) -> Literal["project", "dataset", "splits"]:
        self._active_page = DataJson()[self.widget_id].get("active_page", "project")
        return self._active_page

    @active_page.setter
    def active_page(self, value: Literal["project", "dataset", "splits"]):
        if value not in self.ActivePage.__dict__.values():
            raise ValueError("active_page must be either 'project', 'dataset' or 'splits'")
        DataJson()[self.widget_id]["active_page"] = value
        DataJson().send_changes()

    @property
    def reloadable_area(self) -> ReloadableArea:
        if not hasattr(self, "_reloadable_area"):
            self._reloadable_area = ReloadableArea()
            self._set_modal_by_active_page()
        return self._reloadable_area

    @property
    def next_btn(self) -> Button:
        if not hasattr(self, "_next_btn"):
            self._next_btn = Button(
                "Next",
                button_size="small",
                icon="zmdi zmdi-arrow-right",
                style="primary",
            )

            @self._next_btn.click
            def _on_next_click():
                if self.active_page == self.ActivePage.PROJECT:
                    self.dataset_table.set_project(self.project_table.get_selected_project().id)
                    self.active_page = self.ActivePage.DATASET
                elif self.active_page == self.ActivePage.DATASET:
                    self.active_page = self.ActivePage.SPLITS
                self._set_modal_by_active_page(reload=True)

        return self._next_btn

    @property
    def back_btn(self) -> Button:
        if not hasattr(self, "_back_btn"):
            self._back_btn = Button(
                "Back",
                button_size="small",
                icon="zmdi zmdi-arrow-left",
                style="primary",
            )

            @self._back_btn.click
            def _on_back_click():
                if self.active_page == self.ActivePage.DATASET:
                    self.active_page = self.ActivePage.PROJECT
                elif self.active_page == self.ActivePage.SPLITS:
                    self.active_page = self.ActivePage.DATASET
                self._set_modal_by_active_page(reload=True)

        return self._back_btn

    @property
    def run_btn(self) -> Button:
        if not hasattr(self, "_run_btn"):
            self._run_btn = Button(
                "Run",
                button_size="small",
                icon="zmdi zmdi-play",
                style="primary",
            )
        return self._run_btn

    @property
    def project_table(self) -> ProjectTable:
        if not hasattr(self, "_project_table"):
            self._project_table = ProjectTable(
                team_id=self.team_id,
                workspace_id=self.workspace_id,
                allowed_project_types=[ProjectType.IMAGES],
                page_size=5,
            )

            @self._project_table.selection_changed
            def _project_selection_changed(project):
                if project is None:
                    self.next_btn.disable()
                else:
                    self.next_btn.enable()

        return self._project_table

    @property
    def dataset_table(self) -> DatasetTable:
        if not hasattr(self, "_dataset_table"):
            self._dataset_table = DatasetTable(page_size=5)

            @self._dataset_table.dataset_selection_changed
            def _dataset_selection_changed(datasets: List):
                if len(datasets) == 0:
                    self.next_btn.disable()
                else:
                    self.next_btn.enable()

        return self._dataset_table

    @property
    def splits_table(self) -> Container:
        if not hasattr(self, "_splits_table"):
            self._splits_table = Container(
                [
                    Text("Not implemented yet"),
                ]
            )
        return self._splits_table

    def get_json_data(self) -> dict:
        selected_project_id = None
        proj = self.project_table.get_selected_project()
        if proj is not None:
            selected_project_id = proj.id

        selected_dataset_ids = [ds.id for ds in self.dataset_table.get_selected_datasets()]
        return {
            "active_page": self._active_page,
            "team_id": self.project_table.team_workspace_select.get_selected_team_id(),
            "workspace_id": self.project_table.team_workspace_select.get_selected_workspace_id(),
            "selected_project_id": selected_project_id,
            "selected_dataset_ids": selected_dataset_ids,
        }

    def get_json_state(self) -> dict:
        return {}

    def _set_modal_by_active_page(self, reload: bool = False) -> Widget:
        if self.active_page == self.ActivePage.PROJECT:
            self.reloadable_area.set_content(self.project_table)
            self.back_btn.hide()
            self.next_btn.show()
            self.run_btn.hide()
            if self.project_table.get_selected_project() is None:
                self.next_btn.disable()
            else:
                self.next_btn.enable()
        elif self.active_page == self.ActivePage.DATASET:
            self.reloadable_area.set_content(self.dataset_table)
            self.back_btn.show()
            self.next_btn.show()
            self.run_btn.hide()
            if len(self.dataset_table.get_selected_datasets()) == 0:
                self.next_btn.disable()
            else:
                self.next_btn.enable()
        elif self.active_page == self.ActivePage.SPLITS:
            self.reloadable_area.set_content(self.splits_table)
            self.back_btn.show()
            self.next_btn.hide()
            self.run_btn.show()
            # TODO: splits_selected -> enable/disable run_btn
        if reload:
            self.reloadable_area.reload()


class TrainingDataNode(SolutionElement):
    def __init__(
        self,
        api: Api,
        title: str,
        width: int = 250,
        x: int = 0,
        y: int = 0,
        team_id: Optional[int] = None,
        workspace_id: Optional[int] = None,
        icon: Optional[Icons] = None,
        *args,
        **kwargs,
    ):
        self.api = api
        self.width = width
        icon = icon or Icons(
            "zmdi zmdi-collection-folder-image",
            color="#1976D2",
            bg_color="#E3F2FD",
        )
        super().__init__(*args, **kwargs)

        self.main_widget = TrainingDataGUI(api=self.api, team_id=team_id, workspace_id=workspace_id)

        @self.main_widget.run_btn.click
        def _on_run_click():
            self.main_widget.modal.hide()
            self.run()

        self.card = SolutionCard(title=title, icon=icon)

        @self.card.click
        def _on_click():
            self.main_widget.modal.show()

        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.main_widget.modal]

    def run(self):
        pass
