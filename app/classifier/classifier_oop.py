

from pathlib import Path

from PIL import Image
import torch
from transformers import AutoImageProcessor, SiglipForImageClassification


# Class 1: Handles the input image.
class WasteImage:
    def __init__(self, image_path):
        self._image_path = None
        self.set_image_path(image_path)

    def get_image_path(self):
        return str(self._image_path)

    def set_image_path(self, image_path):
        path = Path(image_path)
        if not path.is_file():
            raise FileNotFoundError(f"Image not found: {path}")
        self._image_path = path

    def load_image(self):
        with Image.open(self._image_path) as image:
            return image.convert("RGB")


# Class 2: Stores the predicted waste type and confidence.
class PredictionResult:
    def __init__(self, label, confidence):
        self._label = ""
        self._confidence = 0.0
        self.set_label(label)
        self.set_confidence(confidence)

    def get_label(self):
        return self._label

    def set_label(self, label):
        if not isinstance(label, str) or not label.strip():
            raise ValueError("Label must be a non-empty string.")
        self._label = label.strip()

    def get_confidence(self):
        return self._confidence

    def set_confidence(self, confidence):
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            raise ValueError("Confidence must be a number between 0 and 1.")
        self._confidence = float(confidence)


# Class 3: Loads the AI model and classifies images.
class WasteClassifier:
    def __init__(self, model_name="prithivMLmods/Augmented-Waste-Classifier-SigLIP2"):
        self._model_name = ""
        self._processor = None
        self._model = None
        self.set_model_name(model_name)

    def get_model_name(self):
        return self._model_name

    def set_model_name(self, model_name):
        if not isinstance(model_name, str) or not model_name.strip():
            raise ValueError("Model name must be a non-empty string.")
        self._model_name = model_name.strip()
        # Reload if the selected model is changed later.
        self._processor = None
        self._model = None

    def initialize_model(self):
        if self._model is None:
            self._processor = AutoImageProcessor.from_pretrained(self._model_name)
            self._model = SiglipForImageClassification.from_pretrained(self._model_name)
            self._model.eval()

    def classify(self, waste_image):
        if isinstance(waste_image, Image.Image):      # PIL image from the web app
            image = waste_image.convert("RGB")
        else:
            if isinstance(waste_image, (str, Path)):
                waste_image = WasteImage(waste_image)
            if not isinstance(waste_image, WasteImage):
                raise TypeError("Expected a WasteImage, an image path or a PIL image.")
            image = waste_image.load_image()
        self.initialize_model()
        inputs = self._processor(images=image, return_tensors="pt")

        with torch.inference_mode():
            outputs = self._model(**inputs)

        probabilities = torch.softmax(outputs.logits, dim=1)
        predicted_id = probabilities.argmax(dim=1).item()
        confidence = probabilities[0][predicted_id].item()
        label = self._model.config.id2label[predicted_id]

        return PredictionResult(label, confidence)


# Class 4: Evaluates predictions when ground-truth labels are available.
class ModelEvaluator:
    def __init__(self, actual_labels=None, predicted_labels=None):
        self._actual_labels = []
        self._predicted_labels = []
        self.set_actual_labels(actual_labels if actual_labels is not None else [])
        self.set_predicted_labels(predicted_labels if predicted_labels is not None else [])

    def get_actual_labels(self):
        return self._actual_labels.copy()

    def set_actual_labels(self, labels):
        self._actual_labels = list(labels)

    def get_predicted_labels(self):
        return self._predicted_labels.copy()

    def set_predicted_labels(self, labels):
        self._predicted_labels = list(labels)

    def add_prediction(self, actual_label, predicted_label):
        self._actual_labels.append(actual_label)
        self._predicted_labels.append(predicted_label)

    def reset(self):
        self._actual_labels = []
        self._predicted_labels = []

    def evaluate(self):
        if not self._actual_labels:
            raise ValueError("No labelled predictions to evaluate.")
        if len(self._actual_labels) != len(self._predicted_labels):
            raise ValueError("Actual and predicted label counts must match.")

        from sklearn.metrics import (
            accuracy_score,
            classification_report,
            confusion_matrix,
            precision_recall_fscore_support,
        )

        precision, recall, f1, _ = precision_recall_fscore_support(
            self._actual_labels,
            self._predicted_labels,
            average="macro",
            zero_division=0,
        )
        labels = sorted(set(self._actual_labels + self._predicted_labels))

        return {
            "accuracy": accuracy_score(self._actual_labels, self._predicted_labels),
            "macro_precision": precision,
            "macro_recall": recall,
            "macro_f1": f1,
            "labels": labels,
            "confusion_matrix": confusion_matrix(
                self._actual_labels, self._predicted_labels, labels=labels
            ).tolist(),
            "classification_report": classification_report(
                self._actual_labels, self._predicted_labels, zero_division=0
            ),
        }

if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print('Usage: python classifier_oop.py "path/to/image.jpg"')
    else:
        classifier = WasteClassifier()
        result = classifier.classify(sys.argv[1])

        print("Detected Waste:", result.get_label())
        print("Confidence:", round(result.get_confidence() * 100, 2), "%")
