# import numpy as np
# import torch

# from app.core.config import settings
# from app.models.device import get_device
# from app.services.extraction import CV_VIEWS, JD_VIEWS
# from app.models.inference import process_view, _build_xai_matches, _get_heatmap_label


# def cross_predict(cv_struct, jd_struct, fusion_model, backbone, tokenizer, entry):
#     device = get_device()

#     cv_data = [process_view(cv_struct.get(v)) for v in CV_VIEWS]
#     jd_data = [process_view(jd_struct.get(v)) for v in JD_VIEWS]
#     cv_texts, cv_exists = zip(*cv_data)
#     jd_texts, jd_exists = zip(*jd_data)

#     n_cv, n_jd = len(cv_texts), len(jd_texts)   # 10, 5
#     n_pairs = n_cv * n_jd                         # 50

#     mask = np.outer(np.array(cv_exists), np.array(jd_exists)).flatten().astype(np.float32)
#     mask_tensor = torch.tensor(mask, device=device).unsqueeze(0)   # (1, 50)

#     # All (cv_view, jd_view) pairs in row-major (i*n_jd + j) order — matches the mask.
#     cv_batch = [cv_texts[i] for i in range(n_cv) for _ in range(n_jd)]
#     jd_batch = [jd_texts[j] for _ in range(n_cv) for j in range(n_jd)]

#     # Only run the (expensive) backbone on non-empty pairs when enabled. Masked
#     # positions contribute 0 to the fusion regardless (masked = raw * mask), so
#     # the final score and the masked alignment matrix stay bit-identical; only
#     # the *raw* matrix at missing-section cells changes (display-only).
#     if settings.skip_empty_view_pairs:
#         active = [k for k in range(n_pairs) if mask[k] > 0]
#     else:
#         active = list(range(n_pairs))

#     hidden = fusion_model.scorer.fc[0].in_features   # 768, backend-agnostic
#     chunk = int(settings.inference_pair_chunk)

#     with torch.inference_mode():
#         cls_full = torch.zeros(1, n_pairs, hidden, device=device)
#         if active:
#             sub_cv = [cv_batch[k] for k in active]
#             sub_jd = [jd_batch[k] for k in active]
#             if chunk > 0 and len(active) > chunk:
#                 # Length-bucketed: tokenize once (no padding), sort pairs by
#                 # length, run the backbone in chunks padded only to each chunk's
#                 # own max — so one long view doesn't pad every pair. Per-pair
#                 # [CLS] is independent of batch composition → output-identical.
#                 enc = tokenizer(sub_cv, sub_jd, truncation=True, max_length=256)
#                 order = sorted(range(len(active)), key=lambda i: len(enc["input_ids"][i]))
#                 for s in range(0, len(order), chunk):
#                     local = order[s:s + chunk]
#                     batch = {k: [enc[k][i] for i in local] for k in enc}
#                     padded = tokenizer.pad(batch, return_tensors="pt").to(device)
#                     cls_chunk = backbone(**padded).last_hidden_state[:, 0, :]
#                     for j, i in enumerate(local):
#                         cls_full[0, active[i], :] = cls_chunk[j].to(cls_full.dtype)
#             else:
#                 enc = tokenizer(
#                     sub_cv, sub_jd,
#                     padding=True, truncation=True, max_length=256, return_tensors="pt",
#                 ).to(device)
#                 cls_sub = backbone(**enc).last_hidden_state[:, 0, :]
#                 cls_full[0, active, :] = cls_sub.to(cls_full.dtype)

#         final_score_t, m_aij_t, r_aij_t = fusion_model(cls_full, mask_tensor)

#     final_score = float(final_score_t.item())
#     similarity_matrix = m_aij_t.squeeze(0).float().cpu().numpy().reshape(n_cv, n_jd)
#     raw_matrix = r_aij_t.squeeze(0).float().cpu().numpy().reshape(n_cv, n_jd)

#     return {
#         "score": round(final_score * 10, 2),
#         "confidence": round(max(0.0, final_score), 4),
#         "match": final_score >= 0.5,
#         "label": "MATCHED" if final_score >= 0.5 else "MISMATCH",
#         "cv_view_coverage": f"{sum(cv_exists)}/{len(cv_exists)}",
#         "jd_view_coverage": f"{sum(jd_exists)}/{len(jd_exists)}",
#         "alignment_matrix_raw": raw_matrix.tolist(),
#         "alignment_matrix_masked": similarity_matrix.tolist(),
#         "heatmap_labels": {
#             "cv": [_get_heatmap_label(v, cv_struct, 45) for v in CV_VIEWS],
#             "jd": [_get_heatmap_label(v, jd_struct, 40) for v in JD_VIEWS],
#         },
#         "view_matches": _build_xai_matches(cv_struct, jd_struct, cv_exists, jd_exists, similarity_matrix),
#     }


#Code mới bắt đầu từ đây để hiển thị đúng score cho missing_section:
import numpy as np
import torch

from app.core.config import settings
from app.models.device import get_device
from app.services.extraction import CV_VIEWS, JD_VIEWS
from app.models.inference import process_view, _build_xai_matches, _get_heatmap_label


def cross_predict(cv_struct, jd_struct, fusion_model, backbone, tokenizer, entry):
    device = get_device()

    cv_data = [process_view(cv_struct.get(v)) for v in CV_VIEWS]
    jd_data = [process_view(jd_struct.get(v)) for v in JD_VIEWS]
    cv_texts, cv_exists = zip(*cv_data)
    jd_texts, jd_exists = zip(*jd_data)

    n_cv, n_jd = len(cv_texts), len(jd_texts)   # 10, 5
    n_pairs = n_cv * n_jd                         # 50

    mask = np.outer(np.array(cv_exists), np.array(jd_exists)).flatten().astype(np.float32)
    mask_tensor = torch.tensor(mask, device=device).unsqueeze(0)   # (1, 50)

    # All (cv_view, jd_view) pairs in row-major (i*n_jd + j) order — matches the mask.
    cv_batch = [cv_texts[i] for i in range(n_cv) for _ in range(n_jd)]
    jd_batch = [jd_texts[j] for _ in range(n_cv) for j in range(n_jd)]

    # Only run the (expensive) backbone on non-empty pairs when enabled. Masked
    # positions still contribute 0 to the fusion regardless (masked = raw * mask),
    # so the final score and the masked alignment matrix stay bit-identical.
    # HOWEVER the *raw* score at missing-section cells must still come from a
    # real "[EMPTY_SECTION]" embedding (matching what the model saw during
    # training) rather than a zero vector — a zero vector is an out-of-distribution
    # input the scorer never learned to handle, and produces meaningless raw
    # values that break the XAI/demo alignment matrix.
    if settings.skip_empty_view_pairs:
        active = [k for k in range(n_pairs) if mask[k] > 0]
        missing = [k for k in range(n_pairs) if mask[k] == 0]
    else:
        active = list(range(n_pairs))
        missing = []

    hidden = fusion_model.scorer.fc[0].in_features   # 768, backend-agnostic
    chunk = int(settings.inference_pair_chunk)

    with torch.inference_mode():
        cls_full = torch.zeros(1, n_pairs, hidden, device=device)

        if active:
            sub_cv = [cv_batch[k] for k in active]
            sub_jd = [jd_batch[k] for k in active]
            if chunk > 0 and len(active) > chunk:
                # Length-bucketed: tokenize once (no padding), sort pairs by
                # length, run the backbone in chunks padded only to each chunk's
                # own max — so one long view doesn't pad every pair. Per-pair
                # [CLS] is independent of batch composition → output-identical.
                enc = tokenizer(sub_cv, sub_jd, truncation=True, max_length=256)
                order = sorted(range(len(active)), key=lambda i: len(enc["input_ids"][i]))
                for s in range(0, len(order), chunk):
                    local = order[s:s + chunk]
                    batch = {k: [enc[k][i] for i in local] for k in enc}
                    padded = tokenizer.pad(batch, return_tensors="pt").to(device)
                    cls_chunk = backbone(**padded).last_hidden_state[:, 0, :]
                    for j, i in enumerate(local):
                        cls_full[0, active[i], :] = cls_chunk[j].to(cls_full.dtype)
            else:
                enc = tokenizer(
                    sub_cv, sub_jd,
                    padding=True, truncation=True, max_length=256, return_tensors="pt",
                ).to(device)
                cls_sub = backbone(**enc).last_hidden_state[:, 0, :]
                cls_full[0, active, :] = cls_sub.to(cls_full.dtype)

        if missing:
            # One extra (cheap) forward pass for the shared "[EMPTY_SECTION]"
            # pair, broadcast to every missing position. This matches the
            # training-time behaviour exactly (missing views are always
            # encoded as "[EMPTY_SECTION]" text, never as a zero vector).
            enc_empty = tokenizer(
                ["[EMPTY_SECTION]"], ["[EMPTY_SECTION]"],
                padding=True, truncation=True, max_length=256, return_tensors="pt",
            ).to(device)
            cls_empty = backbone(**enc_empty).last_hidden_state[:, 0, :]   # (1, hidden)
            cls_full[0, missing, :] = cls_empty.expand(len(missing), -1).to(cls_full.dtype)

        final_score_t, m_aij_t, r_aij_t = fusion_model(cls_full, mask_tensor)

    final_score = float(final_score_t.item())
    similarity_matrix = m_aij_t.squeeze(0).float().cpu().numpy().reshape(n_cv, n_jd)
    raw_matrix = r_aij_t.squeeze(0).float().cpu().numpy().reshape(n_cv, n_jd)

    return {
        "score": round(final_score * 10, 2),
        "confidence": round(max(0.0, final_score), 4),
        "match": final_score >= 0.5,
        "label": "MATCHED" if final_score >= 0.5 else "MISMATCH",
        "cv_view_coverage": f"{sum(cv_exists)}/{len(cv_exists)}",
        "jd_view_coverage": f"{sum(jd_exists)}/{len(jd_exists)}",
        "alignment_matrix_raw": raw_matrix.tolist(),
        "alignment_matrix_masked": similarity_matrix.tolist(),
        "heatmap_labels": {
            "cv": [_get_heatmap_label(v, cv_struct, 45) for v in CV_VIEWS],
            "jd": [_get_heatmap_label(v, jd_struct, 40) for v in JD_VIEWS],
        },
        "view_matches": _build_xai_matches(cv_struct, jd_struct, cv_exists, jd_exists, similarity_matrix),
    }