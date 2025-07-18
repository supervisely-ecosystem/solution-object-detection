import src.sly_globals as g
import supervisely as sly

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
    x=635, y=1390, api=g.api, src_project_id=g.project.id, dst_project_id=g.labeling_project.id
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

versioning = sly.solution.LinkNode(
    x=635,
    y=1700,
    title="Data Versioning",
    description="Versioning allows you to track changes in your datasets over time. Each version is a snapshot of the dataset at a specific point in time, enabling you to revert to previous versions if needed.",
    width=250,
    link=g.training_project.url.replace("datasets", "versions"),
)
