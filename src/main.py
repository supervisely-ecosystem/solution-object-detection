import random
from typing import Optional

import src.nodes as n
import src.sly_globals as g
import supervisely as sly
from src.graph_builder import layout
from supervisely.solution.scheduler import TasksScheduler

app = sly.Application(layout=layout, static_dir="static")
app.call_before_shutdown(TasksScheduler().shutdown)


def _run_import_from_cloud(path: Optional[str] = None):
    task_id = n.cloud_import.main_widget.run(path)
    n.cloud_import.main_widget.wait_import_completion(task_id)

    upd_project = g.api.project.get_info_by_id(g.project.id)
    full_history = upd_project.custom_data.get("import_history", {}).get("tasks", [])
    history_dict = {item["task_id"]: item for item in full_history}

    last_task = history_dict.get(task_id, {})
    last_update = last_task.get("items_count")
    if last_update is not None:
        n.input_project.update(new_items_count=last_update)
        n.sampling.update_sampling_widgets()


@n.cloud_import.main_widget.run_btn.click
def _on_cloud_import_run_btn_click():
    n.cloud_import.main_widget.path_input.set_value("")
    n.cloud_import.run_modal.hide()
    _run_import_from_cloud()


@n.cloud_import.automation_btn.click
def _on_apply_automation_btn_click():
    n.cloud_import.automation_modal.hide()
    n.cloud_import.apply_automation(_run_import_from_cloud)


def run_sampling():
    n.sampling.main_modal.hide()
    n.sampling.automation_modal.hide()
    sample_settinngs = n.sampling.main_widget.get_sample_settings()
    if not sample_settinngs.get("sample_size") and not sample_settinngs.get("limit"):
        sly.logger.warning("Sampling stopped: sample size and limit are not set or both are zero.")
        return
    res = n.sampling.main_widget.run()
    if not res:
        sly.logger.warning("Sampling was not finished successfully.")
        return
    src, dst, images_count = res
    n.labeling_project_node.update(new_items_count=images_count)
    n.sampling.update_sampling_widgets()

    images = []
    for imgs in dst.values():
        images.extend(imgs)
    g.api.entities_collection.add_items(g.labeling_collection.id, images)
    n.queue.refresh_info()
    n.splits.set_items_count(images_count)


n.sampling.run = run_sampling


n.queue.set_callback(lambda: n.splits.set_items_count(n.queue.get_labeled_images_count()))


def _move_labeled_images():
    image_ids = n.queue.get_new_accepted_images()
    if not image_ids:
        sly.logger.warning("No new accepted images to move.")
        return
    src, dst, total_moved = n.move_labeled.run(image_ids=image_ids)
    all_dst_ids = [img_id for img_ids in dst.values() for img_id in img_ids]

    split_results = n.splits.split(all_dst_ids)
    for key in split_results:
        n.move_labeled.add_to_collection(image_ids=split_results[key], split_name=key)
    n.queue.refresh_info()
    n.splits.set_items_count(n.queue.get_labeled_images_count())
    n.training_project.update(new_items_count=total_moved)


@n.move_labeled.pull_btn.click
def _on_move_labeled_pull_btn_click():
    _move_labeled_images()


@n.move_labeled.automation_btn.click
def _on_move_labeled_automation_btn_click():
    n.move_labeled.automation_modal.hide()
    n.move_labeled.apply_automation(_move_labeled_images)


# # * Restore data and state if available
sly.app.restore_data_state(g.task_id)

# # * Some restoration logic (!AFTER restore_data_state)
if n.cloud_import.automation.enabled_checkbox.is_checked():
    n.cloud_import.apply_automation(_run_import_from_cloud)

if n.sampling.automation.enabled_checkbox.is_checked():
    n.sampling.apply_automation(n.sampling.run)

if n.move_labeled.automation.enabled_checkbox.is_checked():
    n.move_labeled.apply_automation(_move_labeled_images)
