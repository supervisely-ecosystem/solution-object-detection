import src.nodes as n
import supervisely as sly

# * Create a SolutionGraphBuilder instance
graph_builder = sly.solution.SolutionGraphBuilder(height="2800px")

# * Add nodes to the graph
graph_builder.add_node(n.cloud_import)
graph_builder.add_node(n.auto_import)
graph_builder.add_node(n.input_project)
graph_builder.add_node(n.sampling)
graph_builder.add_node(n.labeling_project_node)
graph_builder.add_node(n.queue)
graph_builder.add_node(n.labeling_performance)
graph_builder.add_node(n.splits)
graph_builder.add_node(n.move_labeled)
graph_builder.add_node(n.training_project)
graph_builder.add_node(n.versioning)
graph_builder.add_node(n.train_node)
graph_builder.add_node(n.experiments)
graph_builder.add_node(n.evaluation_report)
graph_builder.add_node(n.re_eval_dummy)
graph_builder.add_node(n.overview_dummy)
graph_builder.add_node(n.eval_report_after_training)
graph_builder.add_node(n.training_charts_dummy)
graph_builder.add_node(n.checkpoints_folder)
graph_builder.add_node(n.compare_node)
graph_builder.add_node(n.send_email)
graph_builder.add_node(n.comparison_report)
graph_builder.add_node(n.deploy_node)
graph_builder.add_node(n.train_node)

# * Add edges between nodes
graph_builder.add_edge(n.cloud_import, n.input_project, path="grid")
graph_builder.add_edge(n.auto_import, n.input_project, path="grid")
graph_builder.add_edge(n.input_project, n.sampling)
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
graph_builder.add_edge(n.versioning, n.train_node)
graph_builder.add_edge(n.experiments, n.re_eval_dummy, path="grid", label="best model overall")
graph_builder.add_edge(n.re_eval_dummy, n.evaluation_report, end_socket="left", path="grid")
graph_builder.add_edge(n.train_node, n.checkpoints_folder, end_socket="left", path="grid")
graph_builder.add_edge(
    n.train_node,
    n.overview_dummy,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    n.train_node,
    n.training_charts_dummy,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    n.train_node,
    n.eval_report_after_training,
    end_socket="left",
    path="grid",
)
graph_builder.add_edge(
    n.train_node,
    n.experiments,
    start_socket="right",
    end_socket="left",
    path="grid",
    dash=True,
    label="register experiments",
)
graph_builder.add_edge(n.train_node, n.compare_node, end_socket="left", path="grid")
graph_builder.add_edge(n.re_eval_dummy, n.compare_node)
graph_builder.add_edge(n.compare_node, n.send_email, end_socket="left", path="grid")
graph_builder.add_edge(n.compare_node, n.comparison_report, end_socket="left", path="grid")

# * Build the layout
layout = graph_builder.build()
