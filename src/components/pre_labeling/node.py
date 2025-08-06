import datetime
import time
from threading import Thread
from typing import Any, Callable, Dict, List, Literal, Optional, Union

from src.components.pre_labeling.gui import PreLabelingGUI
from src.components.pre_labeling.history import PreLabelingTasksHistory
from supervisely.api.api import Api
from supervisely.api.project_api import ProjectInfo
from supervisely.app.widgets import Button, Dialog, Icons, SolutionCard
from supervisely.sly_logger import logger
from supervisely.solution.base_node import SolutionCardNode, SolutionElement


class PreLabelingNode(SolutionElement):
    def __init__(
        self,
        api: Api,
        # project: Union[int, ProjectInfo],
        # dst_project: Union[int, ProjectInfo],
        x: int = 0,
        y: int = 0,
        title: str = "Pre-labeling",
        description: str = "Automatically generate predictions for images using the deployed custom model.",
        width: int = 250,
        icon: Optional[Icons] = None,
        tooltip_position: Literal["left", "right"] = "right",
        *args,
        **kwargs,
    ):
        self.api = api
        # self.project = self._validate_project(project)
        # self.dst_project = self._validate_project(dst_project)

        self.title = title
        self.description = description
        self.width = width
        self.tooltip_position = tooltip_position
        self.icon = icon or Icons(
            class_name="zmdi zmdi-label",
            color="#1976D2",
            bg_color="#E3F2FD",
        )

        super().__init__(*args, **kwargs)

        # Initialize components
        self.tasks_history = PreLabelingTasksHistory()
        self.main_widget = PreLabelingGUI(api=api)

        # Callbacks
        self._start_callbacks = []
        self._finish_callbacks = []

        # Widget event handlers
        @self.main_widget.enable_switch.value_changed
        def on_enable_switch_change(value: bool):
            self.save_settings(enabled=value)

        # Create UI components
        self.card = self._create_card()
        self.node = SolutionCardNode(content=self.card, x=x, y=y)
        self.modals = [self.tasks_history_modal, self.settings_modal]

        # Load settings and update properties
        self._update_properties(self.main_widget.enable_switch.is_switched())

    def _validate_project(self, project: Union[int, ProjectInfo]):
        """Validate project type."""
        if isinstance(project, ProjectInfo):
            return project
        elif isinstance(project, int):
            return self.api.project.get_info_by_id(project)
        else:
            raise ValueError("Project must be an instance of ProjectInfo or an integer ID.")

    @property
    def tasks_history_modal(self) -> Dialog:
        if not hasattr(self, "_tasks_history_modal"):
            self._tasks_history_modal = Dialog(
                title="Pre-labeling History", content=self.tasks_history
            )
        return self._tasks_history_modal

    @property
    def settings_modal(self) -> Dialog:
        if not hasattr(self, "_settings_modal"):
            self._settings_modal = Dialog(
                title="Pre-labeling Settings", content=self.main_widget.content
            )
        return self._settings_modal

    @property
    def history_btn(self) -> Button:
        if not hasattr(self, "_history_btn"):
            self._history_btn = Button(
                "Tasks History",
                icon="zmdi zmdi-format-list-bulleted",
                button_size="mini",
                plain=True,
                button_type="text",
            )

            @self._history_btn.click
            def show_history():
                self.tasks_history_modal.show()

        return self._history_btn

    @property
    def run_btn(self) -> Button:
        if not hasattr(self, "_run_btn"):
            self._run_btn = Button(
                "Run manually",
                icon="zmdi zmdi-play",
                button_size="mini",
                plain=True,
                button_type="text",
            )

        return self._run_btn

    def _create_card(self) -> SolutionCard:
        card = SolutionCard(
            title=self.title,
            tooltip=self._create_tooltip(),
            width=self.width,
            icon=self.icon,
            tooltip_position=self.tooltip_position,
        )

        @card.click
        def _on_card_click():
            self.settings_modal.show()

        return card

    def _create_tooltip(self) -> SolutionCard.Tooltip:
        return SolutionCard.Tooltip(
            description=self.description,
            content=[
                # self.run_btn,
                self.history_btn,
            ],
        )

    def _update_properties(self, enabled: bool):
        """Update node properties based on current settings."""
        status = "enabled" if enabled else "disabled"
        self.card.update_property("Pre-labeling", status, highlight=enabled)

        if enabled:
            self.node.show_automation_badge()
        else:
            self.node.hide_automation_badge()

        # Update processed images count
        processed_count = len(self.get_all_processed_images())
        if processed_count > 0:
            self.card.update_property("Processed images", str(processed_count))

    def save_settings(self, enabled: Optional[bool] = None):
        """Save pre-labeling settings."""
        if enabled is None:
            enabled = self.main_widget.enable_switch.is_switched()

        self.main_widget.save_settings(enabled)
        self._update_properties(enabled)

    def load_settings(self):
        """Load pre-labeling settings."""
        self.main_widget.load_settings()
        self._update_properties()

    def is_enabled(self) -> bool:
        """Check if pre-labeling is enabled."""
        return self.main_widget.enable_switch.is_switched()

    def set_deployed_model(self, session_id: int):
        """Set reference to the deployed custom model."""
        if not isinstance(session_id, int):
            raise ValueError("Model must be an integer session ID.")
        self.main_widget.set_model_session_id(session_id)
        logger.info("Pre-labeling: Custom model reference set")

    def get_all_processed_images(self) -> List[int]:
        """Get all processed image IDs from all tasks."""
        return self.main_widget.get_processed_images()

    def _run(self, images: List[int]) -> Optional[Dict[str, Any]]:
        if not self.is_enabled():
            logger.info("Pre-labeling is disabled, skipping...")
            return None

        if self.main_widget.model is None:
            logger.warning("No custom model deployed, cannot perform pre-labeling")
            return None

        start_time = time.time()
        started_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        task_id = len(self.tasks_history.get_tasks()) + 1

        self.node.show_in_progress_badge("Pre-labeling")

        try:
            # Call start callbacks
            for cb in self._start_callbacks:
                try:
                    cb()
                except Exception as e:
                    logger.error(f"Error in start callback: {e}", exc_info=True)

            self.main_widget.run(images=images)

            last_processed_images = self.main_widget.get_last_processed_images()
            self.main_widget.update_preview_gallery(last_processed_images)

            # Create task record
            duration = time.time() - start_time
            task_record = {
                "task_id": task_id,
                "started_at": started_at,
                "images_count": len(images),
                "status": "Success",
                "duration": f"{duration:.2f}s",
            }

            self.tasks_history.add_task(task_record)
            self._update_properties(True)

            logger.info(
                f"Pre-labeling completed: {len(images)} images processed in {duration:.2f}s"
            )

            result = {
                "task_id": task_id,
                "images": self.main_widget.get_last_processed_images(),
                "status": "success",
            }

            # Call finish callbacks
            for cb in self._finish_callbacks:
                try:
                    if cb.__code__.co_argcount == 1:
                        cb(images)
                    else:
                        cb()
                except Exception as e:
                    logger.error(f"Error in finish callback: {e}", exc_info=True)

            return result

        except Exception as e:
            logger.error(f"Pre-labeling failed: {e}", exc_info=True)

            # Create error task record
            task_record = {
                "task_id": task_id,
                "started_at": started_at,
                "images_count": 0,
                "status": "Error",
                "duration": f"{time.time() - start_time:.2f}s",
            }
            self.tasks_history.add_task(task_record)

            return {"task_id": task_id, "status": "error", "error": str(e)}

        finally:
            self.node.hide_in_progress_badge("Pre-labeling")

    def run(self, images: List[int]) -> Optional[Dict[str, Any]]:
        """
        Run pre-labeling on the provided images.

        Args:
            images: List of image IDs to process.
        Returns:
            Dictionary with processing results or None if disabled/failed
        """
        return self._run(images)

    # run asynchronously
    def run_async(self, images: List[int]) -> None:
        """
        Run pre-labeling asynchronously on the provided images.

        Args:
            images: List of image IDs to process.
        """
        thread = Thread(target=self._run, args=(images,))
        thread.start()

    def on_start(self, fn: Callable) -> Callable:
        """Register callback to be called when pre-labeling starts."""
        self._start_callbacks.append(fn)
        return fn

    def on_finish(self, fn: Callable) -> Callable:
        """Register callback to be called when pre-labeling finishes."""
        self._finish_callbacks.append(fn)
        return fn
