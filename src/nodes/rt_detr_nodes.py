import src.sly_globals as g
import supervisely as sly
from src.components.base_train import BaseTrainNode, RTDETRv2TrainNode
from src.components.evaluation_report import EvaluationReportNode


train_node = RTDETRv2TrainNode(
    api=g.api,
    project=g.training_project.id,
    title="Train RT-DETR-v2",
    description="Train the model on the labeled data from the Training Project. ",
    icon=sly.app.widgets.Icons(class_name="zmdi zmdi-memory"),
    x=635,
    y=1850,
)
train_node.set_collection_ids(
    train_collection_id=g.train_collection.id, val_collection_id=g.val_collection.id
)

overview_dummy = sly.solution.LinkNode(
    title="Overview + how to use model",
    description="Quick access to the overview of the model and how to use it for inference. ",
    link="",
    width=250,
    x=800,
    y=2000,
    icon=sly.app.widgets.Icons(
        class_name="zmdi zmdi-open-in-new", color="#1976D2", bg_color="#E3F2FD"
    ),
)
overview_dummy.node.disable()
training_charts_dummy = sly.solution.LinkNode(
    title="Training Charts",
    description="Quick access to the training charts of the training session. ",
    link="",
    width=250,
    x=800,
    y=2070,
    icon=sly.app.widgets.Icons(
        class_name="zmdi zmdi-open-in-new", color="#1976D2", bg_color="#E3F2FD"
    ),
)
training_charts_dummy.node.disable()
checkpoints_folder = sly.solution.LinkNode(
    title="Checkpoints Folder",
    description="View the folder containing the model checkpoints.",
    link="",
    width=200,
    x=800,
    y=2140,
    icon=sly.app.widgets.Icons(class_name="zmdi zmdi-folder", color="#1976D2", bg_color="#E3F2FD"),
)
checkpoints_folder.node.disable()
eval_report_after_training = EvaluationReportNode(
    g.api,
    description="Quick access to the evaluation report of the model after training. The report contains the model performance metrics and visualizations.",
    x=800,
    y=2210,
)
eval_report_after_training.node.disable()
