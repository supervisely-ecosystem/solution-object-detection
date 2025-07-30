import supervisely as sly

import src.nodes as n

# * Create a SolutionGraphBuilder instance
graph_builder = sly.solution.SolutionGraphBuilder(height="2800px", width="3000px")

# * Add nodes to the graph
# common nodes
graph_builder.add_node(n.automation_tasks)
graph_builder.add_node(n.task_logs)
graph_builder.add_node(n.definitions)

# input nodes
graph_builder.add_node(n.cloud_import)
graph_builder.add_node(n.auto_import)
graph_builder.add_node(n.input_project)
graph_builder.add_node(n.ai_search)
graph_builder.add_node(n.ai_search_clip)
graph_builder.add_node(n.sampling)

# labeling nodes
graph_builder.add_node(n.labeling_project_node)
graph_builder.add_node(n.queue)
graph_builder.add_node(n.labeling_performance)

# EXPERIMENT NODES:
# - training preparation nodes
graph_builder.add_node(n.splits)
graph_builder.add_node(n.move_labeled)
graph_builder.add_node(n.training_project)
graph_builder.add_node(n.training_project_qa_stats)
graph_builder.add_node(n.versioning)

# - RT-DETR training nodes
graph_builder.add_node(n.rt_detr.train_node)
graph_builder.add_node(n.rt_detr.overview_dummy)
graph_builder.add_node(n.rt_detr.eval_report_after_training)
graph_builder.add_node(n.rt_detr.training_charts_dummy)
graph_builder.add_node(n.rt_detr.checkpoints_folder)

# - YOLO training nodes
graph_builder.add_node(n.yolo.train_node)
graph_builder.add_node(n.yolo.overview_dummy)
graph_builder.add_node(n.yolo.eval_report_after_training)
graph_builder.add_node(n.yolo.training_charts_dummy)
graph_builder.add_node(n.yolo.checkpoints_folder)

# - common experiment nodes
graph_builder.add_node(n.experiments.re_eval)
graph_builder.add_node(n.experiments.evaluation_report)
graph_builder.add_node(n.experiments.experiments)
graph_builder.add_node(n.experiments.compare_node)
graph_builder.add_node(n.experiments.send_email)
graph_builder.add_node(n.experiments.comparison_report)
graph_builder.add_node(n.experiments.redeploy_settings)
graph_builder.add_node(n.experiments.deploy_custom_model_node)
graph_builder.add_node(n.experiments.api_inference_node)

# * Add edges between nodes
graph_builder.add_edge(n.cloud_import, n.input_project, path="grid")
graph_builder.add_edge(n.auto_import, n.input_project, path="grid")
graph_builder.add_edge(n.input_project, n.sampling)
graph_builder.add_edge(
    n.input_project,
    n.ai_search,
    dash=True,
    start_socket="right",
    end_socket="left",
    end_plug="behind",
)
graph_builder.add_edge(
    n.ai_search,
    n.ai_search_clip,
    dash=True,
    start_socket="right",
    end_socket="left",
    end_plug="behind",
)
graph_builder.add_edge(
    n.ai_search, n.sampling, dash=True, start_socket="bottom", end_socket="right", path="grid"
)
graph_builder.add_edge(n.sampling, n.labeling_project_node)
graph_builder.add_edge(n.labeling_project_node, n.queue)
graph_builder.add_edge(n.queue, n.splits)
graph_builder.add_edge(
    n.labeling_performance,
    n.queue,
    start_socket="left",
    end_socket="right",
    dash=True,
    end_plug="disc",
    point_anchor={"x": "100%", "y": 29},
)
graph_builder.add_edge(n.splits, n.move_labeled)
graph_builder.add_edge(n.move_labeled, n.training_project)
graph_builder.add_edge(n.training_project, n.versioning)
graph_builder.add_edge(
    n.training_project_qa_stats,
    n.training_project,
    start_socket="left",
    end_socket="right",
    dash=True,
    end_plug="disc",
    point_anchor={"x": "100%", "y": 29},
)
graph_builder.add_edge(n.versioning, n.rt_detr.train_node)
graph_builder.add_edge(n.versioning, n.yolo.train_node, path="grid")
graph_builder.add_edge(
    n.experiments.experiments,
    n.experiments.re_eval,
    path="grid",
    label="best model overall",
)
graph_builder.add_edge(
    n.experiments.re_eval, n.experiments.evaluation_report, end_socket="left", path="grid"
)
graph_builder.add_edge(
    n.rt_detr.train_node, n.rt_detr.checkpoints_folder, end_socket="left", path="grid"
)
graph_builder.add_edge(
    n.rt_detr.train_node,
    n.rt_detr.overview_dummy,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    n.rt_detr.train_node,
    n.rt_detr.training_charts_dummy,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    n.rt_detr.train_node,
    n.rt_detr.eval_report_after_training,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    n.rt_detr.train_node,
    n.experiments.experiments,
    start_socket="right",
    end_socket="left",
    path="grid",
    dash=True,
    label="register experiments",
)
graph_builder.add_edge(
    n.rt_detr.train_node, n.experiments.compare_node, end_socket="left", path="grid"
)
graph_builder.add_edge(n.yolo.train_node, n.yolo.checkpoints_folder, end_socket="left", path="grid")
graph_builder.add_edge(
    n.yolo.train_node,
    n.yolo.overview_dummy,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    n.yolo.train_node,
    n.yolo.training_charts_dummy,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    n.yolo.train_node,
    n.yolo.eval_report_after_training,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    n.yolo.train_node,
    n.rt_detr.train_node,
    start_socket="right",
    end_socket="left",
    path="grid",
    end_plug="behind",
    dash=True,
)
graph_builder.add_edge(
    n.yolo.train_node, n.experiments.compare_node, end_socket="left", path="grid"
)
graph_builder.add_edge(n.experiments.re_eval, n.experiments.compare_node)
graph_builder.add_edge(
    n.experiments.compare_node, n.experiments.send_email, end_socket="left", path="grid"
)
graph_builder.add_edge(
    n.experiments.compare_node, n.experiments.comparison_report, end_socket="left", path="grid"
)
graph_builder.add_edge(
    n.experiments.compare_node,
    n.experiments.redeploy_settings,
    start_socket="right",
    end_socket="left",
    label="if new model is better",
)
graph_builder.add_edge(
    n.experiments.redeploy_settings,
    n.experiments.deploy_custom_model_node,
    start_socket="right",
    end_socket="right",
    path="grid",
)
graph_builder.add_edge(
    n.experiments.redeploy_settings,
    n.experiments.api_inference_node,
    end_socket="left",
    path="grid",
)

# * Build the layout
layout = graph_builder.build()
