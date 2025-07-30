import os
from typing import Dict, Optional

import supervisely as sly
from supervisely._utils import abs_url, is_development
from supervisely.api.api import Api


def _get_best_model_from_task_info(task_info: Dict) -> bool:
    if task_info is None:
        sly.logger.error(f"Task with ID {task_info['id']} not found.")
        return
    experiment_data = task_info["meta"].get("output", {}).get("experiment", {}).get("data", {})
    best_model = experiment_data.get("best_checkpoint")
    artifacts_dir = experiment_data.get("artifacts_dir")
    if not best_model or not artifacts_dir:
        sly.logger.warning(f"No best model found in task {task_info['id']} output.")
        return
    model_path = os.path.join(artifacts_dir, "checkpoints", best_model)
    return model_path


def _get_eval_dir_from_task_info(api: Api, task_info: Dict) -> Optional[str]:
    """
    Returns the evaluation directory for the given task ID.
    """
    if task_info is None:
        sly.logger.error(f"Task with ID {task_info['id']} not found.")
        return None

    experiment_data = task_info["meta"].get("output", {}).get("experiment", {}).get("data", {})
    report_id = experiment_data.get("evaluation_report_id")
    if report_id is None:
        sly.logger.warning(f"No evaluation report found in task {task_info['id']} output.")
        return None

    report_info = api.storage.get_info_by_id(report_id)
    return report_info.path.split("visualizations/")[0] if report_info else None


def _get_checkpoints_dir_from_task_info(task_info: Dict) -> Optional[str]:
    """
    Returns the checkpoints directory for the given task ID.
    """
    if task_info is None:
        sly.logger.error(f"Task with ID {task_info['id']} not found.")
        return None

    experiment_data = task_info["meta"].get("output", {}).get("experiment", {}).get("data", {})
    artifacts_dir = experiment_data.get("artifacts_dir")
    if artifacts_dir is None:
        sly.logger.warning(f"No artifacts directory found in task {task_info['id']} output.")
        return None

    path = os.path.join(artifacts_dir, "checkpoints") if artifacts_dir else None
    if path:
        return abs_url(path) if is_development() else path


def _get_app_session_from_task_info(task_info: Dict) -> Optional[str]:
    """
    Returns the app session url for the given task ID.
    """
    if task_info is None:
        sly.logger.error(f"Task with ID {task_info['id']} not found.")
        return None

    session_token = task_info.get("meta", {}).get("sessionToken")
    if session_token is None:
        sly.logger.warning(f"No session token found in task {task_info['id']} output.")
        return None
    url = f"/net/{session_token}"
    return abs_url(url) if is_development() else url


def _download_js_bundle_files():
    """
    Temporarily fix: Downloads JS and CSS files for the app.
    """
    js_link = "https://github.com/supervisely-ecosystem/solution-object-detection/releases/download/v0.0.1/sly-app-widgets-2.2.2.bundle.js"
    css_link = "https://github.com/supervisely-ecosystem/solution-object-detection/releases/download/v0.0.1/sly-app-widgets-2.2.2.bundle.css"

    sly.logger.info("Downloading JS and CSS files for the app...")

    static_dir = "static"
    sly.fs.mkdir(static_dir)

    js_path = os.path.join(static_dir, "sly-app-widgets-2.2.2.bundle.js")
    css_path = os.path.join(static_dir, "sly-app-widgets-2.2.2.bundle.css")

    if not sly.fs.file_exists(js_path):
        sly.fs.download(js_link, js_path)
        sly.logger.info("JS file downloaded successfully.")

    if not sly.fs.file_exists(css_path):
        sly.fs.download(css_link, css_path)
        sly.logger.info("CSS file downloaded successfully.")

    # check if files exist
    if not os.path.exists(js_path) or not os.path.exists(css_path):
        raise FileNotFoundError("Failed to download JS and CSS files for the app.")
