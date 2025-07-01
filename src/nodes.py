import src.sly_globals as g
import supervisely as sly
from src.components import *

cloud_import = sly.solution.CloudImport(
    api=g.api,
    x=480,
    y=30,
    project_id=g.project.id,
    widget_id="cloud_import_widget",
)
auto_import = sly.solution.ManualImport(
    api=g.api,
    x=820,
    y=30,
    project_id=g.project.id,
    widget_id="auto_import_widget",
)

input_project = sly.solution.ProjectNode(
    api=g.api,
    x=670,
    y=150,
    project_id=g.project.id,
    title="Input Project",
    description="Centralizes all incoming data. Data in this project will not be modified.",
    widget_id="input_project_widget",
)

sampling = sly.solution.SmartSampling(
    api=g.api,
    x=635,
    y=360,
    project_id=g.project.id,
    dst_project=g.labeling_project.id,
    widget_id="sampling_widget",
)

labeling_project_node = sly.solution.ProjectNode(
    api=g.api,
    x=670,
    y=580,
    project_id=g.labeling_project.id,
    title="Labeling Project",
    description="Project specifically for labeling data. All data in this project is in the labeling process. After labeling, data will be moved to the Training Project.",
    widget_id="labeling_project_widget",
)

queue = sly.solution.LabelingQueue(
    api=g.api,
    x=660,
    y=810,
    queue_id=g.labeling_queue.id,
    collection_id=g.labeling_collection.id,
    widget_id="labeling_queue_widget",
)

labeling_performance = sly.solution.LinkNode(
    title="Labeling Performance",
    x=1000,
    y=804,  # -6 to align with the queue node
    description="Explore the performance of the labeling process.",
    tooltip_position="right",
    link=sly.utils.abs_url("/labeling-performance"),
)
splits = sly.solution.TrainValSplit(
    x=635,
    y=1300,
    project_id=g.project.id,
    widget_id="train_val_split_widget",
)
move_labeled = sly.solution.MoveLabeled(
    api=g.api,
    x=635,
    y=1390,
    src_project_id=g.project.id,
    dst_project_id=g.labeling_project.id,
    widget_id="move_labeled_widget",
)
training_project = sly.solution.ProjectNode(
    api=g.api,
    x=625,
    y=1490,
    project_id=g.labeling_project.id,
    title="Training Project",
    description="Project specifically for labeling data. All data in this project is in the labeling process. After labeling, data will be moved to the Training Project.",
    is_training=True,
    widget_id="training_project_widget",
)
versioning = sly.solution.LinkNode(
    title="Data Versioning",
    x=635,
    y=1700,
    description="Versioning allows you to track changes in your datasets over time. Each version is a snapshot of the dataset at a specific point in time, enabling you to revert to previous versions if needed.",
    width=250,
    link=g.training_project.url.replace("datasets", "versions"),
)

# train_rt_detr = sly.solution.TrainRTDETR(
#     x=1000,
#     y=1700,
#     project_id=g.training_project.id,
#     widget_id="train_rt_detr_widget",
#     title="Train RT-DETR",
#     description="Train RT-DETR model on the labeled data from the Training Project. The model will be trained using the latest version of the dataset.",
# )

experiments = sly.solution.LinkNode(
    x=1200,
    y=1862,
    title="All experiments",
    description="Track all experiments in one place. The best model for comparison will be selected from the list of experiments based on the mAP metric.",
    link=sly.utils.abs_url("/nn/experiments"),
)
BENCHMARK_DIR = ""
evaluation_report = EvaluationReportNode(
    api=g.api,
    project_info=g.project,
    benchmark_dir=BENCHMARK_DIR,
    title="Evaluation Report",
    description="Quick access to the latest evaluation report of the best model from the Experiments. The report contains the model performance metrics and visualizations. Will be used as a reference for comparing with models from the next experiments.",
    width=200,
    x=1400,
    y=2140,
)
checkpoints_folder = sly.solution.LinkNode(
    title="Checkpoints Folder",
    description="View the folder containing the model checkpoints.",
    link="",
    width=200,
    x=1400,
    y=2290,
    # icon=Icons(class_name="zmdi zmdi-folder"),
)

# * Create a SolutionGraphBuilder instance
graph_builder = sly.solution.SolutionGraphBuilder(height="2500px")

# * Add nodes to the graph
graph_builder.add_node(cloud_import)
graph_builder.add_node(auto_import)
graph_builder.add_node(input_project)
graph_builder.add_node(sampling)
graph_builder.add_node(labeling_project_node)
graph_builder.add_node(queue)
graph_builder.add_node(labeling_performance)
graph_builder.add_node(splits)
graph_builder.add_node(move_labeled)
graph_builder.add_node(training_project)
graph_builder.add_node(versioning)
# graph_builder.add_node(train_rt_detr)
graph_builder.add_node(experiments)
graph_builder.add_node(evaluation_report)
graph_builder.add_node(checkpoints_folder)


# * Add edges between nodes
graph_builder.add_edge(cloud_import, input_project, path="grid")
graph_builder.add_edge(auto_import, input_project, path="grid")
graph_builder.add_edge(input_project, sampling)
graph_builder.add_edge(sampling, labeling_project_node)
graph_builder.add_edge(labeling_project_node, queue)
graph_builder.add_edge(queue, splits)
graph_builder.add_edge(
    labeling_performance,
    queue,
    start_socket="left",
    end_socket="right",
    dash=True,
    end_plug="disc",
    point_anchor={"x": "100%", "y": 21},
)
graph_builder.add_edge(splits, move_labeled)
graph_builder.add_edge(move_labeled, training_project)
graph_builder.add_edge(training_project, versioning)
# graph_builder.add_edge(versioning, train_rt_detr)
graph_builder.add_edge(experiments, evaluation_report, end_socket="left", path="grid")
graph_builder.add_edge(experiments, checkpoints_folder, end_socket="left", path="grid")


# * Build the layout
layout = graph_builder.build()
