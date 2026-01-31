#!/usr/bin/env python3
"""Convert PEFT LoRA adapter to MLX format.

Usage:
    python scripts/convert_peft_to_mlx.py \
        --peft-path models/luna_lora_peft \
        --mlx-path models/luna_lora_mlx \
        --num-layers 36
"""

import argparse
import json
import re
from pathlib import Path

import numpy as np
from safetensors.numpy import save_file


def convert_key(peft_key: str) -> str:
    """Convert PEFT key name to MLX format.

    PEFT:  base_model.model.model.layers.0.self_attn.q_proj.lora_A.weight
    MLX:   model.layers.0.self_attn.q_proj.lora_a
    """
    # Strip the base_model.model prefix (keep one 'model.')
    key = re.sub(r'^base_model\.model\.model\.', 'model.', peft_key)

    # Convert lora_A.weight -> lora_a, lora_B.weight -> lora_b
    key = re.sub(r'\.lora_A\.weight$', '.lora_a', key)
    key = re.sub(r'\.lora_B\.weight$', '.lora_b', key)

    return key


def convert_peft_to_mlx(peft_path: Path, mlx_path: Path, num_layers: int = 36):
    """Convert PEFT adapter to MLX format."""
    # Import here to handle environments without torch
    try:
        from safetensors.torch import load_file as load_torch
    except ImportError:
        from safetensors import safe_open
        def load_torch(path):
            with safe_open(path, framework='np') as f:
                return {k: f.get_tensor(k) for k in f.keys()}

    # Load PEFT adapter
    peft_weights_path = peft_path / 'adapter_model.safetensors'
    print(f"Loading PEFT adapter from {peft_weights_path}")
    peft_weights = load_torch(str(peft_weights_path))

    # Load PEFT config to get LoRA parameters
    peft_config_path = peft_path / 'adapter_config.json'
    with open(peft_config_path) as f:
        peft_config = json.load(f)

    rank = peft_config.get('r', 16)
    alpha = peft_config.get('lora_alpha', 16)
    dropout = peft_config.get('lora_dropout', 0)

    # Convert weights
    # MLX expects different shapes than PEFT:
    #   PEFT lora_A: (r, input_dims) -> MLX lora_a: (input_dims, r)  [transpose]
    #   PEFT lora_B: (output_dims, r) -> MLX lora_b: (r, output_dims) [transpose]
    mlx_weights = {}
    for peft_key, tensor in peft_weights.items():
        mlx_key = convert_key(peft_key)
        # Convert to numpy, handle torch tensors
        if hasattr(tensor, 'numpy'):
            arr = tensor.numpy()
        elif hasattr(tensor, 'cpu'):
            arr = tensor.cpu().numpy()
        else:
            arr = np.array(tensor)

        # Transpose LoRA weights for MLX format
        if '.lora_a' in mlx_key or '.lora_b' in mlx_key:
            arr = arr.T

        mlx_weights[mlx_key] = arr

    print(f"Converted {len(mlx_weights)} weight tensors")

    # Create output directory
    mlx_path.mkdir(parents=True, exist_ok=True)

    # Save MLX weights
    mlx_weights_path = mlx_path / 'adapters.safetensors'
    save_file(mlx_weights, str(mlx_weights_path))
    print(f"Saved MLX weights to {mlx_weights_path}")

    # Build target keys list for MLX config
    target_modules = peft_config.get('target_modules', [])
    mlx_keys = []
    for mod in target_modules:
        if mod in ['q_proj', 'k_proj', 'v_proj', 'o_proj']:
            mlx_keys.append(f'self_attn.{mod}')
        elif mod in ['gate_proj', 'up_proj', 'down_proj']:
            mlx_keys.append(f'mlp.{mod}')

    # Create MLX adapter config (JSON format)
    mlx_config = {
        'num_layers': num_layers,
        'lora_parameters': {
            'rank': rank,
            'alpha': alpha,
            'scale': float(alpha) / float(rank),
            'dropout': dropout,
            'keys': mlx_keys
        }
    }

    mlx_config_path = mlx_path / 'adapter_config.json'
    with open(mlx_config_path, 'w') as f:
        json.dump(mlx_config, f, indent=2)
    print(f"Saved MLX config to {mlx_config_path}")

    # Print summary
    print(f"\nConversion complete!")
    print(f"  Rank: {rank}")
    print(f"  Alpha: {alpha}")
    print(f"  Scale: {float(alpha) / float(rank)}")
    print(f"  Target modules: {mlx_keys}")
    print(f"  Output: {mlx_path}")


def main():
    parser = argparse.ArgumentParser(description='Convert PEFT LoRA to MLX format')
    parser.add_argument('--peft-path', type=Path, required=True,
                        help='Path to PEFT adapter directory')
    parser.add_argument('--mlx-path', type=Path, required=True,
                        help='Output path for MLX adapter')
    parser.add_argument('--num-layers', type=int, default=36,
                        help='Number of transformer layers (default: 36 for Qwen 3B)')

    args = parser.parse_args()
    convert_peft_to_mlx(args.peft_path, args.mlx_path, args.num_layers)


if __name__ == '__main__':
    main()
