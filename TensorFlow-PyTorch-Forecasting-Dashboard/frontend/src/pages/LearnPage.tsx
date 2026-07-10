import { ConceptSection } from "../components/ConceptSection";

export function LearnPage() {
  return (
    <div>
      <div className="page-header">
        <h1 className="page-title">Learn: PyTorch vs. TensorFlow / tf.keras</h1>
      </div>
      <p className="learn-intro">
        This project implements the same LSTM forecasting model twice — once
        in <strong>TensorFlow/Keras</strong> (<code>backend/src/lstm_model.py</code>)
        and once in <strong>PyTorch</strong> (
        <code>backend/src/lstm_pytorch_model.py</code>) — so you can run both
        side-by-side from the sidebar and compare them directly. The sections
        below walk through the core deep-learning concepts both frameworks
        share, showing how each one expresses them, and pointing to where
        that concept shows up in this project's actual code. A few topics
        (CNNs, transfer learning, confusion matrices) aren't part of this
        time-series use case — they're included for completeness of the
        framework comparison and marked as general reference.
      </p>

      <ConceptSection
        title="1. Tensor Creation"
        description="Both frameworks represent data as n-dimensional arrays (tensors) with GPU/accelerator support. PyTorch tensors are eager by default; TensorFlow tensors are also eager since TF2, backed by the same core array semantics as NumPy."
        pytorchCode={`import torch

x = torch.tensor([[1.0, 2.0], [3.0, 4.0]])
zeros = torch.zeros((60, 1))          # matches this project's window shape
random = torch.randn(1, 60, 1)        # (batch, window, features)`}
        tensorflowCode={`import tensorflow as tf

x = tf.constant([[1.0, 2.0], [3.0, 4.0]])
zeros = tf.zeros((60, 1))
random = tf.random.normal((1, 60, 1))`}
        projectNote={
          "In this project, the temperature series is scaled with scikit-learn's StandardScaler " +
          "and reshaped into (batch, window=60, 1) windows before being handed to either model — " +
          "see WindowedSeriesDataset in lstm_pytorch_model.py and the TimeseriesGenerator call in lstm_model.py."
        }
      />

      <ConceptSection
        title="2. Neural Network Building"
        description="PyTorch defines models as classes subclassing nn.Module, with an explicit forward() method. tf.keras favors a declarative Sequential/Functional API, though it also supports subclassing."
        pytorchCode={`class LSTMForecaster(nn.Module):
    def __init__(self):
        super().__init__()
        self.lstm1 = nn.LSTM(1, 100, batch_first=True)
        self.lstm2 = nn.LSTM(100, 50, batch_first=True)
        self.lstm3 = nn.LSTM(50, 10, batch_first=True)
        self.dense1 = nn.Linear(10, 64)
        self.dense2 = nn.Linear(64, 32)
        self.output = nn.Linear(32, 1)

    def forward(self, x):
        x, _ = self.lstm1(x)
        x, _ = self.lstm2(x)
        _, (h, _) = self.lstm3(x)
        x = torch.relu(self.dense1(h[-1]))
        x = torch.relu(self.dense2(x))
        return self.output(x)`}
        tensorflowCode={`model = tf.keras.models.Sequential([
    tf.keras.layers.LSTM(100, input_shape=(60, 1),
                          return_sequences=True),
    tf.keras.layers.LSTM(50, return_sequences=True),
    tf.keras.layers.LSTM(10),
    tf.keras.layers.Dense(64, activation="relu"),
    tf.keras.layers.Dense(32, activation="relu"),
    tf.keras.layers.Dense(1),
])
model.compile(loss="mse", optimizer="adam")`}
        projectNote="The two model definitions in this project (LSTMForecaster and build_model()) are built to the exact same architecture — 3 stacked LSTM layers (100→50→10 units) plus Dense(64)→Dense(32)→Dense(1) — for a fair comparison in the Compare All view."
      />

      <ConceptSection
        title="3. Training and Backpropagation (SGD, Adam)"
        description="PyTorch requires a manual training loop: forward pass, compute loss, loss.backward() to compute gradients, optimizer.step() to update weights, and zero_grad() to reset gradients. tf.keras's model.fit() runs this loop internally."
        pytorchCode={`optimizer = torch.optim.Adam(model.parameters())
# or: torch.optim.SGD(model.parameters(), lr=0.01)
criterion = nn.MSELoss()

for epoch in range(epochs):
    for x_batch, y_batch in loader:
        optimizer.zero_grad()
        prediction = model(x_batch)
        loss = criterion(prediction, y_batch)
        loss.backward()          # backprop
        optimizer.step()`}
        tensorflowCode={`model.compile(
    loss="mse",
    optimizer="adam",   # or tf.keras.optimizers.SGD(0.01)
)
history = model.fit(train_generator, epochs=epochs)
# backprop happens inside .fit()`}
        projectNote="lstm_pytorch_model.py's train_model() contains the explicit loop above with Adam + MSELoss; lstm_model.py's train_model() calls model.fit() with the equivalent adam/mse configuration."
      />

      <ConceptSection
        title="4. Data Handling (Loading, Shuffling, Batching)"
        description="PyTorch's Dataset + DataLoader classes define how to fetch and batch samples. TensorFlow's tf.data.Dataset (or, for sequences specifically, Keras's TimeseriesGenerator) plays the same role."
        pytorchCode={`class WindowedSeriesDataset(Dataset):
    def __init__(self, series_scaled, window_size=60):
        self.series = torch.tensor(series_scaled, dtype=torch.float32)
        self.window_size = window_size

    def __len__(self):
        return len(self.series) - self.window_size

    def __getitem__(self, idx):
        x = self.series[idx : idx + self.window_size]
        y = self.series[idx + self.window_size]
        return x, y

loader = DataLoader(dataset, batch_size=1, shuffle=False)`}
        tensorflowCode={`from tensorflow.keras.preprocessing.sequence import TimeseriesGenerator

train_generator = TimeseriesGenerator(
    train_scaled, train_scaled,
    length=60, batch_size=1,
)
# general tf.data.Dataset equivalent:
ds = tf.data.Dataset.from_tensor_slices(train_scaled)
ds = ds.window(60, shift=1).batch(60).shuffle(1000)`}
        projectNote="Both produce the exact same rolling (60-step window → next value) training pairs for this dataset — see WindowedSeriesDataset in lstm_pytorch_model.py vs. TimeseriesGenerator in lstm_model.py."
      />

      <ConceptSection
        title="5. Transfer Learning"
        description="Both frameworks let you load a pre-trained model, freeze most layers, and fine-tune the rest on a new task — commonly used for image classification with ImageNet-pretrained backbones."
        usedInProject={false}
        pytorchCode={`from torchvision import models

backbone = models.resnet18(weights="IMAGENET1K_V1")
for param in backbone.parameters():
    param.requires_grad = False   # freeze

backbone.fc = nn.Linear(backbone.fc.in_features, num_classes)
# only backbone.fc trains now`}
        tensorflowCode={`base = tf.keras.applications.ResNet50(
    weights="imagenet", include_top=False)
base.trainable = False            # freeze

model = tf.keras.Sequential([
    base,
    tf.keras.layers.GlobalAveragePooling2D(),
    tf.keras.layers.Dense(num_classes, activation="softmax"),
])`}
        projectNote="Not used in this project — the Bombay temperature series is a single-source time-series regression problem with no pretrained backbone to transfer from. Shown here as a general reference for the framework comparison."
      />

      <ConceptSection
        title="6. Regularization (Dropout, Weight Decay, Early Stopping)"
        description="Dropout randomly zeroes activations during training; weight decay (L2 penalty) is often built into the optimizer; early stopping halts training once validation performance stops improving."
        pytorchCode={`self.dropout = nn.Dropout(p=0.2)   # in forward(): x = self.dropout(x)

optimizer = torch.optim.Adam(
    model.parameters(), weight_decay=1e-5)

# early stopping is typically hand-rolled:
if val_loss < best_val_loss:
    best_val_loss = val_loss
    patience_counter = 0
else:
    patience_counter += 1
    if patience_counter >= patience:
        break`}
        tensorflowCode={`tf.keras.layers.Dropout(0.2)   # inserted between layers

tf.keras.optimizers.Adam(weight_decay=1e-5)

early_stop = tf.keras.callbacks.EarlyStopping(
    monitor="val_loss", patience=3,
    restore_best_weights=True)
model.fit(x, y, callbacks=[early_stop])`}
        projectNote="This project's LSTM models keep the notebook's original architecture unchanged (no dropout/weight decay/early stopping were in the source notebook), so neither is applied here — shown as general reference for both frameworks' APIs. Both models do use a ModelCheckpoint/best-loss save (see topic 9) as a lightweight related technique."
      />

      <ConceptSection
        title="7. Model Evaluation (MSE, RMSE, Loss/Accuracy Curves)"
        description="Regression models here are evaluated with MSE and RMSE on held-out test data. Both frameworks compute these the same way once you have prediction and ground-truth arrays."
        pytorchCode={`predictions = model(x_test).detach().numpy()
mse = ((predictions - y_test) ** 2).mean()
rmse = mse ** 0.5

# Training loss is collected manually per epoch (see topic 3):
plt.plot(losses)`}
        tensorflowCode={`predictions = model.predict(x_test)
mse = ((predictions - y_test) ** 2).mean()
rmse = mse ** 0.5

# history.history["loss"] is collected automatically by .fit():
plt.plot(history.history["loss"])`}
        projectNote='Every model in this dashboard reports MSE/RMSE on the 2010-2012 test period (see the "RMSE" metric card on each model page and the Compare All table) — computed identically in evaluate() in both lstm_model.py and lstm_pytorch_model.py, and in sarimax_model.py.'
      />

      <ConceptSection
        title="8. Hyperparameter Tuning (Grid Search, Random Search)"
        description="Searching over hyperparameters (learning rate, layer sizes, ARIMA orders, etc.) to find the best-performing configuration. statsmodels' ecosystem includes purpose-built search for ARIMA orders; general grid/random search works the same way in either DL framework since both just take Python parameters."
        pytorchCode={`from itertools import product

best = None
for lr, hidden in product([1e-2, 1e-3], [32, 64]):
    model = build_model(hidden)
    optimizer = torch.optim.Adam(model.parameters(), lr=lr)
    val_rmse = train_and_evaluate(model, optimizer)
    if best is None or val_rmse < best[0]:
        best = (val_rmse, lr, hidden)`}
        tensorflowCode={`import keras_tuner as kt

def build(hp):
    model = tf.keras.Sequential([...])
    model.compile(optimizer=tf.keras.optimizers.Adam(
        hp.Choice("lr", [1e-2, 1e-3])))
    return model

tuner = kt.RandomSearch(build, objective="val_loss")
tuner.search(x, y, epochs=10)`}
        projectNote="This project's ARIMA model uses pmdarima's auto_arima (a purpose-built stepwise/grid search over (p,d,q)(P,D,Q,m) orders) rather than a generic grid search — see run_auto_arima() in arima_model.py. The two SARIMAX models' orders were selected this way in the original notebook and kept fixed here rather than re-searched on every run."
      />

      <ConceptSection
        title="9. Saving and Loading Models"
        description="PyTorch typically saves a model's state_dict (learned weights only); TensorFlow/Keras can save the full model (architecture + weights + optimizer state) in one file."
        pytorchCode={`torch.save(model.state_dict(), "model.pt")

# later, for inference:
model = LSTMForecaster()
model.load_state_dict(torch.load("model.pt"))
model.eval()`}
        tensorflowCode={`model.save("model.keras")

# later, for inference:
from tensorflow.keras.models import load_model
model = load_model("model.keras")`}
        projectNote={
          "This project saves the best-loss checkpoint during training for both frameworks: " +
          "TemperatureForecastingModel.keras (Keras's ModelCheckpoint callback) and " +
          'TemperatureForecastingModel_pytorch.pt (a manual "save if epoch_loss improved" check ' +
          "in lstm_pytorch_model.py, replicating save_best_only=True)."
        }
      />

      <ConceptSection
        title="10. Deep Learning Models — CNNs & RNNs/LSTMs"
        description="CNNs use convolutional layers for grid-like data (images); RNNs/LSTMs process sequential data by carrying a hidden state across time steps — the right family for time series like this project's temperature data."
        pytorchCode={`# LSTM (used in this project):
nn.LSTM(input_size=1, hidden_size=100, batch_first=True)

# CNN (general reference, not used here):
nn.Conv2d(in_channels=3, out_channels=32, kernel_size=3)
nn.MaxPool2d(kernel_size=2)`}
        tensorflowCode={`# LSTM (used in this project):
tf.keras.layers.LSTM(100, return_sequences=True)

# CNN (general reference, not used here):
tf.keras.layers.Conv2D(32, kernel_size=3, activation="relu")
tf.keras.layers.MaxPooling2D(pool_size=2)`}
        projectNote="Both LSTM models on this dashboard use 3 stacked LSTM layers to capture temporal dependencies in the monthly temperature series — this is the core deep-learning model of the project. CNN layers are shown only for framework-comparison completeness; there's no image data here."
      />

      <ConceptSection
        title="11. Visualization (Predicted vs. Actual, Loss Curves, Confusion Matrices)"
        description="Both ecosystems typically hand off to matplotlib for plotting once you have NumPy arrays — the framework differences mostly disappear at this stage."
        pytorchCode={`import matplotlib.pyplot as plt

plt.plot(y_test, label="Observed")
plt.plot(predictions, label="Forecast", linestyle="--")
plt.legend(); plt.show()

# classification-only, general reference:
from sklearn.metrics import ConfusionMatrixDisplay
ConfusionMatrixDisplay.from_predictions(y_true, y_pred)`}
        tensorflowCode={`import matplotlib.pyplot as plt

plt.plot(history.history["loss"], label="Loss")
plt.plot(y_test, label="Observed")
plt.plot(predictions, label="Forecast", linestyle="--")
plt.legend(); plt.show()`}
        projectNote="This dashboard replaces the notebook's static matplotlib plt.savefig() images with live, interactive Recharts charts (ForecastChart, TrainingLossChart, EdaSection) driven by the same underlying series data returned by the API. Confusion matrices don't apply here since this is a regression, not classification, task — shown for completeness."
      />

      <div className="takeaway-banner">
        <strong>The takeaway:</strong> understanding the trade-offs between
        frameworks like TensorFlow and PyTorch is not just a technical
        decision — it's a business lever. It shapes how quickly teams can
        experiment, how reliably they can deploy, and how effectively they
        can translate data into decisions.
      </div>
    </div>
  );
}
