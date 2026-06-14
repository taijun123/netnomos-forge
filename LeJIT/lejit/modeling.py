from __future__ import annotations

from pathlib import Path

import torch
from transformers import CONFIG_MAPPING, AutoConfig, AutoModelForCausalLM, PreTrainedModel

from lejit.config import ModelSourceConfig


def build_model(config: ModelSourceConfig, vocab_size: int) -> PreTrainedModel:
    if config.mode == "pretrained":
        assert config.name_or_path is not None
        model = AutoModelForCausalLM.from_pretrained(config.name_or_path)
    else:
        if config.name_or_path:
            model_config = AutoConfig.from_pretrained(config.name_or_path)
        else:
            model_config = CONFIG_MAPPING[config.architecture]()
        for key, value in config.config_overrides.items():
            setattr(model_config, key, value)
        model = AutoModelForCausalLM.from_config(model_config)
    model.resize_token_embeddings(vocab_size)
    model.config.vocab_size = vocab_size
    return model


def save_model(model: PreTrainedModel, path: str | Path) -> None:
    model.save_pretrained(Path(path))


def meta_parameter_names(model: PreTrainedModel) -> list[str]:
    return [
        name
        for name, param in model.named_parameters()
        if getattr(param, "is_meta", False)
    ]


def _load_checkpoint_eagerly(path: Path) -> PreTrainedModel:
    model_config = AutoConfig.from_pretrained(path, local_files_only=True)
    model = AutoModelForCausalLM.from_config(model_config)

    safetensors_path = path / "model.safetensors"
    bin_path = path / "pytorch_model.bin"
    if safetensors_path.exists():
        from safetensors.torch import load_file  # noqa: PLC0415

        state_dict = load_file(str(safetensors_path), device="cpu")
    elif bin_path.exists():
        try:
            state_dict = torch.load(bin_path, map_location="cpu", weights_only=True)
        except TypeError:
            state_dict = torch.load(bin_path, map_location="cpu")
    else:
        raise FileNotFoundError(f"LeJIT model checkpoint not found under {path}")

    model.load_state_dict(state_dict, strict=False)
    model.tie_weights()
    return model


def load_model(path: str | Path, device: str | torch.device = "cpu") -> PreTrainedModel:
    model_path = Path(path)
    model = AutoModelForCausalLM.from_pretrained(
        model_path,
        local_files_only=True,
        low_cpu_mem_usage=False,
        device_map=None,
    )
    model.tie_weights()
    if meta_parameter_names(model):
        model = _load_checkpoint_eagerly(model_path)
    meta_names = meta_parameter_names(model)
    if meta_names:
        preview = ", ".join(meta_names[:5])
        raise RuntimeError(
            f"LeJIT model loaded with meta tensors under {model_path}: {preview}"
        )
    model.to(device)
    model.eval()
    return model
