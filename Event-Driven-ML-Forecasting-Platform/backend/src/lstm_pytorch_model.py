"""LSTM neural network model — PyTorch implementation.

Mirrors lstm_model.py (TensorFlow/Keras) exactly in architecture and
hyperparameters (3 stacked LSTM layers 100->50->10, Dense 64->32->1, window
size 60, 10 epochs, Adam/MSE), using PyTorch idioms (torch.nn.Module,
Dataset/DataLoader, manual training loop) so the two can be compared fairly
in the dashboard. There is no notebook cell equivalent for this module -- it
was added to showcase PyTorch alongside the original TensorFlow model.
"""
from __future__ import annotations

import logging
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import torch
from sklearn.preprocessing import StandardScaler
from torch import nn
from torch.utils.data import DataLoader, Dataset

from .series_utils import series_to_points

logger = logging.getLogger(__name__)

WINDOW_SIZE = 60


class WindowedSeriesDataset(Dataset):
    """Produces the same rolling (window -> next value) pairs as Keras's
    TimeseriesGenerator, via PyTorch's Dataset/DataLoader API."""

    def __init__(self, series_scaled: np.ndarray, window_size: int = WINDOW_SIZE):
        self.series = torch.tensor(series_scaled, dtype=torch.float32)
        self.window_size = window_size

    def __len__(self) -> int:
        return len(self.series) - self.window_size

    def __getitem__(self, idx: int):
        x = self.series[idx : idx + self.window_size]
        y = self.series[idx + self.window_size]
        return x, y


class LSTMForecaster(nn.Module):
    """Same shape as the Keras Sequential model in lstm_model.py:
    LSTM(100, return_sequences) -> LSTM(50, return_sequences) -> LSTM(10)
    -> Dense(64, relu) -> Dense(32, relu) -> Dense(1)."""

    def __init__(self):
        super().__init__()
        self.lstm1 = nn.LSTM(input_size=1, hidden_size=100, batch_first=True)
        self.lstm2 = nn.LSTM(input_size=100, hidden_size=50, batch_first=True)
        self.lstm3 = nn.LSTM(input_size=50, hidden_size=10, batch_first=True)
        self.dense1 = nn.Linear(10, 64)
        self.dense2 = nn.Linear(64, 32)
        self.output = nn.Linear(32, 1)
        self.relu = nn.ReLU()

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x, _ = self.lstm1(x)
        x, _ = self.lstm2(x)
        _, (hidden, _) = self.lstm3(x)
        x = hidden[-1]  # last layer's final hidden state, i.e. return_sequences=False
        x = self.relu(self.dense1(x))
        x = self.relu(self.dense2(x))
        return self.output(x)


def scale_training_data(train: pd.Series) -> tuple[StandardScaler, np.ndarray]:
    scaler = StandardScaler()
    train_scaled = scaler.fit_transform(np.array(train).reshape(-1, 1))
    return scaler, train_scaled


def build_model() -> LSTMForecaster:
    return LSTMForecaster()


def train_model(
    train_scaled: np.ndarray, model_path: Path, output_dir: Path, epochs: int = 10
) -> tuple[LSTMForecaster, dict]:
    dataset = WindowedSeriesDataset(train_scaled)
    loader = DataLoader(dataset, batch_size=1, shuffle=False)

    model = build_model()
    logger.info("PyTorch LSTM model: %s", model)

    optimizer = torch.optim.Adam(model.parameters())
    criterion = nn.MSELoss()

    # Reproducibility, matching the notebook's TF seeds' intent for the PyTorch run.
    torch.manual_seed(150)
    np.random.seed(150)

    losses = []
    best_loss = float("inf")
    model_path.parent.mkdir(parents=True, exist_ok=True)

    for epoch in range(epochs):
        model.train()
        epoch_loss = 0.0
        for x_batch, y_batch in loader:
            optimizer.zero_grad()
            prediction = model(x_batch)
            loss = criterion(prediction, y_batch)
            loss.backward()
            optimizer.step()
            epoch_loss += loss.item()
        epoch_loss /= len(loader)
        losses.append(epoch_loss)
        logger.info("Epoch %d/%d - loss: %.4f", epoch + 1, epochs, epoch_loss)

        # save_best_only=True equivalent, matching the Keras ModelCheckpoint behaviour.
        if epoch_loss < best_loss:
            best_loss = epoch_loss
            torch.save(model.state_dict(), model_path)

    plt.plot(losses)
    plt.xlabel("Epochs", fontsize=13)
    plt.ylabel("Loss", fontsize=13)
    plt.legend(["Loss"])
    plt.title("Training Loss (PyTorch)", fontsize=15)
    plt.savefig(output_dir / "lstm_pytorch_training_loss.png")
    plt.close()

    return model, {"loss": losses}


def load_trained_model(model_path: Path) -> LSTMForecaster:
    model = build_model()
    model.load_state_dict(torch.load(model_path, weights_only=True))
    model.eval()
    return model


def forecast(
    model: LSTMForecaster,
    scaler: StandardScaler,
    train_scaled: np.ndarray,
    test: pd.Series,
) -> pd.DataFrame:
    model.eval()
    lstm_predictions_scaled = []
    batch = train_scaled[-WINDOW_SIZE:]
    current_batch = batch.reshape(1, WINDOW_SIZE, 1)

    with torch.no_grad():
        for _ in range(len(test)):
            x = torch.tensor(current_batch, dtype=torch.float32)
            lstm_pred = model(x).numpy()[0]
            lstm_predictions_scaled.append(lstm_pred)
            current_batch = np.append(current_batch[:, 1:, :], [[lstm_pred]], axis=1)

    lstm_predictions = scaler.inverse_transform(lstm_predictions_scaled)
    lstm_preds = pd.DataFrame(
        data=[lstm_predictions[i][0] for i in range(len(lstm_predictions))],
        columns=["LSTM Forecast (PyTorch)"],
    ).set_index(test.index)
    return lstm_preds


def evaluate(lstm_preds: pd.DataFrame, test: pd.Series) -> dict:
    y_forecasted = lstm_preds["LSTM Forecast (PyTorch)"]
    mse = ((y_forecasted - test) ** 2).mean()
    rmse = float(np.sqrt(mse))
    return {"mse": float(mse), "rmse": rmse}


def plot_forecast(y: pd.Series, lstm_preds: pd.DataFrame, output_dir: Path) -> None:
    ax3 = y["2000":].plot(label="Observed")
    ax3.fill_between(
        y["2010":].index, [22 for _ in y["2010":]], [36 for _ in y["2010":]], color="k", alpha=0.2
    )
    lstm_preds.plot(
        ax=ax3, label="LSTM Forecast (PyTorch)", figsize=(15, 6), linewidth=2, linestyle="dashed"
    )
    ax3.set_xlabel("Date")
    ax3.set_ylabel("Average Temperature")
    plt.legend()
    plt.savefig(output_dir / "lstm_pytorch_forecast.png")
    plt.close()


def run_lstm_pytorch(
    train: pd.Series,
    test: pd.Series,
    y: pd.Series,
    model_path: Path,
    output_dir: Path,
    epochs: int = 10,
    retrain: bool = True,
) -> dict:
    """Train (or reload) the PyTorch LSTM model and produce a rolling forecast over the test period."""
    scaler, train_scaled = scale_training_data(train)

    if retrain or not model_path.exists():
        _, history = train_model(train_scaled, model_path, output_dir, epochs=epochs)
    else:
        history = {"loss": []}

    model = load_trained_model(model_path)

    lstm_preds = forecast(model, scaler, train_scaled, test)
    plot_forecast(y, lstm_preds, output_dir)
    metrics = evaluate(lstm_preds, test)

    return {
        "forecast": series_to_points(lstm_preds["LSTM Forecast (PyTorch)"]),
        "metrics": metrics,
        "training_loss": history["loss"],
    }
