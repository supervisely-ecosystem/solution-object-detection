import src.nodes.rt_detr_nodes as rt_detr
import src.nodes.yolo_nodes as yolo
import src.sly_functions as f
import src.sly_globals as g
import supervisely as sly
from src.components.all_experiments import AllExperimentsNode
from src.components.api_inference import ApiInferenceNode
from src.components.compare import CompareNode
from src.components.custom_model import DeployCustomModel
from src.components.evaluation import EvaluationNode
from src.components.evaluation_report import EvaluationReportNode
from src.components.redeploy_settings import RedeploySettingsNode
from src.components.send_email.send_email import SendEmail
from src.components.send_email_node import SendEmailNode

experiments = AllExperimentsNode(x=1300, y=1850, project_id=g.project.id, task_type="detection")
# experiments.set_best_model("/experiments/73_sample COCO/7958_YOLO/checkpoints/best.pt")

evaluation_report = EvaluationReportNode(
    api=g.api,
    description="Quick access to the latest evaluation report of the best model from the Experiments. The report contains the model performance metrics and visualizations. Will be used as a reference for comparing with models from the next experiments.",
    width=200,
    x=1500,
    y=2140,
)
evaluation_report.node.disable()

re_eval = EvaluationNode(
    api=g.api,
    project=g.training_project,
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
    title="Compare Models",
    description="Compare evaluation results from the latest training session againt the best model reference report. Helps track performance improvements over time and identify the most effective training setups. If the new model performs better, it can be used to re-deploy the NN model for pre-labeling to speed-up the process.",
    x=1300,
    y=2300,
    tooltip_position="left",
)
# compare_node.evaluation_dirs = [
#     "/model-benchmark/73_sample COCO/7958_Train YOLO v8 - v12/",
#     "/model-benchmark/73_sample COCO/7958_Train YOLO v8 - v12/",
# ]

send_email = SendEmailNode(width=200, x=1500, y=2400)

comparison_report = EvaluationReportNode(
    api=g.api,
    title="Comparison Report",
    description="Quick access to the most recent comparison report"
    "between the latest training session and the best model reference. "
    "Will be used to assess improvements and decide whether to update the deployed model.",
    width=200,
    x=1500,
    y=2470,
)
comparison_report.node.disable()

redeploy_settings = RedeploySettingsNode(x=1800, y=2300)
deploy_custom_model_node = DeployCustomModel(x=1000, y=470, api=g.api)
api_inference_node = ApiInferenceNode(
    "src/assets/api_inference.md",
    x=2000,
    y=2400,
    markdown_title="Inference API Quickstart",
)


@re_eval.on_start
def on_re_eval_started():
    evaluation_report.hide_new_report_badge()
    evaluation_report.node.disable()


@re_eval.on_finish
def on_re_eval_finished(res_dir) -> None:
    evaluation_report.set_benchmark_dir(res_dir)
    evaluation_report.node.enable()
    compare_node.evaluation_dirs.append(res_dir)
    comparison_report.hide_new_report_badge()
    comparison_report.node.disable()
    compare_node.run()


@compare_node.on_finish
def on_compare_finished(res_dir, res_link) -> None:
    comparison_report.card.link = res_link
    comparison_report.show_new_report_badge()
    comparison_report.node.enable()
    if send_email.is_email_sending_enabled:
        url = sly.utils.abs_url(res_link)
        message = f"Comparison report is ready: <a href='{url}' target='_blank'>View Report</a>"
        send_email.run(text=message)

    if redeploy_settings.is_enabled() and compare_node.is_new_model_better(primary_metric="mAP"):
        agent_id = redeploy_settings.get_agent_id()
        deployed_task_id = deploy_custom_model_node.deploy(
            model=compare_node.result_best_checkpoint, agent_id=agent_id
        )
        api_inference_node.set_task_id(deployed_task_id)


@rt_detr.train_node.on_train_started
def _on_train_rt_detr_started():
    evaluation_report.hide_new_report_badge()
    evaluation_report.node.disable()
    rt_detr.eval_report_after_training.hide_new_report_badge()
    rt_detr.eval_report_after_training.node.disable()
    rt_detr.overview_dummy.node.disable()
    rt_detr.training_charts_dummy.node.disable()
    rt_detr.checkpoints_folder.node.disable()


@yolo.train_node.on_train_started
def _on_train_yolo_started():
    evaluation_report.hide_new_report_badge()
    evaluation_report.node.disable()
    yolo.eval_report_after_training.hide_new_report_badge()
    yolo.yolo_eval_report_after_training.node.disable()
    yolo.overview_dummy.node.disable()
    yolo.training_charts_dummy.node.disable()
    yolo.checkpoints_folder.node.disable()


@rt_detr.train_node.on_train_finished
def _on_train_rt_detr_finished(task_id: int):
    task_info = g.api.task.get_info_by_id(task_id)
    if task_info is None:
        sly.logger.error(f"Task with ID {task_info['id']} not found.")
        return None

    # * Set app session URL for the custom model deployment node
    session_url = f._get_app_session_from_task_info(task_info)
    if session_url:
        rt_detr.training_charts_dummy.card.link = session_url

    # * Set checkpoints directory for the RT-DETR training node
    checkpoints_dir = f._get_checkpoints_dir_from_task_info(task_info)
    if checkpoints_dir:
        rt_detr.checkpoints_folder.card.link = checkpoints_dir
        rt_detr.checkpoints_folder.node.enable()

    # * Get evaluation report directory from the task info
    report_eval_dir = f._get_eval_dir_from_task_info(g.api, task_info)
    if report_eval_dir is None:
        sly.logger.error(f"Evaluation directory for task {task_id} not found.")
        return

    # * Clear previous evaluation directories
    compare_node.evaluation_dirs = []

    # * Update evaluation report after training
    rt_detr.eval_report_after_training.set_benchmark_dir(report_eval_dir)
    rt_detr.eval_report_after_training.node.enable()

    if experiments.best_model:
        # * Start re-evaluation the best model on new validation set
        re_eval.set_model_path(experiments.best_model)
        re_eval.run()
        # * Add evaluation report directory to the compare node
        compare_node.evaluation_dirs.append(report_eval_dir)
    elif model_path := f._get_best_model_from_task_info(task_info):
        # * Set best model from task info if not set yet
        experiments.set_best_model(model_path)
        evaluation_report.set_benchmark_dir(report_eval_dir)
        evaluation_report.node.enable()
        if redeploy_settings.is_enabled():
            sly.logger.info("Redeploying the best model after RT-DETR training.")
            agent_id = redeploy_settings.get_agent_id()
            deployed_task_id = deploy_custom_model_node.deploy(
                model=experiments.best_model, agent_id=agent_id
            )
            api_inference_node.set_task_id(deployed_task_id)


@yolo.train_node.on_train_finished
def _on_train_yolo_finished(task_id: int):
    task_info = g.api.task.get_info_by_id(task_id)
    if task_info is None:
        sly.logger.error(f"Task with ID {task_info['id']} not found.")
        return None

    # * Set app session URL for the custom model deployment node
    sesioon_url = f._get_app_session_from_task_info(task_info)
    if sesioon_url:
        yolo.overview_dummy.card.link = sesioon_url

    # * Set checkpoints directory for the YOLO training node
    checkpoints_dir = f._get_checkpoints_dir_from_task_info(task_info)
    if checkpoints_dir:
        yolo.checkpoints_folder.card.link = checkpoints_dir
        yolo.checkpoints_folder.node.enable()

    # * Get evaluation report directory from the task info
    report_eval_dir = f._get_eval_dir_from_task_info(g.api, task_info)
    if report_eval_dir is None:
        sly.logger.error(f"Evaluation directory for task {task_id} not found.")
        return

    # * Clear previous evaluation directories
    compare_node.evaluation_dirs = []

    # * Update evaluation report after training
    yolo.eval_report_after_training.set_benchmark_dir(report_eval_dir)
    yolo.eval_report_after_training.node.enable()

    if experiments.best_model:
        # * Start re-evaluation the best model on new validation set
        re_eval.set_model_path(experiments.best_model)
        re_eval.run()

        # * Add evaluation report directory to the compare node
        compare_node.evaluation_dirs.append(report_eval_dir)
    elif model_path := f._get_best_model_from_task_info(task_info):
        # * Set best model from task info if not set yet
        experiments.set_best_model(model_path)
        evaluation_report.set_benchmark_dir(report_eval_dir)
        evaluation_report.node.enable()
        if redeploy_settings.is_enabled():
            sly.logger.info("Redeploying the best model after YOLO training.")
            agent_id = redeploy_settings.get_agent_id()
            deployed_task_id = deploy_custom_model_node.deploy(
                model=experiments.best_model, agent_id=agent_id
            )
            api_inference_node.set_task_id(deployed_task_id)
