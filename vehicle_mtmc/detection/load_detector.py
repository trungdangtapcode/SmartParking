from pathlib import Path
import torch
import os


def load_yolo(which):
    """Load a yolo network from local repository. Download the weights there if needed."""
    
    # Check if it's a custom .pt file path
    if which.endswith('.pt') or os.path.exists(which) or os.path.exists(f'{which}.pt'):
        try:
            from ultralytics import YOLO
            # Use the path as-is if it ends with .pt, otherwise add .pt
            model_path = which if which.endswith('.pt') else f'{which}.pt'
            model = YOLO(model_path)
            return YOLOv8Wrapper(model)
        except ImportError:
            raise ImportError("ultralytics package not installed. Run: pip install ultralytics")
    
    # Check if it's a YOLOv8/v11 model name
    if which.startswith('yolov8') or which.startswith('yolo11'):
        try:
            from ultralytics import YOLO
            model = YOLO(f'{which}.pt')
            # Wrap in a class to make it compatible with YOLOv5 interface
            return YOLOv8Wrapper(model)
        except ImportError:
            raise ImportError("ultralytics package not installed. Run: pip install ultralytics")
    
    # YOLOv5 loading
    cwd = Path.cwd()
    yolo_dir = str(Path(__file__).parent.joinpath("yolov5"))
    os.chdir(yolo_dir)
    model = torch.hub.load(yolo_dir, which, source="local")
    os.chdir(str(cwd))
    return model


class YOLOv8Wrapper:
    """Wrapper to make YOLOv8 compatible with YOLOv5 interface."""
    
    def __init__(self, model):
        self.model = model
        self.device_type = 'cpu'
    
    def to(self, device):
        self.device_type = str(device)
        self.model.to(device)
        return self
    
    def __call__(self, img):
        results = self.model(img, verbose=False, device=self.device_type)
        return YOLOv8Results(results[0])


class YOLOv8Results:
    """Wrapper to make YOLOv8 results compatible with YOLOv5 results."""
    
    def __init__(self, results):
        self.results = results
        self.xywh = [self._get_xywh()]
    
    def _get_xywh(self):
        import torch
        boxes = self.results.boxes
        if len(boxes) == 0:
            return torch.zeros((0, 6))
        
        # Convert xyxy to xywh (center x, center y, width, height)
        xyxy = boxes.xyxy
        xywh = torch.zeros_like(xyxy[:, :4])
        xywh[:, 0] = (xyxy[:, 0] + xyxy[:, 2]) / 2  # center x
        xywh[:, 1] = (xyxy[:, 1] + xyxy[:, 3]) / 2  # center y
        xywh[:, 2] = xyxy[:, 2] - xyxy[:, 0]  # width
        xywh[:, 3] = xyxy[:, 3] - xyxy[:, 1]  # height
        
        # Combine with confidence and class
        result = torch.cat([xywh, boxes.conf.unsqueeze(1), boxes.cls.unsqueeze(1)], dim=1)
        return result.cpu()
