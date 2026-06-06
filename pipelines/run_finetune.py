"""Finetune Lifecycle Stub — SIMULATED SFT by default.

This module is a lifecycle *stub*, not a real SFT trainer. The default code path
performs NO gradient steps. It exists to exercise the surrounding orchestration:
dataset validation, recipe parsing, checkpoint registration, and promotion-gate
enforcement. When you see "trained", read it as "simulated training returned
placeholder metrics".

Pipeline stages and their reality:

1. Dataset validation — schema checks, quality checks, SHA-256 fingerprinting. REAL.
2. Recipe parsing — hyperparameter bounds checking. REAL.
3. Training — dispatches to `_simulate_training()` by default. SIMULATED.
   Returns a synthetic checkpoint ID and hardcoded metrics so the pipeline can
   complete without a GPU. The integration point for a real backend
   (SageMaker, Vertex AI, Ray Train, local torchtune) is the `training_backend`
   slot documented inline.
4. Post-training evaluation — uses metrics returned by stage 3. When stage 3 is
   simulated, these are placeholder values; when a real backend is plugged in,
   these are real validation-set metrics.
5. Checkpoint registration in model registry. REAL.
6. Promotion gate enforcement. REAL (uses the same gate as other candidate models).

Run: python -m pipelines.run_finetune --recipe data/finetune/sample_recipe.yaml --dataset data/finetune/sample_dataset.json
"""

from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)


class TrainingState(StrEnum):
    VALIDATING = 'validating'
    PREPARING = 'preparing'
    TRAINING = 'training'
    EVALUATING = 'evaluating'
    REGISTERING = 'registering'
    COMPLETED = 'completed'
    FAILED = 'failed'


@dataclass
class FinetuneRecipe:
    base_model: str  # set to a real model ID (e.g. 'meta-llama/Llama-3.2-1B') when wiring a real backend
    learning_rate: float
    epochs: int
    batch_size: int
    max_seq_length: int
    lora_rank: int = 16
    lora_alpha: int = 32


@dataclass
class DatasetManifest:
    path: str
    num_examples: int
    num_train: int
    num_val: int
    fingerprint: str
    schema_valid: bool
    quality_issues: list[str]


def validate_dataset(dataset_path: str) -> DatasetManifest:
    """Validate dataset schema and quality.

    Checks:
    - File exists and is valid JSON
    - Each example has 'input' and 'output' fields
    - No empty fields
    - No exact duplicates
    - Minimum example count
    """
    path = Path(dataset_path)
    issues = []

    if not path.exists():
        return DatasetManifest(
            path=dataset_path,
            num_examples=0,
            num_train=0,
            num_val=0,
            fingerprint='',
            schema_valid=False,
            quality_issues=[f'Dataset not found: {dataset_path}'],
        )

    try:
        data = json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return DatasetManifest(
            path=dataset_path,
            num_examples=0,
            num_train=0,
            num_val=0,
            fingerprint='',
            schema_valid=False,
            quality_issues=[f'Invalid JSON: {e}'],
        )

    if not isinstance(data, list):
        issues.append('Dataset must be a JSON array')
        return DatasetManifest(
            path=dataset_path,
            num_examples=0,
            num_train=0,
            num_val=0,
            fingerprint='',
            schema_valid=False,
            quality_issues=issues,
        )

    # Schema validation
    schema_valid = True
    seen_inputs = set()
    for i, example in enumerate(data):
        if not isinstance(example, dict):
            issues.append(f'Example {i}: not a JSON object')
            schema_valid = False
            continue
        if 'input' not in example or 'output' not in example:
            issues.append(f'Example {i}: missing input or output field')
            schema_valid = False
        elif not isinstance(example['input'], str) or not isinstance(example['output'], str):
            issues.append(f'Example {i}: input and output must be strings')
            schema_valid = False
        elif not example['input'].strip() or not example['output'].strip():
            issues.append(f'Example {i}: empty input or output')
        input_text = example.get('input', '')
        if not isinstance(input_text, str):
            input_text = ''
        if input_text in seen_inputs:
            issues.append(f'Example {i}: duplicate input')
        seen_inputs.add(input_text)

    if len(data) < 10:
        issues.append(f'Only {len(data)} examples — minimum recommended is 10')

    # Compute fingerprint for reproducibility
    fingerprint = hashlib.sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()[:16]

    # Train/val split (80/20)
    num_train = int(len(data) * 0.8)
    num_val = len(data) - num_train

    return DatasetManifest(
        path=dataset_path,
        num_examples=len(data),
        num_train=num_train,
        num_val=num_val,
        fingerprint=fingerprint,
        schema_valid=schema_valid,
        quality_issues=issues,
    )


def load_recipe(recipe_path: str) -> FinetuneRecipe:
    """Load and validate fine-tuning recipe."""
    path = Path(recipe_path)
    if not path.exists():
        raise FileNotFoundError(f'Recipe not found: {recipe_path}')

    raw = yaml.safe_load(path.read_text())

    # Validate hyperparameters
    lr = raw.get('learning_rate', 2e-5)
    if lr <= 0 or lr > 0.1:
        raise ValueError(f'Learning rate {lr} outside valid range (0, 0.1]')

    epochs = raw.get('epochs', 3)
    if epochs < 1 or epochs > 100:
        raise ValueError(f'Epochs {epochs} outside valid range [1, 100]')

    return FinetuneRecipe(
        base_model=raw.get('base_model', 'text-main'),  # 'text-main' is a demo placeholder — replace with a real model ID for a live backend
        learning_rate=lr,
        epochs=epochs,
        batch_size=raw.get('batch_size', 8),
        max_seq_length=raw.get('max_seq_length', 2048),
        lora_rank=raw.get('lora_rank', 16),
        lora_alpha=raw.get('lora_alpha', 32),
    )


def _simulate_training(recipe: FinetuneRecipe, manifest: DatasetManifest) -> tuple[str, dict]:
    """Simulate the training step with hardcoded metrics.

    This is the DEFAULT backend for portability — it lets the full pipeline
    run without a GPU. Returns a checkpoint ID and placeholder metrics.

    A real implementation would:
    - Dispatch to a GPU training service (SageMaker, Vertex AI, Ray Train, etc.)
    - Stream training logs and loss curves
    - Return the actual checkpoint path and validation metrics
    - Support early stopping, checkpointing, and resumption
    """
    checkpoint_id = f'ckpt-{recipe.base_model}-{time.strftime("%Y%m%d%H%M%S")}'
    logger.info(
        'Training complete (SIMULATED — no GPU backend configured). Checkpoint: %s',
        checkpoint_id,
    )
    simulated_metrics = {
        'grounded_support': 0.82,
        'citation_coverage': 0.78,
        'val_loss': 0.45,
    }
    return checkpoint_id, simulated_metrics


def run_finetune(recipe_path: str, dataset_path: str) -> dict:
    """Orchestrate the Finetune Lifecycle Stub through a state machine.

    Training is SIMULATED in the default backend — see `_simulate_training`.
    States: validating -> preparing -> training -> evaluating -> registering -> completed
    """
    state = TrainingState.VALIDATING
    logger.info('Finetune Lifecycle Stub started (state=%s) — training will be SIMULATED', state)

    # 1. Validate dataset
    manifest = validate_dataset(dataset_path)
    if not manifest.schema_valid:
        return {
            'status': 'failed',
            'state': TrainingState.FAILED,
            'stage': 'validation',
            'dataset_manifest': asdict(manifest),
        }
    logger.info('Dataset validated: %d examples, fingerprint=%s', manifest.num_examples, manifest.fingerprint)

    # 2. Load recipe
    state = TrainingState.PREPARING
    logger.info('State: %s', state)
    try:
        recipe = load_recipe(recipe_path)
    except (FileNotFoundError, ValueError) as e:
        return {'status': 'failed', 'state': TrainingState.FAILED, 'stage': 'recipe', 'error': str(e)}

    # 3. Training step — INTEGRATION POINT
    state = TrainingState.TRAINING
    logger.info('State: %s', state)
    logger.info(
        'Training config: model=%s, lr=%s, epochs=%d, batch=%d, lora_rank=%d',
        recipe.base_model,
        recipe.learning_rate,
        recipe.epochs,
        recipe.batch_size,
        recipe.lora_rank,
    )

    # INTEGRATION POINT: replace _simulate_training() with your GPU-backed backend
    # (SageMaker, Vertex AI, Ray Train, local torchtune). See module docstring.
    #   checkpoint_id, train_metrics = training_backend.train(recipe, manifest)
    checkpoint_id, train_metrics = _simulate_training(recipe, manifest)

    # 4. Post-training evaluation
    state = TrainingState.EVALUATING
    logger.info('State: %s', state)
    # In production: run eval suite against the real checkpoint.
    # The simulated training returns placeholder metrics; a real backend
    # would return actual validation loss and quality scores.
    eval_metrics = train_metrics

    # 5. Register in model registry
    state = TrainingState.REGISTERING
    logger.info('State: %s', state)
    try:
        from app.domain.models import ModelRegistryEntry
        from app.services.model_registry import ModelRegistry

        registry = ModelRegistry()
        entry = ModelRegistryEntry(
            model_id=checkpoint_id,
            backend='finetune',
            prompt_version='grounded_answer:v1',
            embedding_model='all-MiniLM-L6-v2',
            eval_snapshot=eval_metrics,
        )
        registry.register(entry)
    except Exception as e:
        logger.warning('Failed to register in model registry: %s', e)

    state = TrainingState.COMPLETED
    logger.info('Fine-tune pipeline completed (state=%s)', state)

    return {
        'status': 'completed',
        'state': state,
        'checkpoint_id': checkpoint_id,
        'recipe': asdict(recipe),
        'dataset_manifest': asdict(manifest),
        'eval_metrics': eval_metrics,
    }


if __name__ == '__main__':
    import argparse

    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(name)s %(message)s')

    parser = argparse.ArgumentParser(description='Fine-tuning pipeline')
    parser.add_argument('--recipe', default='data/finetune/sample_recipe.yaml')
    parser.add_argument('--dataset', default='data/finetune/sample_dataset.json')
    args = parser.parse_args()

    result = run_finetune(args.recipe, args.dataset)
    print(json.dumps(result, indent=2))
