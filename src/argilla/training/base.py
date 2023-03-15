#  Copyright 2021-present, the Recognai S.L. team.
#
#  Licensed under the Apache License, Version 2.0 (the "License");
#  you may not use this file except in compliance with the License.
#  You may obtain a copy of the License at
#
#      http://www.apache.org/licenses/LICENSE-2.0
#
#  Unless required by applicable law or agreed to in writing, software
#  distributed under the License is distributed on an "AS IS" BASIS,
#  WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#  See the License for the specific language governing permissions and
#  limitations under the License.

import inspect
import logging
from typing import List, Union

import argilla as rg
from argilla.training.setfit import ArgillaSetFitTrainer


class ArgillaBaseTrainer(object):
    _logger = logging.getLogger("argilla.training")

    def __init__(self, name: str, framework: str, train_size: float = None, seed: int = None, **load_kwargs):
        """
        `__init__` is a function that initializes the class

        Args:
          name (str): the name of the dataset you want to load.
          framework (str): the framework to use for training. Currently, only "setfit" is supported.
          query (str): a query to filter the dataset.
          train_size (float): the size of the training set. If not specified, the entire dataset will be
        used for training.
          seed (int): int = None,
        """
        self.device = "cpu"

        self._name = name
        self._multi_label = False
        self._split_applied = False
        self._seed = seed

        if train_size:
            self._train_size = train_size
            self._split_applied = True

        self.rg_dataset_snapshot = rg.load(name=self._name, limit=1)
        assert len(self.rg_dataset_snapshot) > 0, "Dataset must have at least one Validated record"
        if isinstance(self.rg_dataset_snapshot, rg.DatasetForTextClassification):
            self._rg_dataset_type = rg.DatasetForTextClassification
            self._required_fields = ["id", "text", "inputs", "annotation"]
            if self.rg_dataset_snapshot[0].multi_label:
                self._multi_label = True
        elif isinstance(self.rg_dataset_snapshot, rg.DatasetForTokenClassification):
            self._rg_dataset_type = rg.DatasetForTokenClassification
            self._required_fields = ["id", "text", "tokens", "ner_tags"]

        elif isinstance(self.rg_dataset_snapshot, rg.DatasetForText2Text):
            self._rg_dataset_type = rg.DatasetForText2Text
            self._required_fields = ["id", "text", "annotation"]
        else:
            raise NotImplementedError(f"Dataset type {type(self.rg_dataset_snapshot)} is not supported.")

        self.dataset_full = rg.load(name=self._name, fields=self._required_fields, **load_kwargs)
        self.dataset_full_prepared = self.dataset_full.prepare_for_training(
            framework=framework, train_size=self._train_size, seed=self._seed
        )
        if framework in ["transformers", "setfit"]:
            import torch

            if torch.backends.mps.is_available():
                self.device = "mps"
            elif torch.cuda.is_available():
                self.device = "cuda"
            else:
                self.device = "cpu"

        if framework == "setfit":
            assert self._rg_dataset_type == rg.DatasetForTextClassification, "SetFit supports only text classification"
            self._trainer = ArgillaSetFitTrainer(
                record_class=self._rg_dataset_type._RECORD_TYPE,
                dataset=self.dataset_full_prepared,
                multi_label=self._multi_label,
                device=self.device,
                seed=self._seed,
            )
        else:
            raise NotImplementedError(f"Framework {framework} is not supported")
        self._logger.error(self)

    def __repr__(self) -> str:
        """
        `trainer.__repr__()` prints out the trainer's parameters and a summary of how to use the trainer

        Returns:
          The trainer object.
        """
        return inspect.cleandoc(
            f"""
            ArgillaBaseTrainer info:
            _________________________________________________________________
            These baseline params are fixed:
                dataset: {self._name}
                task: {self._rg_dataset_type.__name__}
                multi_label: {self._multi_label}
                required_fields: {self._required_fields}
                train_size: {self._train_size}

            {self._trainer.__class__} info:
            _________________________________________________________________
            The parameters are configurable via `trainer.update_config()`:
                {self._trainer}

            Using the trainer:
            _________________________________________________________________
            `trainer.train(path)` to train to start training. `path` is the path to save the model automatically.
            `trainer.predict(text, as_argilla_records=True)` to make predictions.
            `trainer.save(path)` to save the model manually."""
        )

    def update_config(self, *args, **kwargs):
        """
        It updates the configuration of the trainer, but the parameters depend on the trainer.subclass.
        """
        self._trainer.update_config(*args, **kwargs)

    def predict(self, text: Union[List[str], str], as_argilla_records: bool = True):
        """
        `predict` takes a string or list of strings and returns a list of dictionaries, each dictionary
        containing the text, the predicted label, and the confidence score

        Args:
          text (Union[List[str], str]): The text to be classified.
          as_argilla_records (bool): If True, the output will be a list of ArgillaRecord objects. If
        True, the output will be a list of Argilla records. Defaults to True.

        Returns:
          A list of predictions or argilla records.
        """
        return self._trainer.predict(text, as_argilla_records)

    def train(self, path: str = None):
        """
        > The function `train` takes in a path to a file and trains the model. If a path is provided,
        the model is saved to that path

        Args:
          path (str): The path to the model file.
        """
        self._trainer.train()
        if path is not None:
            self._trainer.save(path)

    def save(self, path: str):
        """
        It saves the model to the path specified

        Args:
          path (str): The path to the directory where the model will be saved.
        """
        self._trainer.save(path)
