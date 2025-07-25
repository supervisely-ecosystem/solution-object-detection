from src.components.base_deploy import BaseDeployNode
from supervisely.api.api import Api


class DeployCustomModel(BaseDeployNode):
    """
    CustomModel class for managing custom model components in the Supervisely platform.
    This class is used to create and manage custom models, including their properties and configurations.
    """

    def __init__(self, x: int, y: int, api: Api, *args, **kwargs):
        """
        Initializes the CustomModel node with the given parameters.

        :param x: X coordinate for the node position.
        :param y: Y coordinate for the node position.
        :param api: Supervisely API instance.
        :param args: Additional positional arguments.
        :param kwargs: Additional keyword arguments.
        """
        super().__init__(
            x=x,
            y=y,
            api=api,
            title="Custom Model",
            description="Deploy and manage custom models trained in Supervisely on your data. This node provides interface for deploying custom models, monitoring agents memory usage.",
            *args,
            **kwargs,
        )
        self.title = "Custom Model"
        self.description = "Manage custom models and their configurations."
