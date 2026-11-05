from types import SimpleNamespace

from app.streaming.processors import (
    ResultStream,
    ConfidenceFilter,
    LabelNormalizer,
    TopKLimiter,
)

# Sample predictions from an image classification system
predictions = [
    SimpleNamespace(label="PET", confidence=0.95),
    SimpleNamespace(label="HDPE", confidence=0.20),
    SimpleNamespace(label="aluminum can", confidence=0.88),
    SimpleNamespace(label="battery", confidence=0.80),
]

# Build the processing pipeline
pipeline = (
    ConfidenceFilter(0.35)
    | LabelNormalizer()
    | TopKLimiter(3)
)

print("Pipeline:", pipeline)
print("Total input predictions:", len(predictions))
print("\nProcessed results:")

# Process predictions one by one
stream = ResultStream(predictions)

for result in pipeline(stream):
    print(
        "Label:", result.label,
        "| Confidence:", f"{result.confidence:.0%}",
        "| Material:", result.material
    )
