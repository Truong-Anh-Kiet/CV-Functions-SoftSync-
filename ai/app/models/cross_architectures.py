import torch
import torch.nn as nn
import torch.nn.functional as F

class ViewPairScorer(nn.Module):
    def __init__(self, hidden_dim=768):
        super().__init__()
        self.fc = nn.Sequential(
            nn.Linear(hidden_dim, 256),
            nn.ReLU(),
            nn.Linear(256, 1)
        )
        nn.init.constant_(self.fc[2].bias, -2.0) 

    def forward(self, cls):
        return torch.sigmoid(self.fc(cls)).squeeze(-1)

class ResidualBlock(nn.Module):
    def __init__(self, dim):
        super().__init__()
        self.ln = nn.LayerNorm(dim)
        self.fc = nn.Linear(dim, dim)
    def forward(self, x):
        return x + F.relu(self.fc(self.ln(x)))

class CrossFusion_Residual(nn.Module):
    # Attribute names match the checkpoint keys: fusion.inp / res1 / res2 / hidden / out
    def __init__(self, input_dim=100):
        super().__init__()
        self.inp = nn.Sequential(nn.Linear(input_dim, 256), nn.ReLU())
        self.res1 = ResidualBlock(256)
        self.res2 = ResidualBlock(256)
        self.hidden = nn.Sequential(
            nn.Linear(256, 128), # index 0
            nn.ReLU(),           # index 1
            nn.Dropout(0.4),     # index 2 (no params; identity in eval)
            nn.Linear(128, 64),  # index 3
            nn.ReLU()            # index 4
        )
        self.out = nn.Sequential(
            nn.Linear(64, 1),
            nn.Sigmoid()
        )

    def forward(self, a_ij, mask):
        x = torch.cat([a_ij, mask], dim=-1)
        x = self.inp(x)
        x = self.res1(x)
        x = self.res2(x)
        return self.out(self.hidden(x))

class CrossFusion_MLP(nn.Module):
    def __init__(self, input_dim=100):
        super().__init__()
        # Khớp index với checkpoint MLP Base
        self.net = nn.Sequential(
            nn.Linear(input_dim, 512), # 0
            nn.BatchNorm1d(512),       # 1
            nn.ReLU(),                 # 2
            nn.Dropout(0.3),           # 3
            nn.Linear(512, 128),       # 4
            nn.ReLU(),                 # 5
            nn.Linear(128, 64),        # 6
            nn.ReLU(),                 # 7
            nn.Linear(64, 1),          # 8
            nn.Sigmoid()               # 9
        )

    def forward(self, a_ij, mask):
        x = torch.cat([a_ij, mask], dim=-1)
        return self.net(x)

class CrossFusion_Weighted(nn.Module):
    # Attribute name matches the checkpoint key: fusion.layer
    def __init__(self, input_dim=100):
        super().__init__()
        self.layer = nn.Linear(input_dim, 1)

    def forward(self, a_ij, mask):
        x = torch.cat([a_ij, mask], dim=-1)
        return torch.sigmoid(self.layer(x))

class CrossFusion_Attention(nn.Module):
    # Attribute names match the checkpoint keys: fusion.proj / attn / head
    def __init__(self, num_views=50, d_model=64, nhead=8):
        super().__init__()
        self.proj = nn.Linear(2, d_model)
        encoder_layer = nn.TransformerEncoderLayer(
            d_model=d_model, nhead=nhead, dim_feedforward=256, dropout=0.2, batch_first=True
        )
        self.attn = nn.TransformerEncoder(encoder_layer, num_layers=3)
        self.head = nn.Sequential(
            nn.Linear(d_model * num_views, 128), # 0
            nn.ReLU(),                           # 1
            nn.Dropout(0.4),                     # 2 (no params; identity in eval)
            nn.Linear(128, 1),                   # 3
            nn.Sigmoid(),                        # 4
        )

    def forward(self, a_ij, mask):
        tokens = torch.stack([a_ij, mask], dim=-1)
        h = self.proj(tokens)
        attn_out = self.attn(h)
        attn_flat = attn_out.reshape(attn_out.shape[0], -1)
        return self.head(attn_flat)

class FusionWithScorerWrapper(nn.Module):
    def __init__(self, hidden_dim, fusion_module):
        super().__init__()
        self.scorer = ViewPairScorer(hidden_dim)
        self.fusion = fusion_module
        
    def forward(self, cls, mask):
        raw_a_ij = self.scorer(cls) 
        masked_a_ij = raw_a_ij * mask 
        final_score = self.fusion(masked_a_ij, mask)               
        return final_score, masked_a_ij, raw_a_ij