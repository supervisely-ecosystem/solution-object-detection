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
    n.cloud_import.run_modal.hide()
    n.cloud_import.main_widget.path_input.set_value("")


@n.cloud_import.on_finish
def _on_cloud_import_finish(task_id: int):
    n.cloud_import.main_widget.wait_import_completion(task_id)

    upd_project = g.api.project.get_info_by_id(g.project.id)
    full_history = upd_project.custom_data.get("import_history", {}).get("tasks", [])
    history_dict = {item["task_id"]: item for item in full_history}

    last_task = history_dict.get(task_id, {})
    last_update = last_task.get("items_count")
    if last_update is not None:
        n.input_project.update(new_items_count=last_update)
        n.sampling.update_sampling_widgets()


@n.cloud_import.automation_btn.click
def _on_apply_automation_btn_click():
    n.cloud_import.automation_modal.hide()
    n.cloud_import.apply_automation(n.cloud_import.main_widget.run)


@n.sampling.on_start
def _on_sampling_start():
    n.sampling.main_modal.hide()
    n.sampling.automation_modal.hide()
    sample_settinngs = n.sampling.main_widget.get_sample_settings()
    if not sample_settinngs.get("sample_size") and not sample_settinngs.get("limit"):
        sly.logger.error("Sampling stopped: sample size and limit are not set or both are zero.")


@n.sampling.on_finish
def _on_sampling_finish(res):
    if not res:
        sly.logger.error("Sampling was not finished successfully.")
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


# # * Restore data and state if available
sly.app.restore_data_state(g.task_id)

# # * Some restoration logic (!AFTER restore_data_state)
if n.cloud_import.automation.enabled_checkbox.is_checked():
    n.cloud_import.apply_automation(n.cloud_import.main_widget.run)

if n.sampling.automation.enabled_checkbox.is_checked():
    n.sampling.apply_automation(n.sampling.run)

if n.move_labeled.automation.enabled_checkbox.is_checked():
    n.move_labeled.apply_automation(_move_labeled_images)

n.experiments.redeploy_settings.load_settings()


@btn.click
def _on_start_btn_click():
    # set best model
    best_model_path = "/experiments/2730_SOLUTION1 (training)/48663_RT-DETRv2/checkpoints/best.pth"
    n.experiments.experiments.set_best_model(best_model_path)
    # add best model evaluation directory to compare node
    best_eval_dir = "/model-benchmark/2730_SOLUTION1 (training)/48664_Serve RT-DETRv2"
    n.experiments.compare_node.evaluation_dirs = [best_eval_dir]

    # get last trained model evaluation report
    task_id = 48663
    task_info = g.api.task.get_info_by_id(task_id)
    experiment_data = task_info["meta"].get("output", {}).get("experiment", {}).get("data", {})
    report_id = experiment_data.get("evaluation_report_id")
    report_id = 778295
    report_info = g.api.storage.get_info_by_id(report_id)
    report_eval_dir = report_info.path.split("visualizations/")[0]
    n.rt_detr.eval_report_after_training.set_benchmark_dir(report_eval_dir)
    n.rt_detr.eval_report_after_training.node.enable()

    # add evaluation report directory to compare node
    # n.experiments.compare_node.evaluation_dirs.append(report_eval_dir)

    # start re-evaluation of the best model on new validation set
    n.experiments.re_eval.set_model_path(n.experiments.experiments.best_model)
    n.experiments.re_eval.run()  # comparison will be done automatically after re-evaluation


# sly.logger.warning(f"No evaluation report found in task {task_id} output. Re-evaluating...")
# artifacts_dir = task_info["meta"]["output"]["experiment"]["data"]["artifacts_dir"]
# best_checkpoint = task_info["meta"]["output"]["experiment"]["data"]["best_checkpoint"]
# model_path = os.path.join(artifacts_dir, "checkpoints", best_checkpoint)
# n.re_eval.set_model_path(model_path)
# n.re_eval.run(skip_cb=True)
# # todo: get res eval dir from re_eval
# # report_eval_dir
