# Standard library
from pathlib import Path

# Third-party
import pytest
import pytorch_lightning as pl
import torch
import wandb

# First-party
from neural_lam.datastore import DATASTORES
from neural_lam.datastore.base import BaseRegularGridDatastore
from neural_lam.models.graph_lam import GraphLAM
from neural_lam.weather_dataset import WeatherDataModule
from tests.conftest import init_datastore_example


@pytest.mark.parametrize("datastore_name", DATASTORES.keys())
def test_training(datastore_name):
    datastore = init_datastore_example(datastore_name)

    if not isinstance(datastore, BaseRegularGridDatastore):
        pytest.skip(
            f"Skipping test for {datastore_name} as it is not a regular "
            "grid datastore."
        )

    if torch.cuda.is_available():
        device_name = "cuda"
        torch.set_float32_matmul_precision(
            "high"
        )  # Allows using Tensor Cores on A100s
    else:
        device_name = "cpu"

    trainer = pl.Trainer(
        max_epochs=1,
        deterministic=True,
        accelerator=device_name,
        # XXX: `devices` has to be set to 2 otherwise
        # neural_lam.models.ar_model.ARModel.aggregate_and_plot_metrics fails
        # because it expects to aggregate over multiple devices
        devices=2,
        log_every_n_steps=1,
    )

    graph_name = "1level"

    data_module = WeatherDataModule(
        datastore=datastore,
        ar_steps_train=3,
        ar_steps_eval=5,
        standardize=True,
        batch_size=2,
        num_workers=1,
        forcing_window_size=3,
    )

    class ModelArgs:
        output_std = False
        loss = "mse"
        restore_opt = False
        n_example_pred = 1
        # XXX: this should be superfluous when we have already defined the
        # model object no?
        graph = graph_name
        hidden_dim = 8
        hidden_layers = 1
        processor_layers = 4
        mesh_aggr = "sum"
        lr = 1.0e-3
        val_steps_to_log = [1, 3]
        metrics_watch = []
        forcing_window_size = 3

    model_args = ModelArgs()

    model = GraphLAM(  # noqa
        args=model_args,
        datastore=datastore,
    )
    wandb.init()
    trainer.fit(model=model, datamodule=data_module)
