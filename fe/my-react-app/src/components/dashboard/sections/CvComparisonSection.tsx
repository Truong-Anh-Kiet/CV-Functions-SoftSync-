import { useState } from 'react';
import type { ModelOption } from '../../../types/model';
import type { RankingResultItem } from '../../../types/ranking';
import type { UploadedFile } from '../../../types/dashboard';
import { useCvComparison } from '../../../hooks/useCvComparison';
import RankingDetailModal from '../modals/RankingDetailModal';
import FileViewerModal from '../modals/FileViewerModal';

interface CvComparisonSectionProps {
  modelOptions: ModelOption[];
  selectedModel: string;
  setSelectedModel: (value: string) => void;
  showNotify: (msg: string) => void;
}

const pct = (value: number) => `${Math.round(value * 100)}%`;

const cellTone = (score: number) => {
  if (score >= 0.66) return 'good';
  if (score >= 0.33) return 'mid';
  return 'low';
};

const UploadIcon = () => (
  <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">
    <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
    <polyline points="17 8 12 3 7 8" />
    <line x1="12" y1="3" x2="12" y2="15" />
  </svg>
);

/** Khung tài liệu chỉ-đọc (dùng cho JD pdf đã chọn & dải preview thu gọn). */
function DocCard({
  label, name, url, placeholder, onOpen,
}: { label: string; name?: string; url: string | null; placeholder: string; onOpen?: () => void }) {
  return (
    <div className="cmp-doc">
      <div className="cmp-doc-head">
        <span className="cmp-doc-label">{label}</span>
        {name && <span className="cmp-doc-name" title={name}>{name}</span>}
      </div>
      <div className="cmp-doc-body">
        {url ? (
          <>
            <iframe src={url} title={name || label} className="cmp-doc-frame" />
            {onOpen && <button type="button" className="cmp-doc-open" onClick={onOpen}>Xem to</button>}
          </>
        ) : (
          <div className="cmp-doc-empty">{placeholder}</div>
        )}
      </div>
    </div>
  );
}

export default function CvComparisonSection({
  modelOptions,
  selectedModel,
  setSelectedModel,
  showNotify,
}: CvComparisonSectionProps) {
  const cmp = useCvComparison();
  const [detailResult, setDetailResult] = useState<RankingResultItem | null>(null);
  const [viewingFile, setViewingFile] = useState<UploadedFile | null>(null);
  const [showPreview, setShowPreview] = useState(true);

  const hasResults = cmp.results.length > 0;
  const jdReady = cmp.jdMode === 'text' ? cmp.jdText.trim().length > 0 : Boolean(cmp.jdFile);
  const canRun = jdReady && cmp.totalCvCount === 2 && !cmp.loading;

  const handleRun = () => cmp.handleRunComparison({ modelId: selectedModel, showNotify });

  const handleReset = () => {
    cmp.clearResults();
    setShowPreview(true);
  };

  const openPdf = (name: string, url: string | null) => {
    if (!url) return;
    setViewingFile({
      id: `cmp-${name}`,
      filename: name.toLowerCase().endsWith('.pdf') ? name : `${name}.pdf`,
      preview_url: url,
      isSaved: true,
      category: 'CV',
      section: 'CV Comparison',
    });
  };

  // ---- Khung CV (setup): tự chứa nút upload / chọn từ kho ----
  const renderSlotCard = (index: 0 | 1) => {
    const slot = cmp.slots[index];
    const preview = cmp.cvPreviews[index];
    const inputId = `cmp-cv-upload-${index}`;
    const label = index === 0 ? 'CV A' : 'CV B';
    const otherSavedId = cmp.savedIdInOtherSlot(index);

    return (
      <div className="cmp-doc">
        <div className="cmp-doc-head">
          <span className="cmp-doc-label">{label}</span>
          {preview?.name && <span className="cmp-doc-name" title={preview.name}>{preview.name}</span>}
          {slot && (
            <button type="button" className="cmp-doc-clear" onClick={() => cmp.clearSlot(index)} disabled={cmp.loading}>
              Gỡ
            </button>
          )}
        </div>
        <div className="cmp-doc-body">
          {slot ? (
            <>
              {preview?.url ? (
                <iframe src={preview.url} title={preview.name} className="cmp-doc-frame" />
              ) : (
                <div className="cmp-doc-empty">Không có bản xem trước cho CV này.</div>
              )}
              {preview?.url && (
                <button type="button" className="cmp-doc-open" onClick={() => openPdf(preview.name, preview.url)}>
                  Xem to
                </button>
              )}
            </>
          ) : (
            <div className="cmp-slot-input">
              <input id={inputId} type="file" accept=".pdf" hidden onChange={(e) => cmp.setSlotUpload(index, e)} disabled={cmp.loading} />
              <label htmlFor={inputId} className="cmp-slot-drop">
                <div className="upload-icon-circle"><UploadIcon /></div>
                <strong>Tải lên {label} (PDF)</strong>
              </label>
              <div className="cmp-slot-or"><span>hoặc</span></div>
              <select
                className="cmp-slot-select"
                value=""
                disabled={cmp.loading || cmp.savedCvs.length === 0}
                onChange={(e) => {
                  const id = Number(e.target.value);
                  const cv = cmp.savedCvs.find((c) => c.id === id);
                  if (cv) cmp.setSlotSaved(index, cv);
                }}
              >
                <option value="">
                  {cmp.savedCvs.length === 0 ? 'Kho CV trống' : `Chọn từ kho (${cmp.savedCvs.length})`}
                </option>
                {cmp.savedCvs.map((cv) => (
                  <option key={cv.id} value={cv.id} disabled={cv.id === otherSavedId}>
                    {cv.filename}
                  </option>
                ))}
              </select>
            </div>
          )}
        </div>
      </div>
    );
  };

  // ---- Khung JD (setup): toggle Text/PDF + nhập ngay trong khung ----
  const renderJdCard = () => (
    <div className="cmp-doc">
      <div className="cmp-doc-head">
        <span className="cmp-doc-label">JD</span>
        <div className="cmp-jd-tabs">
          <button type="button" className={cmp.jdMode === 'text' ? 'active' : ''} onClick={() => cmp.setJdMode('text')} disabled={cmp.loading}>Text</button>
          <button type="button" className={cmp.jdMode === 'file' ? 'active' : ''} onClick={() => cmp.setJdMode('file')} disabled={cmp.loading}>PDF</button>
        </div>
        {cmp.jdMode === 'file' && cmp.jdFile && (
          <button type="button" className="cmp-doc-clear" onClick={cmp.clearJdFile} disabled={cmp.loading}>Gỡ</button>
        )}
      </div>
      <div className="cmp-doc-body">
        {cmp.jdMode === 'text' ? (
          <textarea
            className="cmp-jd-textarea"
            value={cmp.jdText}
            onChange={(e) => cmp.setJdText(e.target.value)}
            placeholder="Dán nội dung Job Description vào đây..."
            spellCheck={false}
            disabled={cmp.loading}
          />
        ) : cmp.jdFile && cmp.jdFileUrl ? (
          <>
            <iframe src={cmp.jdFileUrl} title={cmp.jdFile.name} className="cmp-doc-frame" />
            <button type="button" className="cmp-doc-open" onClick={() => openPdf(cmp.jdFile!.name, cmp.jdFileUrl)}>Xem to</button>
          </>
        ) : (
          <div className="cmp-slot-input">
            <input id="cmp-jd-upload" type="file" accept=".pdf" hidden onChange={cmp.handleJdFileChange} disabled={cmp.loading} />
            <label htmlFor="cmp-jd-upload" className="cmp-slot-drop">
              <div className="upload-icon-circle"><UploadIcon /></div>
              <strong>Tải lên JD (PDF)</strong>
            </label>
          </div>
        )}
      </div>
    </div>
  );

  const previewA = cmp.cvPreviews[0];
  const previewB = cmp.cvPreviews[1];

  return (
    <div className="cmp-workspace">
      {/* Control bar */}
      <div className="cmp-controlbar">
        <div className="cmp-controlbar-field">
          <span>Model AI</span>
          <select
            className="cmp-controlbar-select"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={cmp.loading || modelOptions.length === 0}
          >
            {modelOptions.length === 0 ? (
              <option value="">Đang tải model...</option>
            ) : (
              modelOptions.map((opt) => <option key={opt.id} value={opt.id}>{opt.display_name}</option>)
            )}
          </select>
        </div>

        <span className={`cmp-count ${cmp.totalCvCount === 2 ? 'ok' : ''}`}>
          {cmp.totalCvCount === 2 ? 'Đã chọn đủ 2 CV' : `Cần chọn đủ 2 CV (hiện ${cmp.totalCvCount})`}
        </span>

        {cmp.meta?.elapsed_seconds != null && <span className="cmp-elapsed">{cmp.meta.elapsed_seconds}s</span>}

        <div className="cmp-controlbar-actions">
          {hasResults && (
            <button type="button" className="ranking-link-btn" onClick={handleReset}>So sánh lại</button>
          )}
          <button type="button" className="save-btn cmp-run-btn" onClick={handleRun} disabled={!canRun}>
            {cmp.loading ? 'Đang so sánh...' : 'So sánh 2 CV'}
          </button>
        </div>
      </div>

      {/* SETUP: chỉ 3 khung preview, mỗi khung tự chứa input */}
      {!hasResults && (
        <div className="cmp-preview-row">
          {renderSlotCard(0)}
          {renderJdCard()}
          {renderSlotCard(1)}
        </div>
      )}

      {/* RESULT: verdict + dimension grid + dải preview thu gọn */}
      {hasResults && cmp.verdict && (
        <div className="cmp-result">
          <div className={`cmp-verdict ${cmp.verdict.isClose ? 'is-close' : ''}`}>
            <div className="cmp-verdict-head">
              {cmp.verdict.isClose ? (
                <span className="cmp-verdict-badge warn">⚠ Quá sát — nên review thủ công</span>
              ) : (
                <span className="cmp-verdict-badge win">
                  ✓ Nên chọn: {(cmp.verdict.winnerIndex === 0 ? cmp.verdict.cvA : cmp.verdict.cvB).cv_file}
                </span>
              )}
              <span className="cmp-verdict-margin">Chênh lệch {cmp.verdict.margin.toFixed(2)} / 10</span>
            </div>

            <div className="cmp-verdict-cards">
              {[cmp.verdict.cvA, cmp.verdict.cvB].map((cv, idx) => {
                const isWinner = cmp.verdict!.winnerIndex === idx;
                return (
                  <div key={cv.cv_file} className={`cmp-cand ${isWinner ? 'winner' : ''}`}>
                    <div className="cmp-cand-top">
                      <span className="cmp-cand-tag">{idx === 0 ? 'CV A' : 'CV B'}</span>
                      {isWinner && <span className="cmp-cand-star">★ Dẫn đầu</span>}
                    </div>
                    <strong className="cmp-cand-name" title={cv.cv_file}>{cv.cv_file}</strong>
                    <div className="cmp-cand-stats">
                      <span>Score <b>{cv.score.toFixed(2)}/10</b></span>
                      <span>Confidence <b>{(cv.confidence * 100).toFixed(0)}%</b></span>
                      <span className={cv.match ? 'cmp-tag matched' : 'cmp-tag mismatch'}>{cv.label}</span>
                    </div>
                    <button type="button" className="cmp-cand-detail" onClick={() => setDetailResult(cv)}>Xem chi tiết</button>
                  </div>
                );
              })}
            </div>

            {(cmp.verdict.advantagesA.length > 0 || cmp.verdict.advantagesB.length > 0) && (
              <div className="cmp-verdict-notes">
                <div className="cmp-notes-col">
                  <h4>Điểm mạnh của {cmp.verdict.cvA.cv_file}</h4>
                  {cmp.verdict.advantagesA.length > 0 ? (
                    <ul>{cmp.verdict.advantagesA.map((r, i) => <li key={i}>{r}</li>)}</ul>
                  ) : (
                    <p className="cmp-notes-empty">Không có tiêu chí nào vượt trội rõ rệt.</p>
                  )}
                </div>
                <div className="cmp-notes-col">
                  <h4>Điểm mạnh của {cmp.verdict.cvB.cv_file}</h4>
                  {cmp.verdict.advantagesB.length > 0 ? (
                    <ul>{cmp.verdict.advantagesB.map((c, i) => <li key={i}>{c}</li>)}</ul>
                  ) : (
                    <p className="cmp-notes-empty">Không có tiêu chí nào vượt trội rõ rệt.</p>
                  )}
                </div>
              </div>
            )}
          </div>

          {/* Per-dimension grid */}
          <div className="cmp-grid-wrap">
            <table className="cmp-grid">
              <thead>
                <tr>
                  <th>Tiêu chí (theo JD)</th>
                  <th className="cmp-grid-cv">{cmp.verdict.cvA.cv_file}</th>
                  <th className="cmp-grid-cv">{cmp.verdict.cvB.cv_file}</th>
                </tr>
              </thead>
              <tbody>
                {cmp.verdict.dimensionRows.map((row) => (
                  <tr key={row.jdKey}>
                    <td className="cmp-grid-label">{row.label}</td>
                    <td
                      className={`cmp-grid-cell ${cellTone(row.scoreA)} ${row.winner === 'A' ? 'win' : ''}`}
                      onClick={() => setDetailResult(cmp.verdict!.cvA)}
                    >
                      {pct(row.scoreA)}{row.winner === 'A' && ' ✓'}
                    </td>
                    <td
                      className={`cmp-grid-cell ${cellTone(row.scoreB)} ${row.winner === 'B' ? 'win' : ''}`}
                      onClick={() => setDetailResult(cmp.verdict!.cvB)}
                    >
                      {pct(row.scoreB)}{row.winner === 'B' && ' ✓'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          {/* Dải preview thu gọn */}
          <div className="cmp-preview-collapse">
            <button type="button" className="ranking-link-btn" onClick={() => setShowPreview((v) => !v)}>
              {showPreview ? 'Ẩn tài liệu' : 'Hiện tài liệu'}
            </button>
            {showPreview && (
              <div className="cmp-preview-row slim">
                <DocCard label="CV A" name={previewA?.name} url={previewA?.url ?? null} placeholder="—" onOpen={previewA?.url ? () => openPdf(previewA.name, previewA.url) : undefined} />
                {cmp.jdMode === 'text' ? (
                  <div className="cmp-doc">
                    <div className="cmp-doc-head"><span className="cmp-doc-label">JD</span></div>
                    <div className="cmp-doc-body"><div className="cmp-doc-text">{cmp.jdText}</div></div>
                  </div>
                ) : (
                  <DocCard label="JD" name={cmp.jdFile?.name} url={cmp.jdFileUrl} placeholder="—" onOpen={cmp.jdFile && cmp.jdFileUrl ? () => openPdf(cmp.jdFile!.name, cmp.jdFileUrl) : undefined} />
                )}
                <DocCard label="CV B" name={previewB?.name} url={previewB?.url ?? null} placeholder="—" onOpen={previewB?.url ? () => openPdf(previewB.name, previewB.url) : undefined} />
              </div>
            )}
          </div>
        </div>
      )}

      <RankingDetailModal result={detailResult} onClose={() => setDetailResult(null)} />
      <FileViewerModal file={viewingFile} onClose={() => setViewingFile(null)} />
    </div>
  );
}
