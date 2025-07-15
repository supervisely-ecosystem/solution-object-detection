## **Python API**

## Connect to existing model

If your model is already deployed in Supervisely, you just need to connect to it using the `api.nn.connect()` method, providing a `task_id` of the running serving app. This method returns a `ModelAPI` object for running predictions.

```python
import supervisely as sly

api = sly.Api()

# Connect to a deployed model
model = api.nn.connect(
    task_id=122,  # Task ID of a running Serving App in Supervisely
)
```

## Predict

After you've connected to the model, you can use it to make predictions. Here's an example usage:

```python
# Predicting multiple images
predictions = model.predict(
    input=["image1.jpg",  "image2.jpg"],
)

# Iterating through predictions
for p in predictions:
    boxes = p.boxes  # np.array of shape (N, 4) with predicted boxes in "xyxy" format
    masks = p.masks  # np.array of shape (N, H, W) with binary masks
    scores = p.scores  # np.array of shape (N,) with predicted confidence scores
    classes = p.classes  # list of predicted class names
    annotation = p.annotation  # predictions in sly.Annotation format
    p.visualize(save_dir="./output")  # save visualization with predicted annotations
```

### Input format

The model can accept various input formats, including image paths, np.ndarray, Project ID, Image ID and others.

```python
# 1. Single image file
predictions = model.predict(
    input="path/to/image.jpg"
)
# 2. URL to an image
predictions = model.predict(
    input="https://example.com/image.jpg"
)

# 3. Load image with PIL
from PIL import Image
image = Image.open("path/to/image.jpg")

predictions = model.predict(
    input=image,
)

# 4. Numpy array of shape (H, W, C) in RGB format
import numpy as np
image_np = np.random.randint(low=0, high=255, size=(640, 640, 3), dtype="uint8")

predictions = model.predict(
    input=image_np,
)
# 5. A list of images in any format, such as paths, PIL, np.array, etc.
predictions = model.predict(
    input=["image1.jpg", "image2.jpg"],
)
# 6. A directory of images
predictions = model.predict(
    input="path/to/directory",
    recursive=True,  # Search for images in sub-directories
)
# 7. A video file
predictions = model.predict(
    input="path/to/video.mp4",
)
# 8. A local Supervisely Project containing images
predictions = model.predict(
    input="path/to/sly_project",
)
```

```python
# You can pass IDs of items from Supervisely platform

# Image ID
predictions = model.predict(image_id=12345)

# List of Image IDs
predictions = model.predict(image_ids=[12345, 67890])

# Project ID
predictions = model.predict(project_id=123)

# Dataset ID
predictions = model.predict(dataset_id=456)

# Video ID
predictions = model.predict(video_id=1212)
```

### Documentation

You can find the full documentation [here](https://docs.supervisely.com/neural-networks/overview-1/prediction-api).

## **Local inference using checkpoints**

Models trained in Supervisely can be used as a standalone PyTorch model (or ONNX / TensorRT) outside of the platform. This method completely decouple you from both Supervisely Platform and Supervisely SDK, and you will develop your own code for inference and deployment. It's also important to understand that for each neural network and framework, you'll need to set up an environment and write inference code by yourself, since each model has its own installation instructions and a format of inputs and outputs. But, in many cases, we provide examples of using the model as a standalone PyTorch model. You can find our guidelines in a GitHub repository of the corresponding model. For example, [RT-DETRv2 Demo](https://github.com/supervisely-ecosystem/RT-DETRv2/tree/main/supervisely_integration/demo#readme).

Next, we will see how to use a standalone PyTorch model in your code with RT-DETRv2 model.

### Quick start _(RT-DETRv2 example)_:

1. **Download** your checkpoint and model files from Team Files.
2. **Clone** our [RT-DETRv2](https://github.com/supervisely-ecosystem/RT-DETRv2) fork with the model implementation. Alternatively, you can use the original [RT-DETRv2](https://github.com/lyuwenyu/RT-DETR/tree/0b6972de10bc968045aba776ec1a60efea476165) repository, but you may face some unexpected issues if the authors have updated the code.

```bash
git clone https://github.com/supervisely-ecosystem/RT-DETRv2
cd RT-DETRv2
```

3. **Set up environment:** Install [requirements](https://github.com/supervisely-ecosystem/RT-DETRv2/blob/main/rtdetrv2_pytorch/requirements.txt) manually, or use our pre-built docker image ([DockerHub](https://hub.docker.com/r/supervisely/rt-detrv2/tags) | [Dockerfile](https://github.com/supervisely-ecosystem/RT-DETRv2/blob/main/docker/Dockerfile)).

```bash
pip install -r rtdetrv2_pytorch/requirements.txt
```

4. **Run inference:** Refer to our example scripts of how to load RT-DETRv2 and get predictions:

* [demo\_pytorch.py](https://github.com/supervisely-ecosystem/RT-DETRv2/blob/main/supervisely_integration/demo/demo_pytorch.py)
* [demo\_onnx.py](https://github.com/supervisely-ecosystem/RT-DETRv2/blob/main/supervisely_integration/demo/demo_onnx.py)
* [demo\_tensorrt.py](https://github.com/supervisely-ecosystem/RT-DETRv2/blob/main/supervisely_integration/demo/demo_tensorrt.py)

**demo\_pytorch.py** is a simple example of how to load a PyTorch checkpoint and get predictions. You can use it as a starting point for your own code:

```python
import json
from PIL import Image, ImageDraw
import torch
import torchvision.transforms as T
from rtdetrv2_pytorch.src.core import YAMLConfig


device = "cuda" if torch.cuda.is_available() else "cpu"

# put your files here
checkpoint_path = "model/best.pth"
config_path = "model/model_config.yml"
model_meta_path = "model/model_meta.json"
image_path = "img/coco_sample.jpg"


def draw(images, labels, boxes, scores, classes, thrh = 0.5):
    for i, im in enumerate(images):
        draw = ImageDraw.Draw(im)
        scr = scores[i]
        lab = labels[i][scr > thrh]
        box = boxes[i][scr > thrh]
        scrs = scores[i][scr > thrh]
        for j,b in enumerate(box):
            draw.rectangle(list(b), outline='red',)
            draw.text((b[0], b[1]), text=f"{classes[lab[j].item()]} {round(scrs[j].item(),2)}", fill='blue', )


if __name__ == "__main__":

    # load class names
    with open(model_meta_path, "r") as f:
        model_meta = json.load(f)
    classes = [c["title"] for c in model_meta["classes"]]

    # load model
    cfg = YAMLConfig(config_path, resume=checkpoint_path)
    checkpoint = torch.load(checkpoint_path, map_location="cpu")
    state = checkpoint["ema"]["module"] if "ema" in checkpoint else checkpoint["model"]
    model = cfg.model
    model.load_state_dict(state)
    model.deploy().to(device)
    postprocessor = cfg.postprocessor.deploy().to(device)
    h, w = 640, 640
    transforms = T.Compose([
        T.Resize((h, w)),
        T.ToTensor(),
    ])

    # prepare image
    im_pil = Image.open(image_path).convert('RGB')
    w, h = im_pil.size
    orig_size = torch.tensor([w, h])[None].to(device)
    im_data = transforms(im_pil)[None].to(device)

    # inference
    output = model(im_data)
    labels, boxes, scores = postprocessor(output, orig_size)

    # save result
    draw([im_pil], labels, boxes, scores, classes)
    im_pil.save("result.jpg")
```

### Documentation

You can find the full documentation [here](https://docs.supervisely.com/neural-networks/overview-1/using-standalone-pytorch-models).