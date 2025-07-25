from supervisely._utils import abs_url, is_development
from supervisely.app.widgets import Icons
from supervisely.solution import LinkNode


class AllExperimentsNode(LinkNode):
    def __init__(
        self,
        x: int = 0,
        y: int = 0,
        *args,
        **kwargs,
    ):
        title = "All Experiments"
        description = "Track all experiments in one place. The best model for comparison will be selected from the list of experiments based on the primary metric (mAP for detection, IoU for semantic segmentation)."
        link = abs_url("/nn/experiments") if is_development() else "/nn/experiments"
        icon = Icons(class_name="zmdi zmdi-chart", color="#1976D2", bg_color="#E3F2FD")

        super().__init__(
            title=title,
            description=description,
            link=link,
            width=250,
            x=x,
            y=y,
            icon=icon,
            tooltip_position="right",
            *args,
            **kwargs,
        )
        self._best_model = None
        self._update_properties()

    @property
    def best_model(self):
        return self._best_model

    @best_model.setter
    def best_model(self, value):
        """
        Set the best model for comparison.

        :param value: Name or ID of the best model.
        """
        self.set_best_model(value)

    def set_best_model(self, model_path: str):
        """
        Set the best model for comparison.

        :param model_name: Name or ID of the best model.
        """
        if not isinstance(model_path, str):
            raise ValueError("Best model must be a string representing the model path.")
        if not model_path.startswith("/"):
            raise ValueError(
                "Best model should be from Team Files. Path must start with '/'. E.g. '/experiments/2730_my_project/48650_YOLO/checkpoints/best.pt'."
            )
        self._best_model = model_path
        self._update_properties()

    def _update_properties(self):
        """
        Update the properties of the node.
        This method can be overridden to customize the node's behavior.
        """
        if self.best_model:
            model_name = self._best_model.split("/")[-1]
            link = (
                abs_url(f"/files/?path={self.best_model}")
                if is_development()
                else f"/files/?path={self.best_model}"
            )
        else:
            model_name = "Not set"
            link = None
        if self._best_model:
            new_prop = {
                "key": "Best Model",
                "value": model_name,
                "highlight": False,
                "link": link,
            }
            self.card.update_property(**new_prop)
        else:
            self.card.remove_property_by_key("Best Model")
