import os

from dotenv import load_dotenv

import supervisely as sly
from supervisely.solution.scheduler import TasksScheduler

LOCAL_DATA = "data.json"
LOCAL_STATE = "state.json"


if sly.is_development():
    load_dotenv("local.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))

api = sly.Api.from_env()
team_id = sly.env.team_id()
workspace_id = sly.env.workspace_id()
scheduler = TasksScheduler()
PROJECT_NAME = "Solution_005"
project = api.project.get_or_create(workspace_id, PROJECT_NAME)
update_project = False
custom_data = project.custom_data
if "labeling_project" not in custom_data:
    labeling_project = api.project.create(
        workspace_id,
        f"{PROJECT_NAME} (labeling)",
        change_name_if_conflict=True,
        description="labeling project",
    )
    custom_data["labeling_project"] = labeling_project.id
    update_project = True
else:
    labeling_project = api.project.get_info_by_id(custom_data["labeling_project"])

if "training_project" not in custom_data:
    training_project = api.project.create(
        workspace_id,
        f"{PROJECT_NAME} (training)",
        change_name_if_conflict=True,
        description="training project",
    )
    custom_data["training_project"] = training_project.id
    update_project = True
else:
    training_project = api.project.get_info_by_id(custom_data["training_project"])


if "labeling_collection" not in custom_data:
    labeling_collection = api.entities_collection.create(labeling_project.id, "Labeling Collection")
    custom_data["labeling_collection"] = labeling_collection.id
    update_project = True
else:
    labeling_collection = api.entities_collection.get_info_by_id(custom_data["labeling_collection"])

if "labeling_queue" not in custom_data:
    user_ids = [api.user.get_my_info().id]
    labeling_queue = api.labeling_queue.create(
        name="Labeling Queue for Solutions",
        user_ids=user_ids,
        reviewer_ids=user_ids,
        collection_id=labeling_collection.id,
        dynamic_classes=True,
        dynamic_tags=True,
        allow_review_own_annotations=True,
        skip_complete_job_on_empty=True,
    )
    labeling_queue = api.labeling_queue.get_info_by_id(labeling_queue)
    custom_data["labeling_queue"] = labeling_queue.id
    update_project = True
else:
    labeling_queue = api.labeling_queue.get_info_by_id(custom_data["labeling_queue"])

if update_project:
    api.project.update_custom_data(project.id, custom_data)

if sly.is_development():
    sly.logger.setLevel(10)
