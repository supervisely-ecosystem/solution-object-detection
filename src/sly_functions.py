import os
from typing import Optional

import supervisely as sly
from supervisely.api.api import Api


def _get_best_model_from_task_info(api: Api, task_id: int) -> bool:
    task_info = api.task.get_info_by_id(task_id)
    if task_info is None:
        sly.logger.error(f"Task with ID {task_id} not found.")
        return
    experiment_data = task_info["meta"].get("output", {}).get("experiment", {}).get("data", {})
    best_model = experiment_data.get("best_checkpoint")
    artifacts_dir = experiment_data.get("artifacts_dir")
    if not best_model or not artifacts_dir:
        sly.logger.warning(f"No best model found in task {task_id} output.")
        return
    model_path = os.path.join(artifacts_dir, "checkpoints", best_model)
    return model_path


def _get_eval_dir_from_task_info(api: Api, task_id: int) -> Optional[str]:
    """
    Returns the evaluation directory for the given task ID.
    """
    task_info = api.task.get_info_by_id(task_id)
    if task_info is None:
        sly.logger.error(f"Task with ID {task_id} not found.")
        return None

    experiment_data = task_info["meta"].get("output", {}).get("experiment", {}).get("data", {})
    report_id = experiment_data.get("evaluation_report_id")
    if report_id is None:
        sly.logger.warning(f"No evaluation report found in task {task_id} output.")
        return None

    report_info = api.storage.get_info_by_id(report_id)
    return report_info.path.split("visualizations/")[0] if report_info else None
