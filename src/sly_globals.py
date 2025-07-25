import os

from dotenv import load_dotenv

import supervisely as sly

if sly.is_development():
    load_dotenv("local.env")
    load_dotenv("email_creds.env")
    load_dotenv(os.path.expanduser("~/supervisely.env"))

api = sly.Api.from_env()
team_id = sly.env.team_id()
task_id = sly.env.task_id()
workspace_id = sly.env.workspace_id()
project_id = sly.env.project_id()

project = api.project.get_info_by_id(project_id)
custom_data = project.custom_data

update_project = False
if "labeling_project" not in custom_data:
    labeling_project = api.project.create(
        workspace_id,
        f"{project.name} (labeling)",
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
        f"{project.name} (training)",
        change_name_if_conflict=True,
        description="training project",
    )
    custom_data["training_project"] = training_project.id
    update_project = True
else:
    training_project = api.project.get_info_by_id(custom_data["training_project"])

if "train_collection" not in custom_data:
    train_collection = api.entities_collection.create(training_project.id, "All_train")
    custom_data["train_collection"] = train_collection.id
    update_project = True
else:
    train_collection = api.entities_collection.get_info_by_id(custom_data["train_collection"])

if "val_collection" not in custom_data:
    val_collection = api.entities_collection.create(training_project.id, "All_val")
    custom_data["val_collection"] = val_collection.id
    update_project = True
else:
    val_collection = api.entities_collection.get_info_by_id(custom_data["val_collection"])

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
