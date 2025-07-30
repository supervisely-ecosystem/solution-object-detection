## Connect to existing model

Once your model is deployed in Supervisely, you can connect to it using the `api.nn.connect()` method. You need to provide the `task_id` of the running serving app. This method returns a `ModelAPI` object that you can use to run predictions.

```python
import supervisely as sly

api = sly.Api.from_env()

model = api.nn.connect(task_id=12345)
```

## Predict

After you've connected to the model, you can use it to make predictions. Here's an example usage:

```python
# Predicting multiple images
predictions = model.predict(
    input=["path/to/image1.jpg",  "path/to/image2.jpg"],
)

# Iterating through predictions
for p in predictions:
    boxes = p.boxes
    masks = p.masks
    scores = p.scores
    classes = p.classes
    annotation = p.annotation
    p.visualize(save_dir="./output")
```

<details>
<summary>Input format (click to expand)</summary>

The model can accept various inputs:

```python
# 1. Single image file
predictions = model.predict(input="path/to/image.jpg")

# 2. URL
predictions = model.predict(input="https://.../image.jpg")

# 3. PIL.Image
from PIL import Image
image = Image.open("path/to/image.jpg")
predictions = model.predict(input=image)

# 4. NumPy array
import numpy as np
image_np = np.random.randint(0,255,(640,640,3),dtype="uint8")
predictions = model.predict(input=image_np)

# 5. Mixed list
predictions = model.predict(input=["img1.jpg","img2.jpg"])

# 6. Directory (recursive)
predictions = model.predict(input="path/to/dir", recursive=True)

# 7. Video file
predictions = model.predict(input="path/to/video.mp4")

# 8. Supervisely project
predictions = model.predict(input="path/to/sly_project")
```

You can also pass Supervisely IDs:

```python
predictions = model.predict(image_id=12345)
predictions = model.predict(image_ids=[12345,67890])
predictions = model.predict(project_id=123)
predictions = model.predict(dataset_id=456)
predictions = model.predict(video_id=1212)
```

</details>

<details>
<summary>Local inference using checkpoints (click to expand)</summary>

Models can also be run standalone (PyTorch / ONNX / TensorRT). You’ll need to:

1. Download your checkpoint & model files.
2. Clone the integration demo repo:
   ```bash
   git clone https://github.com/supervisely-ecosystem/RT-DETRv2
   cd RT-DETRv2
   ```
3. Install requirements:
   ```bash
   pip install -r rtdetrv2_pytorch/requirements.txt
   ```
4. Run one of the demos (PyTorch / ONNX / TensorRT):

   - [demo_pytorch.py](https://github.com/supervisely-ecosystem/RT-DETRv2/blob/main/supervisely_integration/demo/demo_pytorch.py)
   - [demo_onnx.py](https://github.com/supervisely-ecosystem/RT-DETRv2/blob/main/supervisely_integration/demo/demo_onnx.py)
   - [demo_tensorrt.py](https://github.com/supervisely-ecosystem/RT-DETRv2/blob/main/supervisely_integration/demo/demo_tensorrt.py)

Example snippet from `demo_pytorch.py`:

```python
import torch, json
from PIL import Image, ImageDraw
from rtdetrv2_pytorch.src.core import YAMLConfig
import torchvision.transforms as T

# setup
device = "cuda" if torch.cuda.is_available() else "cpu"
checkpoint = "model/best.pth"
cfg = YAMLConfig("model/model_config.yml", resume=checkpoint)
model = cfg.model
model.load_state_dict(torch.load(checkpoint,map_location="cpu")["model"])
model.deploy().to(device)

# inference
im = Image.open("img/coco_sample.jpg").convert('RGB')
transforms = T.Compose([T.Resize((640,640)), T.ToTensor()])
data = transforms(im)[None].to(device)
output = model(data)
# ...postprocess & draw...
```

See full standalone inference documentation [here](https://docs.supervisely.com/neural-networks/overview-1/using-standalone-pytorch-models).

</details>
