# AI Model Checkpoints

Deployable model weights for the CV–JD matching service. Each model lives in its
own subfolder named after its `model_id`. The runtime reads the **registry** (not
these files) to decide what to load; the loader globs `*.pth` in the folder.

## Layout

```
checkpoints/
├── README.md
├── <model_id>/
│   └── *.pth              # loader picks the .pth in the folder
└── ...
```

`MODELS_DIR` (default `./checkpoints`, resolved against the `ai/` repo root) sets the root.

## Deployed models (cross-encoder, mBERT)

The active models are 4 cross-encoders that **share one `bert-base-multilingual-cased`
backbone**; each `.pth` holds only the small fusion head + scorer (`{"model", "task_w"}`
format — `task_w` is training-only and ignored at inference). Registered in
`app/models/cross_registry.py` (+ `app/models/registry.py`); classes in
`app/models/cross_architectures.py`.

| model_id (key)    | Fusion head  | Notes                  |
| ----------------- | ------------ | ---------------------- |
| `cross_weighted`  | Weighted Sum | **default** (~86% acc) |
| `cross_mlp`       | MLP          |                        |
| `cross_residual`  | Residual MLP |                        |
| `cross_attention` | Transformer  |                        |

Default is set by `DEFAULT_MODEL_ID` (default `cross_weighted`). Only models whose
checkpoint is present are exposed at `GET /api/v1/matching/models`.

## Legacy bi-encoder models

Folders such as `attention_gte_base`, `mlp_base_gte_base`, `mlp_residual_bge_base`,
`weighted_sum_careerbert` (each `weights.pth` + `metadata.json`) are the older SBERT
bi-encoders. They stay in the registry but are **hidden from `/models`**
(`list_public()` filters to cross-encoders); classes in `app/models/architectures.py`.

## Adding a cross-encoder model

1. **Architecture**: add/adjust the fusion `nn.Module` in `app/models/cross_architectures.py`.
   Attribute names must match the checkpoint's `state_dict` keys (`scorer.*`, `fusion.*`).
2. **Registry**: add a `CrossModelEntry` to `cross_registry.py` **and** a matching
   `ModelEntry` (`is_cross=True`) to `registry.py` — keep both in sync.
3. **Weights**: create `checkpoints/<model_id>/` and drop the `.pth` in.
4. **Verify**: the first load runs `load_state_dict(strict=True)` — any key mismatch
   raises immediately with the offending key name.

## Removing a model

Delete the folder and the entries in both registries. If it was the default,
update `DEFAULT_MODEL_ID` first.
