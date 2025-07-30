import supervisely as sly

import src.sly_globals as g
from src.components.automation_tasks import AutomationTasksNode
from src.components.definitions import DefinitionsNode
from src.components.task_logs import TaskLogsNode

automation_tasks = AutomationTasksNode(x=20, y=30)
task_logs = TaskLogsNode(task_id=g.task_id, x=20, y=100)
definitions = DefinitionsNode(api=g.api, project_id=g.labeling_project.id, x=20, y=170)

cloud_import = sly.solution.CloudImport(x=480, y=30, api=g.api, project_id=g.project.id)
auto_import = sly.solution.ManualImport(x=820, y=30, api=g.api, project_id=g.project.id)

input_project = sly.solution.ProjectNode(
    x=670,
    y=150,
    api=g.api,
    project_id=g.project.id,
    title="Input Project",
    description="Centralizes all incoming data. Data in this project will not be modified.",
)

sampling = sly.solution.SmartSampling(
    x=635, y=360, api=g.api, project_id=g.project.id, dst_project=g.labeling_project.id
)

labeling_project_node = sly.solution.ProjectNode(
    x=670,
    y=580,
    api=g.api,
    project_id=g.labeling_project.id,
    title="Labeling Project",
    description="Project specifically for labeling data. All data in this project is in the labeling process. After labeling, data will be moved to the Training Project.",
)

queue = sly.solution.LabelingQueue(
    api=g.api, x=660, y=810, queue_id=g.labeling_queue.id, collection_id=g.labeling_collection.id
)

labeling_performance = sly.solution.LinkNode(
    x=1000,
    y=810,
    title="Labeling Performance",
    description="Explore the performance of the labeling process.",
    tooltip_position="right",
    link=sly.utils.abs_url("/labeling-performance"),
)

splits = sly.solution.TrainValSplit(x=635, y=1300, project_id=g.project.id)

move_labeled = sly.solution.MoveLabeled(
    x=635,
    y=1390,
    api=g.api,
    src_project_id=g.labeling_project.id,
    dst_project_id=g.training_project.id,
)

training_project = sly.solution.ProjectNode(
    x=625,
    y=1490,
    api=g.api,
    project_id=g.training_project.id,
    title="Training Project",
    description="Project specifically for training data. All data in this project is in the training process. After training, data will be moved to the Training Project.",
    is_training=True,
)

training_project_qa_stats = sly.solution.LinkNode(
    x=1000,
    y=1490,
    title="Training Project QA Stats",
    description="Explore the QA stats of the training project.",
    tooltip_position="right",
    link=g.training_project.url.replace("datasets", "stats/datasets"),
)

versioning = sly.solution.LinkNode(
    x=635,
    y=1700,
    title="Data Versioning",
    description="Versioning allows you to track changes in your datasets over time. Each version is a snapshot of the dataset at a specific point in time, enabling you to revert to previous versions if needed.",
    width=250,
    link=g.training_project.url.replace("datasets", "versions"),
)

ai_search = sly.solution.LinkNode(
    x=886,
    y=205,
    title="AI Search",
    description="AI Search Service allows you to search for similar images in the dataset using AI models.",
    width=180,
)

ai_search_clip = sly.solution.LinkNode(
    x=1100,
    y=205,
    title="CLIP Service",
    description="CLIP Service creates vectors for images and converts prompts to vectors for AI search.",
    link=sly.utils.abs_url("/ecosystem/apps/deploy-clip-as-service"),
)
