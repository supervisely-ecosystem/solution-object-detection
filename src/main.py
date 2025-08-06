import src.sly_functions as f

f._download_js_bundle_files()

import src.nodes as n
import src.sly_globals as g
import supervisely as sly
from src.graph_builder import layout
from supervisely.solution.scheduler import TasksScheduler

btn = sly.app.widgets.Button("debug train finished")

app = sly.Application(layout=sly.app.widgets.Container([btn, layout]), static_dir="static")
app.call_before_shutdown(TasksScheduler().shutdown)


@n.cloud_import.on_start
def _on_cloud_import_start():
    n.cloud_import.modal.hide()
    n.cloud_import.gui.path_input.set_value("")


@n.cloud_import.on_finish
def _on_cloud_import_finish(task_id: int):
    n.cloud_import.gui.wait_import_completion(task_id)

    upd_project = g.api.project.get_info_by_id(g.project.id)
    full_history = upd_project.custom_data.get("import_history", {}).get("tasks", [])
    history_dict = {item["task_id"]: item for item in full_history}

    last_task = history_dict.get(task_id, {})
    last_update = last_task.get("items_count")
    if last_update is not None:
        n.input_project.update(new_items_count=last_update)
        n.smart_sampling.update_widgets(updated_project_info=upd_project)


@n.cloud_import.automation.apply_button.click
def _on_apply_automation_btn_click():
    n.cloud_import.automation.modal.hide()
    n.cloud_import.apply_automation(n.cloud_import.run)


@n.smart_sampling.on_start
def _on_sampling_start():
    n.smart_sampling.gui.modal.hide()
    n.smart_sampling.automation.modal.hide()
    sample_settinngs = n.smart_sampling.gui.get_settings()
    if not sample_settinngs.get("sample_size") and not sample_settinngs.get("limit"):
        sly.logger.error("Sampling stopped: sample size and limit are not set or both are zero.")


@n.smart_sampling.on_finish
def _on_sampling_finish(res):
    if not res:
        sly.logger.error("Sampling was not finished successfully.")
        return
    src, dst, images_count = res
    n.labeling_project_node.update(new_items_count=images_count)
    n.smart_sampling.update_widgets()

    images = []
    for imgs in dst.values():
        images.extend(imgs)
    g.api.entities_collection.add_items(g.labeling_collection.id, images)
    if n.pre_labeling.is_enabled() and n.experiments.deploy_custom_model_node.is_deployed():
        n.pre_labeling.run(images=images)
        # n.pre_labeling.run_async(images=images)
    n.labeling_project_node.update(new_items_count=images_count)
    n.sampling.update_sampling_widgets()
    n.queue.refresh_info()
    n.splits.set_items_count(images_count)


@n.queue.on_refresh
def _on_queue_refresh():
    n.splits.set_items_count(n.queue.get_labeled_images_count())


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

@n.experiments.deploy_custom_model_node.on_deploy
def on_model_deployed(deployed_task_id: int):
    n.experiments.api_inference_node.set_task_id(deployed_task_id)
    n.pre_labeling.set_deployed_model(deployed_task_id)


# # * Restore data and state if available
sly.app.restore_data_state(g.task_id)

# # * Some restoration logic (!AFTER restore_data_state)
if n.cloud_import.automation.enabled_checkbox.is_checked():
    n.cloud_import.apply_automation(n.cloud_import.run)

if n.smart_sampling.automation.enabled_checkbox.is_checked():
    n.smart_sampling.apply_automation(n.smart_sampling.run)

if n.move_labeled.automation.enabled_checkbox.is_checked():
    n.move_labeled.apply_automation(_move_labeled_images)

n.experiments.redeploy_settings.load_settings()


@btn.click
def _on_start_btn_click():
    # set best model
    sly.logger.info("DEBUG: using dummy models for comparison")
    try:
        n.experiments.evaluation_report.hide_new_report_badge()
        n.experiments.evaluation_report.node.disable()
        n.rt_detr.eval_report_after_training.hide_new_report_badge()
        n.rt_detr.eval_report_after_training.node.disable()
        n.experiments.comparison_report.hide_new_report_badge()
        n.experiments.comparison_report.node.disable()
    except Exception as e:
        sly.logger.warning(f"Failed to hide new report badges: {e}")
    model_path_1 = "/experiments/2786_SOLUTION2 (training)/48699_RT-DETRv2/checkpoints/best.pth"
    task_id_1 = int(model_path_1.split("/")[-3].split("_")[0])

    # * Set the first model as the best model
    n.experiments.experiments.set_best_model(model_path_1)

    # * Get evaluation report directory from the task info
    task_info_1 = g.api.task.get_info_by_id(task_id_1)
    report_eval_dir_1 = f._get_eval_dir_from_task_info(g.api, task_info_1)

    # * Set evaluation report (to re-evaluate node)
    n.experiments.evaluation_report.set_benchmark_dir(report_eval_dir_1)
    n.experiments.evaluation_report.node.enable()
    n.rt_detr.eval_report_after_training.set_benchmark_dir(report_eval_dir_1)
    n.rt_detr.eval_report_after_training.node.enable()

    # * Add evaluation report directory to the compare node
    n.experiments.compare_node.best_eval_dir = report_eval_dir_1

    # * This is the second model (assuming it is just from training session)
    model_path_2 = "/experiments/2786_SOLUTION2 (training)/48698_RT-DETRv2/checkpoints/best.pth"
    task_id_2 = int(model_path_2.split("/")[-3].split("_")[0])

    # * Get evaluation report directory from the task info
    task_info_2 = g.api.task.get_info_by_id(task_id_2)
    report_eval_dir_2 = f._get_eval_dir_from_task_info(g.api, task_info_2)

    # * Add second evaluation report directory to the compare node
    n.experiments.compare_node.new_eval_dir = report_eval_dir_2

    # * Run the comparison (if new model is better, it will be automatically re-deployed and email will be sent)
    n.experiments.compare_node.run()
