import src.sly_globals as g
import supervisely as sly
from src.components import BaseDeployNode
from src.components.compare import CompareNode
from src.components.evaluation_report import EvaluationReportNode
from src.components.reevaluate import ReevaluateNode
from src.components.send_email.send_email import SendEmail
from src.components.send_email_node import SendEmailNode

experiments = sly.solution.LinkNode(
    x=1300,
    y=1850,
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
    x=1500,
    y=2140,
)
re_eval = ReevaluateNode(
    api=g.api,
    model_path="",
    project_info=g.project,
    x=1300,
    y=2025,
    tooltip_position="left",
)

compare_node = CompareNode(
    g.api,
    g.project,
    title="Compare Reports",
    description="Compare evaluation results from the latest training session againt the best model reference report. Helps track performance improvements over time and identify the most effective training setups. If the new model performs better, it can be used to re-deploy the NN model for pre-labeling to speed-up the process.",
    width=250,
    x=1300,
    y=2300,
    tooltip_position="left",
)
compare_node.evaluation_dirs = [
    "/model-benchmark/73_sample COCO/7958_Train YOLO v8 - v12/",
    "/model-benchmark/73_sample COCO/7958_Train YOLO v8 - v12/",
]

send_email = SendEmailNode(width=200, x=1500, y=2400)

comparison_report = sly.solution.LinkNode(
    title="Comparison Report",
    description="Quick access to the most recent comparison report"
    "between the latest training session and the best model reference. "
    "Will be used to assess improvements and decide whether to update the deployed model.",
    width=200,
    x=1500,
    y=2470,
    icon=sly.app.widgets.Icons(
        class_name="zmdi zmdi-open-in-new", color="#FF00A6", bg_color="#FFBCED"
    ),
)
comparison_report.node.disable()


deploy_node = BaseDeployNode(
    x=1000,
    y=470,
    api=g.api,
    title="Deploy Model",
    description="Deploy the trained model to the Supervisely platform for inference.",
    icon=sly.app.widgets.Icons(class_name="zmdi zmdi-deployment-unit"),
)


# @re_eval.on_finish
# def on_re_eval_finished(res_dir) -> None:
#     compare_node.evaluation_dirs.append(res_dir)
#     if compare_node.automation.is_on:
#         compare_node.run()


@compare_node.on_finish
def on_compare_finished(res_dir, res_link) -> None:
    comparison_report.card.link = res_link
    comparison_report.node.enable()
    url = sly.utils.abs_url(res_link)
    message = f"Comparison report is ready: <a href='{url}' target='_blank'>View Report</a>"
    send_email.run(text=message)

    if compare_node.is_new_model_better("mAP"):
        deploy_node.deploy(compare_node.result_best_checkpoint)
