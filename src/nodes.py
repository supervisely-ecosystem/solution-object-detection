import src.sly_globals as g
import supervisely as sly
from src.components import *
from src.components.send_email.send_email import SendEmail

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
dummy_icon = sly.app.widgets.Icons(
    class_name="zmdi zmdi-circle", color="#000000", bg_color="#FED800"
)
train_rt_detr_dummy = sly.solution.LinkNode(
    "Train RT-DETR", "Dummy Node", "", 250, 635, 1862, dummy_icon
)

experiments = sly.solution.LinkNode(
    x=1100,
    y=1862,
    title="All experiments",
    description="Track all experiments in one place. The best model for comparison will be selected from the list of experiments based on the mAP metric.",
    link=sly.utils.abs_url("/nn/experiments"),
)
evaluation_report = EvaluationReportNode(
    api=g.api,
    project_info=g.project,
    benchmark_dir=None,
    title="Evaluation Report",
    description="Quick access to the latest evaluation report of the best model from the Experiments. The report contains the model performance metrics and visualizations. Will be used as a reference for comparing with models from the next experiments.",
    width=200,
    x=1300,
    y=2140,
    tooltip_position="left",
)
re_eval_dummy = sly.solution.LinkNode(
    "Re-evaluate Model", "Dummy Node", "", 250, 1100, 2025, dummy_icon
)
overview_dummy = sly.solution.LinkNode(
    "Overview + how to use model", "Dummy Node", "", 250, 795, 2000, dummy_icon
)
eval_report_after_training = EvaluationReportNode(
    g.api,
    g.project,
    benchmark_dir=None,
    title="Evaluation Report",
    description="Quick access to the evaluation report of the model after training. The report contains the model performance metrics and visualizations.",
    width=200,
    x=795,
    y=2070,
)
training_charts_dummy = sly.solution.LinkNode(
    "Training Charts", "Dummy Node", "", 250, 795, 2140, dummy_icon
)
checkpoints_folder = sly.solution.LinkNode(
    title="Checkpoints Folder",
    description="View the folder containing the model checkpoints.",
    link="",
    width=200,
    x=795,
    y=2210,
    # icon=Icons(class_name="zmdi zmdi-folder"),
)
compare_desc = "Compare evaluation results from the latest training session againt the best model reference report. "
"Helps track performance improvements over time and identify the most effective training setups. "
"If the new model performs better, it can be used to re-deploy the NN model for pre-labeling to speed-up the process."
compare_node = CompareNode(
    g.api,
    g.project,
    "Compare Reports",
    compare_desc,
    250,
    1100,
    2300,
    tooltip_position="left",
)
email_creds = SendEmail.EmailCredentials("user123@gmail.com", "pass123")
send_email = SendEmailNode(
    email_creds,
    target_addresses="user321@gmail.com",
    width=200,
    x=1300,
    y=2400,
    tooltip_position="left",
)
comparison_report = sly.solution.LinkNode(
    title="Comparison Report",
    description="Quick access to the most recent comparison report"
    "between the latest training session and the best model reference. "
    "Will be used to assess improvements and decide whether to update the deployed model.",
    link="",
    width=200,
    x=1300,
    y=2470,
    icon=sly.app.widgets.Icons(
        class_name="zmdi zmdi-open-in-new", color="#FF00A6", bg_color="#FFBCED"
    ),
    tooltip_position="left",
)
comparison_report.node.disable()

# * Create a SolutionGraphBuilder instance
graph_builder = sly.solution.SolutionGraphBuilder(height="2800px")

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
graph_builder.add_node(train_rt_detr_dummy)
graph_builder.add_node(experiments)
graph_builder.add_node(evaluation_report)
graph_builder.add_node(re_eval_dummy)
graph_builder.add_node(overview_dummy)
graph_builder.add_node(eval_report_after_training)
graph_builder.add_node(training_charts_dummy)
graph_builder.add_node(checkpoints_folder)
graph_builder.add_node(compare_node)
graph_builder.add_node(send_email)
graph_builder.add_node(comparison_report)

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
graph_builder.add_edge(versioning, train_rt_detr_dummy)
graph_builder.add_edge(experiments, re_eval_dummy, path="grid", label="best model overall")
graph_builder.add_edge(re_eval_dummy, evaluation_report, end_socket="left", path="grid")
graph_builder.add_edge(train_rt_detr_dummy, checkpoints_folder, end_socket="left", path="grid")
graph_builder.add_edge(
    train_rt_detr_dummy,
    overview_dummy,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    train_rt_detr_dummy,
    training_charts_dummy,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    train_rt_detr_dummy,
    eval_report_after_training,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    train_rt_detr_dummy,
    experiments,
    start_socket="right",
    end_socket="left",
    path="grid",
    dash=True,
    label="register experiments",
)
graph_builder.add_edge(checkpoints_folder, compare_node, end_socket="left", path="grid")
graph_builder.add_edge(re_eval_dummy, compare_node)
graph_builder.add_edge(compare_node, send_email, end_socket="left", path="grid")
graph_builder.add_edge(compare_node, comparison_report, end_socket="left", path="grid")

# * Build the layout
layout = graph_builder.build()
