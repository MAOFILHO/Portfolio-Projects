# Learning ML

A practical guide to foundation models, datasets, fine-tuning, job status, inference, and comparison.

## 1. Foundation model

A pre-trained model that already understands broad patterns and can be adapted to your task.

**What it does**
- Provides a strong starting point instead of training from zero.
- Reduces the amount of labeled data needed.
- Speeds up development and often improves baseline quality.
**When to use it**
- When your use case is close to a known ML problem.
- When you need faster time to value.
- When labeled data is limited or expensive.
**Examples**
- Text model adapted to support-ticket classification.
- Vision model adapted to detect defects in industrial images.
- Multimodal model used for document understanding.

## 2. Dataset

The data used to train, validate, and test the model.

**What it does**
- Teaches the model your labels, patterns, and edge cases.
- Controls how well the model generalizes to new data.
- Determines the limits of what the model can learn.
**When to use it**
- Before training or fine-tuning any model.
- When performance is inconsistent or biased.
- When your business rules change and the labels must be refreshed.
**Examples**
- Labeled emails: billing, technical, cancellation.
- Warehouse images: good product, damaged product, ambiguous.
- Call transcripts with compliance outcome labels.

## 3. Launch fine-tune

Start a training run that adapts the foundation model using your dataset.

**What it does**
- Updates model weights to better match your domain.
- Can improve accuracy, precision, recall, or style adherence.
- Creates a new model version that can be compared later.
**When to use it**
- When the base model is good but not good enough.
- When you want consistent behavior for a narrow task.
- When you need the model to learn business-specific language.
**Examples**
- Fine-tune a classifier for insurance document types.
- Fine-tune an assistant for regulated financial workflows.
- Fine-tune a vision model for defect detection.

## 4. Job status

The live state of the training or fine-tuning job.

**What it does**
- Shows progress through queueing, training, evaluation, or completion.
- Helps users know whether to wait, retry, or inspect logs.
- Provides visibility into failures and resource issues.
**When to use it**
- Whenever a fine-tuning job is running.
- When monitoring SLA or turnaround time.
- When diagnosing failed or stalled jobs.
**Examples**
- Queued, running, succeeded, failed, cancelled.
- Progress bar with % complete.
- Event log with timestamps and status updates.

## 5. Inference

Using the trained model to make predictions on new input.

**What it does**
- Returns a label, score, probability, or generated output.
- Lets the app automate decisions or assist users in real time.
- Introduces practical constraints like latency and cost.
**When to use it**
- After a model is trained and ready for production.
- When you want live predictions or batch scoring.
- When evaluation is done and the model is promoted.
**Examples**
- Classify an incoming support ticket.
- Score a transaction for fraud risk.
- Detect a defect from a new image.

## 6. Compare

Compare runs, datasets, or model versions to pick the best candidate.

**What it does**
- Makes tradeoffs visible across quality, cost, and speed.
- Supports model selection before production release.
- Helps identify regression when a new version performs worse.
**When to use it**
- After two or more runs are available.
- When deciding whether to promote a new model.
- When debugging performance changes across experiments.
**Examples**
- Compare accuracy and recall across three versions.
- Compare latency on small vs large batches.
- Compare confusion matrices for two datasets.

## Key concepts

### Overfitting

- Definition: The model learns the training data too well and does not generalize.
- Performance pattern: Very low training loss, rising validation loss.
- Causes:
  - Too many parameters for the data size
  - Not enough data
  - Too many training epochs
  - Noisy or duplicated labels
- How to fix:
  - Use more data
  - Add regularization
  - Early stopping
  - Simplify the model
  - Improve label quality

### Underfitting

- Definition: The model is too simple or undertrained to learn the pattern.
- Performance pattern: High training loss and high validation loss.
- Causes:
  - Model too small
  - Too few training steps
  - Weak features
  - Poor learning rate setup
- How to fix:
  - Train longer
  - Use a larger model
  - Improve features
  - Tune learning rate
  - Increase capacity

### Ideal fit

- Definition: The model learns the signal without memorizing the noise.
- Performance pattern: Low training loss and low validation loss with a small gap.
- Causes:
  - Balanced model capacity
  - Good data quality
  - Proper regularization
- How to fix:
  - Keep the current setup
  - Validate on fresh data
  - Monitor drift after launch

## Metrics

- **Accuracy**: Overall percent of correct predictions. Best when Classes are balanced and all mistakes matter similarly.
- **Precision**: How many predicted positives were correct. Best when False positives are expensive.
- **Recall**: How many real positives were found. Best when False negatives are expensive.
- **F1 score**: Balance between precision and recall. Best when You need one score that balances both.
- **Loss**: How far predictions are from the target. Best when Training progress and model fitting.
- **Latency**: Time to produce a prediction. Best when Real-time applications.

## Chart specs

### Training vs validation loss curve

- Type: line
- Purpose: Show underfitting, ideal fit, and overfitting.
- X axis: Epoch
- Y axis: Loss
- Interpretation: Training loss keeps dropping while validation loss turns upward after epoch 7, suggesting overfitting.
- Sample data:
```json
[
  {
    "epoch": 1,
    "training_loss": 1.2,
    "validation_loss": 1.25
  },
  {
    "epoch": 2,
    "training_loss": 0.98,
    "validation_loss": 1.05
  },
  {
    "epoch": 3,
    "training_loss": 0.82,
    "validation_loss": 0.94
  },
  {
    "epoch": 4,
    "training_loss": 0.68,
    "validation_loss": 0.88
  },
  {
    "epoch": 5,
    "training_loss": 0.56,
    "validation_loss": 0.83
  },
  {
    "epoch": 6,
    "training_loss": 0.47,
    "validation_loss": 0.81
  },
  {
    "epoch": 7,
    "training_loss": 0.4,
    "validation_loss": 0.8
  },
  {
    "epoch": 8,
    "training_loss": 0.34,
    "validation_loss": 0.82
  },
  {
    "epoch": 9,
    "training_loss": 0.29,
    "validation_loss": 0.86
  },
  {
    "epoch": 10,
    "training_loss": 0.25,
    "validation_loss": 0.92
  }
]
```

### Model comparison bar chart

- Type: bar
- Purpose: Compare model versions on accuracy and F1 score.
- X axis: Model version
- Y axis: Score
- Interpretation: Version v3 performs best overall and is the strongest candidate for promotion.
- Sample data:
```json
[
  {
    "model": "v1",
    "accuracy": 0.81,
    "f1": 0.78
  },
  {
    "model": "v2",
    "accuracy": 0.85,
    "f1": 0.83
  },
  {
    "model": "v3",
    "accuracy": 0.88,
    "f1": 0.87
  }
]
```

### Confusion matrix

- Type: heatmap
- Purpose: Show where the model confuses one class with another.
- X axis: Predicted class
- Y axis: Actual class
- Interpretation: Most predictions are correct, but technical and cancellation are being confused in some cases.
- Sample data:
```json
[
  [
    48,
    2,
    1
  ],
  [
    4,
    41,
    5
  ],
  [
    1,
    6,
    42
  ]
]
```

### Job status timeline

- Type: timeline
- Purpose: Explain the sequence of a fine-tuning run.
- X axis: Time
- Y axis: Status
- Interpretation: The job moves through setup, training, evaluation, and success.
- Sample data:
```json
[
  {
    "time": "4:29 PM",
    "status": "Started"
  },
  {
    "time": "4:31 PM",
    "status": "Preprocessing"
  },
  {
    "time": "4:36 PM",
    "status": "Training"
  },
  {
    "time": "4:42 PM",
    "status": "Evaluating"
  },
  {
    "time": "4:48 PM",
    "status": "Succeeded"
  }
]
```

### Latency vs accuracy scatter plot

- Type: scatter
- Purpose: Show tradeoffs between speed and quality.
- X axis: Latency (ms)
- Y axis: Accuracy
- Interpretation: Higher accuracy often costs more latency; choose the point that fits the product requirement.
- Sample data:
```json
[
  {
    "model": "A",
    "latency_ms": 45,
    "accuracy": 0.82
  },
  {
    "model": "B",
    "latency_ms": 70,
    "accuracy": 0.86
  },
  {
    "model": "C",
    "latency_ms": 120,
    "accuracy": 0.89
  },
  {
    "model": "D",
    "latency_ms": 35,
    "accuracy": 0.77
  },
  {
    "model": "E",
    "latency_ms": 95,
    "accuracy": 0.88
  }
]
```
