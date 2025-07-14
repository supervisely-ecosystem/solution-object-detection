import src.sly_globals as g
import supervisely as sly
from src.components.compare import CompareNode
from src.components.evaluation_report import EvaluationReportNode
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
    tooltip_position="left",
)
re_eval_dummy = sly.solution.LinkNode(
    title="Re-evaluate Model",
    description="Re-evaluate the model on the latest labeled data from the Training Project. ",
    link="",
    width=250,
    x=1300,
    y=2025,
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

email_creds = SendEmail.EmailCredentials("user123@gmail.com", "pass123")
send_email = SendEmailNode(
    email_creds,
    target_addresses="user321@gmail.com",
    width=200,
    x=1500,
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
    x=1500,
    y=2470,
    icon=sly.app.widgets.Icons(
        class_name="zmdi zmdi-open-in-new", color="#FF00A6", bg_color="#FFBCED"
    ),
    tooltip_position="left",
)
comparison_report.node.disable()
