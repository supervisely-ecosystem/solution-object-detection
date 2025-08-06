import src.sly_globals as g
import supervisely as sly
from src.components.automation_tasks import AutomationTasksNode
from src.components.definitions import DefinitionsNode
from src.components.empty import EmptyNode
from src.components.pre_labeling.node import PreLabelingNode
from src.components.task_logs import TaskLogsNode

automation_tasks = AutomationTasksNode(x=20, y=30)
task_logs = TaskLogsNode(task_id=g.task_id, x=20, y=100)
definitions = DefinitionsNode(api=g.api, project_id=g.labeling_project.id, x=20, y=170)

cloud_import = sly.solution.CloudImportNode(x=680, y=30, api=g.api, project_id=g.project.id)
auto_import = sly.solution.AutoImportNode(x=1020, y=30, api=g.api, project_id=g.project.id)

input_project = sly.solution.ProjectNode(
    x=870,
    y=150,
    api=g.api,
    project_id=g.project.id,
    title="Input Project",
    description="Centralizes all incoming data. Data in this project will not be modified.",
)

smart_sampling = sly.solution.SmartSamplingNode(
    x=835, y=360, api=g.api, project_id=g.project.id, dst_project=g.labeling_project.id
)

labeling_project_node = sly.solution.ProjectNode(
    x=870,
    y=580,
    api=g.api,
    project_id=g.labeling_project.id,
    title="Labeling Project",
    description="Project specifically for labeling data. All data in this project is in the labeling process. After labeling, data will be moved to the Training Project.",
)

queue = sly.solution.LabelingQueue(
    api=g.api, x=860, y=810, queue_id=g.labeling_queue.id, collection_id=g.labeling_collection.id
)

labeling_performance = sly.solution.LinkNode(
    x=1200,
    y=810,
    title="Labeling Performance",
    description="Explore the performance of the labeling process.",
    tooltip_position="right",
    link=sly.utils.abs_url("/labeling-performance"),
)

splits = sly.solution.TrainValSplit(x=835, y=1300, project_id=g.project.id)

move_labeled = sly.solution.MoveLabeled(
    x=835,
    y=1390,
    api=g.api,
    src_project_id=g.labeling_project.id,
    dst_project_id=g.training_project.id,
)

training_project = sly.solution.ProjectNode(
    x=825,
    y=1490,
    api=g.api,
    project_id=g.training_project.id,
    title="Training Project",
    description="Project specifically for training data. All data in this project is in the training process. After training, data will be moved to the Training Project.",
    is_training=True,
)

training_project_qa_stats = sly.solution.LinkNode(
    x=1200,
    y=1490,
    title="QA & Stats",
    description="Open the QA & Stats page to explore detailed insights into the training project.",
    tooltip_position="right",
    link=g.training_project.url.replace("datasets", "stats/datasets"),
)

ai_index = EmptyNode(
    x=630,
    y=205,
    title="AI Index",
    description="AI Search Index is a powerful tool that allows you to search for images in your dataset using AI models. It provides a quick and efficient way to find similar images based on visual features. You can use it in Smart Sampling node to select images for labeling based on speciied prompt.",
    width=150,
    badge=sly.app.widgets.SolutionCard.Badge(label="⚡", on_hover="On", plain=True),
    icon=sly.app.widgets.Icons(class_name="zmdi zmdi-apps", color="#4CAF50", bg_color="#E8F5E9"),
    tooltip_position="left",
)

open_ai_clip = EmptyNode(
    x=400,
    y=205,
    title="OpenAI CLIP",
    description="OpenAI CLIP is a powerful model that can be used to generate embeddings for images in your project. These embeddings can be used for various tasks, such as image similarity search, prompt-based image retrieval. In this application, it is used to create an index and search images based on text prompts or clusters.",
    width=150,
    badge=sly.app.widgets.SolutionCard.Badge(label="⚡", on_hover="On", plain=True),
    icon=sly.app.widgets.Icons(class_name="zmdi zmdi-apps", color="#4CAF50", bg_color="#E8F5E9"),
    tooltip_position="left",
)

pre_labeling = PreLabelingNode(api=g.api, x=1400, y=470)
