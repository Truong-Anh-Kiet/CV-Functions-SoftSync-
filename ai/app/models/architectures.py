"""
Architecture classes for the 4 multi-view cross-view model variants.

All 4 models share the same inference contract:
    forward(x: Tensor[B, 50]) -> Tensor[B, 1]  (sigmoid probability)

Where `x` is the masked cross-view similarity vector (cv_view × jd_view = 10 × 5 = 50)
flattened. The SBERT encoder + similarity + masking pipeline lives in inference.py.

Field names below MUST stay aligned with the keys saved in the original .pth
state_dicts (see folder_model_notebook_architurecture_model/). Any rename here
must be matched by a corresponding rename in those checkpoints.
"""

import torch.nn as nn
import torch.nn.functional as F


class AttentionFusionModel(nn.Module):
    def __init__(self, num_views: int = 50, d_model: int = 64, nhead: int = 8):
        super().__init__()

        self.input_projection = nn.Linear(1, d_model)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model,
            nhead=nhead,
            dim_feedforward=256,
            dropout=0.2,
            batch_first=True,
        )
        self.attention_block = nn.TransformerEncoder(encoder_layer, num_layers=3)

        self.fc_fusion = nn.Sequential(
            nn.Linear(d_model * num_views, 128),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(128, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        batch_size = x.shape[0]
        tokens = x.unsqueeze(-1)
        h = self.input_projection(tokens)
        attn_out = self.attention_block(h)
        attn_flat = attn_out.reshape(batch_size, -1)
        return self.fc_fusion(attn_flat)


class AdvancedFusionMLP_Base(nn.Module):
    def __init__(self, input_dim: int = 50):
        super().__init__()
        self.net = nn.Sequential(
            nn.Linear(input_dim, 512),
            nn.BatchNorm1d(512),
            nn.ReLU(),
            nn.Dropout(0.3),

            nn.Linear(512, 128),
            nn.ReLU(),

            nn.Linear(128, 64),
            nn.ReLU(),

            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.net(x)


class ResidualBlock(nn.Module):
    def __init__(self, dim: int):
        super().__init__()
        self.ln = nn.LayerNorm(dim)
        self.fc = nn.Linear(dim, dim)

    def forward(self, x):
        return x + F.relu(self.fc(self.ln(x)))


class AdvancedFusionMLP_Residual(nn.Module):
    def __init__(self, input_dim: int = 50):
        super().__init__()
        self.input_layer = nn.Sequential(
            nn.Linear(input_dim, 256),
            nn.ReLU(),
        )

        self.res1 = ResidualBlock(256)
        self.res2 = ResidualBlock(256)

        self.fc_hidden = nn.Sequential(
            nn.Linear(256, 128),
            nn.ReLU(),
            nn.Dropout(0.4),
            nn.Linear(128, 64),
            nn.ReLU(),
        )

        self.output_layer = nn.Sequential(
            nn.Linear(64, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        x = self.input_layer(x)
        x = self.res1(x)
        x = self.res2(x)
        x = self.fc_hidden(x)
        return self.output_layer(x)


class WeightedSumFusion(nn.Module):
    def __init__(self, input_dim: int = 50):
        super().__init__()
        self.weighted_layer = nn.Linear(input_dim, 1)
        self.sigmoid = nn.Sigmoid()

    def forward(self, x):
        out = self.weighted_layer(x)
        return self.sigmoid(out)
