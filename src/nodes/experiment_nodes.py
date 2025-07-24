import src.sly_globals as g
import supervisely as sly
from src.components import BaseDeployNode
from src.components.all_experiments import AllExperimentsNode
from src.components.compare import CompareNode
from src.components.custom_model import DeployCustomModel
from src.components.evaluation import EvaluationNode
from src.components.evaluation_report import EvaluationReportNode
from src.components.redeploy_settings import RedeploySettingsNode
from src.components.send_email.send_email import SendEmail
from src.components.send_email_node import SendEmailNode

experiments = AllExperimentsNode(x=1300, y=1850)
experiments.set_best_model("/experiments/73_sample COCO/7958_YOLO/checkpoints/best.pt")

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
evaluation_report.node.disable()

re_eval = EvaluationNode(
    api=g.api,
    project=g.project,
    collection=g.val_collection,
    x=1265,
    y=2025,
    tooltip_position="left",
)
re_eval.set_model_path(
    "/mmsegmentation/2266_coffee-leaf-biotic-stress/checkpoints/data/best_aAcc_epoch_18.pth"
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

redeploy_settings = RedeploySettingsNode(x=1800, y=2300)
deploy_custom_model_node = DeployCustomModel(x=1000, y=470, api=g.api)
api_inference_node = ApiInferenceNode(
    "src/assets/api_inference.md",
    x=2000,
    y=2400,
    tooltip_position="left",
    markdown_title="Inference API Quickstart",
)


@re_eval.on_finish
def on_re_eval_finished(res_dir) -> None:
    evaluation_report.set_benchmark_dir(res_dir)
    evaluation_report.node.enable()
    compare_node.evaluation_dirs.append(res_dir)
    compare_node.evaluation_dirs.append(res_dir) # TODO: temp fix
    compare_node.run()


@compare_node.on_finish
def on_compare_finished(res_dir, res_link) -> None:
    comparison_report.card.link = res_link
    comparison_report.node.enable()
    if send_email.is_email_sending_enabled:
        url = sly.utils.abs_url(res_link)
        message = f"Comparison report is ready: <a href='{url}' target='_blank'>View Report</a>"
        send_email.run(text=message)

    if redeploy_settings.is_enabled() and compare_node.is_new_model_better("mAP"):
        agent_id = redeploy_settings.get_agent_id()
        deploy_custom_model_node.deploy(
            model=compare_node.result_best_checkpoint, agent_id=agent_id
        )
