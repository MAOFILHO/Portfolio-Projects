"""LSTM neural network model: scaling, windowing, training, and iterative forecasting.

Converted from notebook cells 99, 101, 105, 107, 111, 113, 115, 118, 120, 122, 124
(execution order 43-53).
"""
from __future__ import annotations

import logging
import random as rd
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import tensorflow as tf
from sklearn.preprocessing import StandardScaler
from tensorflow.keras.callbacks import ModelCheckpoint
from tensorflow.keras.models import load_model
from tensorflow.keras.preprocessing.sequence import TimeseriesGenerator

from .series_utils import series_to_points

logger = logging.getLogger(__name__)

WINDOW_SIZE = 60


def scale_training_data(train: pd.Series) -> tuple[StandardScaler, np.ndarray]:
    scaler = StandardScaler()
    train_scaled = scaler.fit_transform(np.array(train).reshape(-1, 1))
    return scaler, train_scaled


def build_model() -> tf.keras.Model:
    model = tf.keras.models.Sequential(
        [
            tf.keras.layers.LSTM(100, input_shape=(WINDOW_SIZE, 1), return_sequences=True),
            tf.keras.layers.LSTM(50, return_sequences=True),
            tf.keras.layers.LSTM(10),
            tf.keras.layers.Dense(64, activation="relu"),
            tf.keras.layers.Dense(32, activation="relu"),
            tf.keras.layers.Dense(1),
        ]
    )
    model.compile(loss="mse", optimizer="adam")
    return model


def train_model(
    train_scaled: np.ndarray, model_path: Path, output_dir: Path, epochs: int = 10
) -> tuple[tf.keras.Model, dict]:
    train_generator = TimeseriesGenerator(
        train_scaled, train_scaled, length=WINDOW_SIZE, batch_size=1
    )

    model = build_model()
    logger.info("LSTM model summary:\n%s", model.summary())

    model_path.parent.mkdir(parents=True, exist_ok=True)
    checkpoint = ModelCheckpoint(str(model_path), monitor="loss", save_best_only=True)

    # Reproducibility, matching the notebook's fixed seeds exactly.
    rd.seed(10)
    np.random.seed(150)
    tf.random.set_seed(150)

    history = model.fit(train_generator, epochs=epochs, callbacks=[checkpoint])

    plt.plot(history.history["loss"])
    plt.xlabel("Epochs", fontsize=13)
    plt.ylabel("Loss", fontsize=13)
    plt.legend(["Loss"])
    plt.title("Training Loss", fontsize=15)
    plt.savefig(output_dir / "lstm_training_loss.png")
    plt.close()

    return model, {"loss": [float(x) for x in history.history["loss"]]}


def forecast(
    model: tf.keras.Model,
    scaler: StandardScaler,
    train_scaled: np.ndarray,
    test: pd.Series,
) -> pd.DataFrame:
    lstm_predictions_scaled = []
    batch = train_scaled[-WINDOW_SIZE:]
    current_batch = batch.reshape((1, WINDOW_SIZE, 1))

    for _ in range(len(test)):
        lstm_pred = model.predict(current_batch, verbose=0)[0]
        lstm_predictions_scaled.append(lstm_pred)
        current_batch = np.append(current_batch[:, 1:, :], [[lstm_pred]], axis=1)

    lstm_predictions = scaler.inverse_transform(lstm_predictions_scaled)
    lstm_preds = pd.DataFrame(
        data=[lstm_predictions[i][0] for i in range(len(lstm_predictions))],
        columns=["LSTM Forecast"],
    ).set_index(test.index)
    return lstm_preds


def evaluate(lstm_preds: pd.DataFrame, test: pd.Series) -> dict:
    y_forecasted = lstm_preds["LSTM Forecast"]
    mse = ((y_forecasted - test) ** 2).mean()
    rmse = float(np.sqrt(mse))
    return {"mse": float(mse), "rmse": rmse}


def plot_forecast(y: pd.Series, lstm_preds: pd.DataFrame, output_dir: Path) -> None:
    ax3 = y["2000":].plot(label="Observed")
    ax3.fill_between(
        y["2010":].index, [22 for _ in y["2010":]], [36 for _ in y["2010":]], color="k", alpha=0.2
    )
    lstm_preds.plot(ax=ax3, label="LSTM Forecast", figsize=(15, 6), linewidth=2, linestyle="dashed")
    ax3.set_xlabel("Date")
    ax3.set_ylabel("Average Temperature")
    plt.legend()
    plt.savefig(output_dir / "lstm_forecast.png")
    plt.close()


def run_lstm(
    train: pd.Series,
    test: pd.Series,
    y: pd.Series,
    model_path: Path,
    output_dir: Path,
    epochs: int = 10,
    retrain: bool = True,
) -> dict:
    """Train (or reload) the LSTM model and produce a rolling forecast over the test period."""
    scaler, train_scaled = scale_training_data(train)

    if retrain or not model_path.exists():
        _, history = train_model(train_scaled, model_path, output_dir, epochs=epochs)
    else:
        history = {"loss": []}

    model = load_model(str(model_path))

    lstm_preds = forecast(model, scaler, train_scaled, test)
    plot_forecast(y, lstm_preds, output_dir)
    metrics = evaluate(lstm_preds, test)

    return {
        "forecast": series_to_points(lstm_preds["LSTM Forecast"]),
        "metrics": metrics,
        "training_loss": history["loss"],
    }
