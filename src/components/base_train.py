# здесь будет класс, которые будет отвечать за деплой модели, показывать информацию о ней


from typing import Callable, List, Literal, Optional, Tuple, Union

import supervisely.io.env as sly_env
from supervisely import ProjectMeta
from supervisely.annotation.obj_class import ObjClass
from supervisely.api.api import Api
from supervisely.api.project_api import ProjectInfo
from supervisely.app.exceptions import show_dialog
from supervisely.app.widgets import (
    AgentSelector,
    Button,
    Container,
    Dialog,
    Field,
    Flexbox,
    Icons,
    Input,
    NewExperiment,
    SolutionCard,
    TasksHistory,
    Text,
    Widget,
)
from supervisely.nn.task_type import TaskType
from supervisely.project.project_type import ProjectType
from supervisely.sly_logger import logger
from supervisely.solution.base_node import Automation, SolutionCardNode, SolutionElement
from supervisely.solution.components.tasks_history import SolutionTasksHistory


class TrainAutomation(Automation):
    TRAIN_JOB_ID = "train_model_job"
    check_status_job_id = "check_train_status_job"

    def __init__(self, func: Callable):
        super().__init__()
        self.func = func
        self.widget = self._create_widget()
        self.job_id = self.widget.widget_id

    def _create_widget(self) -> Container:
        pass

    def apply(self, sec: int, job_id: str, *args) -> None:
        self.scheduler.add_job(self.func, interval=sec, job_id=job_id, replace_existing=True, *args)
        logger.info(f"Scheduled model comparison job with ID {job_id} every {sec} seconds.")

    def remove(self, job_id: str) -> None:
        if self.scheduler.is_job_scheduled(job_id):
            self.scheduler.remove_job(job_id)
            logger.info(f"Removed scheduled model comparison job with ID {job_id}.")


class TrainTasksHistory(SolutionTasksHistory):
    def __init__(self, api: Api, title: str = "Tasks History"):
        super().__init__(api, title)
        self.tasks_history.table_columns = [
            "Task ID",
            "Model Name",
            "Started At",
            "Status",
            "Hardware",
            "Device",
            # "Classes Count",
            "Images Count",
            "Train Collection",
            "Validation Collection",
        ]
        self.tasks_history.table_columns_keys = [
            ["id"],
            ["model_name"],
            ["task_info", "created_at"],
            ["status"],
            ["hardware"],
            ["device"],
            # ["classes_count"],
            ["images_count"],
            ["train_collection_name"],
            ["validation_collection_name"],
        ]


class BaseTrainGUI(Widget):
    cv_task: TaskType = TaskType.OBJECT_DETECTION
    frameworks: Optional[List[str]] = None

    def __init__(
        self,
        api: Api,
        project: Union[ProjectInfo, int],
        workspace_id: Optional[int] = None,
        team_id: Optional[int] = None,
        widget_id: Optional[str] = None,
    ):
        self.api = api
        self.project = (
            project
            if isinstance(project, ProjectInfo)
            else self.api.project.get_info_by_id(project)
        )
        self.workspace_id = workspace_id or self.project.workspace_id
        self.team_id = team_id or self.project.team_id
        super().__init__(widget_id=widget_id)
        self.content = self._init_gui()

    def _init_gui(self) -> NewExperiment:
        train_collections, val_collections = self._get_train_val_collections()
        split_mode = "collections" if train_collections and val_collections else "random"
        
        project_meta = ProjectMeta.from_json(self.api.project.get_meta(self.project.id))
        classes = [obj_cls.name for obj_cls in project_meta.obj_classes]

        content = NewExperiment(
            team_id=self.team_id,
            workspace_id=self.workspace_id,
            project_id=self.project.id,
            classes=classes,
            step=5, # 5 - start with model selection
            filter_projects_by_workspace=True,
            project_types=[ProjectType.IMAGES],
            cv_task=self.cv_task,
            selected_frameworks=self.frameworks,
            train_val_split_mode=split_mode, # only collections?
            train_collections=train_collections,
            val_collections=val_collections,
            # gui selectors disabled
            cv_task_selection_disabled=True, # 1 - cv task selection
            project_selection_disabled=True, # 2 - project selection
            classes_selection_disabled=False, # 3 - classes selection
            train_val_split_selection_disabled=True, # 4 - train/val split selection
            model_selection_disabled=False, # 5 - model selection
            evaluation_selection_disabled=False, # 9 - evaluation selection
            speed_test_selection_disabled=False, # 9 - speed test selection
            framework_selection_disabled=self.frameworks is not None,
            architecture_selection_disabled=True,
        )

        @content.visible_changed
        def _on_visible_changed(visible: bool):
            print(f"NewExperiment visibility changed: {visible}")

        return content

    def _get_train_val_collections(self) -> Tuple[List[int], List[int]]:
        if self.project.type != ProjectType.IMAGES.value:
            return [], []
        train_collections, val_collections = [], []
        all_collections = self.api.entities_collection.get_list(self.project.id)
        for collection in all_collections:
            if collection.name == "All_train":
                train_collections.append(collection.id)
            elif collection.name == "All_val":
                val_collections.append(collection.id)

        return train_collections, val_collections

    def get_json_data(self):
        return {}

    def get_json_state(self):
        return {}


class BaseTrainNode(SolutionElement):
    gui_class = BaseTrainGUI
    title = "Train Model"
    description = "Train a model on the selected project. The model will be trained on the training collection and validated on the validation collection. If collections are not set, the model will be trained on random split of the project images."

    def __init__(
        self,
        api: Api,
        project: Union[ProjectInfo, int],
        x: int = 0,
        y: int = 0,
        icon: Optional[Icons] = None,
        *args,
        **kwargs,
    ):
        self.icon = icon
        self.width = 250
        self.project_id = project.id if isinstance(project, ProjectInfo) else project

        self.api = api
        self.tasks_history = TrainTasksHistory(self.api, title="Train Tasks History")
        self.main_widget = self.gui_class(api=api, project=self.project_id)
        # self.automation = TrainAutomation(self.main_widget.a)

        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [
            self.tasks_history.tasks_modal,
            self.tasks_history.logs_modal,
            self.main_widget.content,
        ]
        self._train_started_cb = []
        self._train_finished_cb = []
        super().__init__(*args, **kwargs)

        @self.card.click
        def _on_card_click():
            # if not self.main_widget.content.visible:
            self.main_widget.content.visible = True

    def _create_card(self) -> SolutionCard:
        return SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            width=self.width,
            icon=self.icon,
            tooltip_position="right",
        )

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        return SolutionCard.Tooltip(
            description=self.description,
            content=[self.tasks_button, self.open_session_button],
        )

    @property
    def tasks_button(self) -> Button:
        if not hasattr(self, "_tasks_button"):
            self._tasks_button = self._create_tasks_button()
        return self._tasks_button

    def _create_tasks_button(self) -> Button:
        btn = Button(
            text="Tasks History",
            icon="zmdi zmdi-view-list",
            button_size="mini",
            plain=True,
            button_type="text",
        )

        @btn.click
        def _show_tasks_dialog():
            self.tasks_history.tasks_history.update()
            self.tasks_history.tasks_modal.show()

        return btn

    @property
    def open_session_button(self) -> Button:
        if not hasattr(self, "_open_session_button"):
            self._open_session_button = self._create_open_session_button()
        return self._open_session_button

    def _create_open_session_button(self) -> Button:
        return Button(
            text="Open Running Session",
            icon="zmdi zmdi-open-in-new",
            button_size="mini",
            plain=True,
            button_type="text",
            link=self.session_link,
        )

    @property
    def session_link(self) -> str:
        return self._session_link if hasattr(self, "_session_link") else ""

    @session_link.setter
    def session_link(self, value: str):
        if not hasattr(self, "_session_link"):
            setattr(self, "_session_link", value)
        else:
            self._session_link = value
        self.open_session_button.link = value

    def set_collection_ids(
        self,
        train_collection_id: Optional[int] = None,
        val_collection_id: Optional[int] = None,
    ):
        """
        Set the collection IDs for training and validation collections.
        """
        if train_collection_id is not None:
            self.main_widget.content.train_collections = [train_collection_id]
        if val_collection_id is not None:
            self.main_widget.content.val_collections = [val_collection_id]

    def set_classes(self, classes: Union[List[str], List[ObjClass]]):
        """
        Set the classes for the training session.
        """
        if isinstance(classes, list) and all(isinstance(cls, str) for cls in classes):
            self.main_widget.content.classes = classes
        elif isinstance(classes, list) and all(isinstance(cls, ObjClass) for cls in classes):
            self.main_widget.content.classes = [c.name for c in classes]
        else:
            raise ValueError("Classes must be a list of strings or ObjClass instances.")

    def on_train_started(self, fn: Callable) -> Callable:
        """
        Register a callback function to be called when the training starts.
        """
        self._train_started_cb.append(fn)
        return fn

    def on_train_finished(self, fn: Callable) -> Callable:
        """
        Register a callback function to be called when the training finishes.
        """
        self._train_finished_cb.append(fn)
        return fn

    def check_train_finised(self, task_id: int) -> bool:
        """
        Check if the training task has finished.
        """
        # todo: Implement the logic to check train task status.
        pass
