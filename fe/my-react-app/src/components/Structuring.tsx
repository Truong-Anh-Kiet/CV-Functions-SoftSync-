import { useState, useEffect } from 'react';
import './Structuring.css';

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000';

// Định nghĩa các nhãn hiển thị cho 10 mục CV
const CV_VIEW_LABELS: Record<string, string> = {
  skills: 'Skills',
  education: 'Education',
  year_experience: 'Year Experience',
  experience: 'Experience',
  responsibilities: 'Responsibilities',
  projects: 'Projects',
  publications: 'Publications',
  achievement: 'Achievement',
  certification: 'Certification',
  employment_history: 'Employment History',
};

// Định nghĩa các nhãn hiển thị cho 5 mục JD
const JD_VIEW_LABELS: Record<string, string> = {
  skills: 'Skills',
  education: 'Education',
  year_experience_requirement: 'Year Experience Requirement',
  experience_requirement: 'Experience Requirement',
  responsibilities: 'Responsibilities',
};

interface UploadedFile {
  filename: string;
  preview_url: string;
  sourceFile: File;
}

interface StructuringProps {
  // Dữ liệu được nạp từ kết quả Matching của Dashboard.tsx
  sharedCvData?: any;
  sharedJdData?: any;
  onDataUpdate?: (type: 'cv' | 'jd', data: any) => void;
  hideControls?: boolean; // Thêm dòng này để nhận diện prop từ Dashboard và hết gạch đỏ
}

export default function Structuring({ sharedCvData, sharedJdData, onDataUpdate, hideControls }: StructuringProps) {
  const [activeTab, setActiveTab] = useState<'cv' | 'jd'>('cv');
  const [file, setFile] = useState<UploadedFile | null>(null);
  const [jdText, setJdText] = useState('');
  const [isTextInput, setIsTextInput] = useState(false);
  
  const [loading, setLoading] = useState(false);
  const [cvStructuredData, setCvStructuredData] = useState<any>(null);
  const [jdStructuredData, setJdStructuredData] = useState<any>(null);
  const [notification, setNotification] = useState<string | null>(null);

  // Lắng nghe sự thay đổi từ props (sharedCvData, sharedJdData)
  useEffect(() => {
    if (sharedCvData) {
      setCvStructuredData(sharedCvData);
    }
    if (sharedJdData) {
      setJdStructuredData(sharedJdData);
    }
  }, [sharedCvData, sharedJdData]);

  const showNotify = (msg: string) => {
    setNotification(msg);
    setTimeout(() => setNotification(null), 3000);
  };

  const handleFileUpload = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const selectedFile = e.target.files?.[0];
    if (!selectedFile) return;

    setLoading(true);
    const formData = new FormData();
    formData.append('file', selectedFile);

    try {
      const response = await fetch(`${API_BASE_URL}/api/v1/upload/preview`, {
        method: 'POST',
        body: formData,
      });
      const result = await response.json();

      if (result.status === 'success') {
        setFile({
          filename: result.data.filename,
          preview_url: result.data.preview_url,
          sourceFile: selectedFile,
        });
        if (activeTab === 'cv') setCvStructuredData(null);
        else setJdStructuredData(null);

        showNotify("File đã sẵn sàng. Hãy nhấn 'Bắt đầu trích xuất'");
      }
    } catch (error) {
      showNotify("Lỗi tải file preview!");
    } finally {
      setLoading(false);
    }
  };

  const handleRunStructuring = async () => {
    if (!file && !jdText) {
      showNotify("Vui lòng chọn file hoặc nhập văn bản.");
      return;
    }

    setLoading(true);
    const formData = new FormData();
    const endpoint = activeTab === 'cv' 
      ? '/api/v1/structuring/cv/structure' 
      : (isTextInput ? '/api/v1/structuring/jd/text-structure' : '/api/v1/structuring/jd/structure');

    if (isTextInput && activeTab === 'jd') {
      formData.append('jd_text', jdText);
    } else if (file) {
      formData.append('file', file.sourceFile);
    }
    
    formData.append('extract_raw_text', 'true');

    try {
      const response = await fetch(`${API_BASE_URL}${endpoint}`, {
        method: 'POST',
        body: formData,
      });
      const result = await response.json();

      if (result.status === 'success') {
        const data = result.structured_data;
        if (activeTab === 'cv') {
          setCvStructuredData(data);
          if (onDataUpdate) onDataUpdate('cv', data);
        } else {
          setJdStructuredData(data);
          if (onDataUpdate) onDataUpdate('jd', data);
        }
        showNotify("Phân tích dữ liệu thành công!");
      } else {
        showNotify("Lỗi xử lý: " + result.message);
      }
    } catch (error) {
      showNotify("Không thể kết nối API AI.");
    } finally {
      setLoading(false);
    }
  };

  const renderStructuredSections = () => {
    const currentData = activeTab === 'cv' ? cvStructuredData : jdStructuredData;
    if (!currentData) return null;

    const labels = activeTab === 'cv' ? CV_VIEW_LABELS : JD_VIEW_LABELS;

    return (
      <div className="structured-results-grid">
        {Object.entries(labels).map(([key, label]) => {
          const content = currentData[key];
          const isMissing = !content || content === 'missing_section';

          return (
            <div key={key} className={`view-card ${isMissing ? 'missing' : ''}`}>
              <div className="view-card-header">
                <span className="view-icon">{isMissing ? '⚠️' : '✅'}</span>
                <h4>{label}</h4>
              </div>
              <div className="view-card-body">
                <p>{isMissing ? 'Thông tin không được tìm thấy.' : content}</p>
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  return (
    <div className="structuring-inline-view">
      {notification && <div className="toast-notify">{notification}</div>}

      <div className="structuring-tabs-row">
        <button 
          className={`struct-tab-btn ${activeTab === 'cv' ? 'active' : ''}`}
          onClick={() => setActiveTab('cv')}
        >
          📄 CV Analysis (10 Sections)
        </button>
        <button 
          className={`struct-tab-btn ${activeTab === 'jd' ? 'active' : ''}`}
          onClick={() => setActiveTab('jd')}
        >
          💼 JD Analysis (5 Sections)
        </button>
      </div>

      {/* Thêm class 'controls-hidden' nếu hideControls = true */}
      <div className={`structuring-workspace-grid ${hideControls ? 'controls-hidden' : ''}`}>
        
        {/* CHỈ HIỂN THỊ CỘT ĐIỀU KHIỂN NẾU hideControls LÀ FALSE */}
        {!hideControls && (
          <aside className="struct-control-panel">
            {activeTab === 'jd' && (
              <div className="mode-toggle-group">
                <button className={!isTextInput ? 'active' : ''} onClick={() => setIsTextInput(false)}>File PDF</button>
                <button className={isTextInput ? 'active' : ''} onClick={() => setIsTextInput(true)}>Text JD</button>
              </div>
            )}

            {!isTextInput ? (
              <div className="upload-container">
                <input type="file" id="file-input-inline" accept=".pdf,.doc,.docx" hidden onChange={handleFileUpload} />
                <label htmlFor="file-input-inline" className="struct-dropzone">
                  <div className="dropzone-content">
                    <span className="icon">📤</span>
                    <strong>{file ? file.filename : `Chọn tài liệu`}</strong>
                  </div>
                </label>
              </div>
            ) : (
              <textarea 
                className="struct-textarea" 
                placeholder="Nhập nội dung JD để bóc tách dữ liệu..."
                value={jdText}
                onChange={(e) => setJdText(e.target.value)}
              />
            )}

            <button 
              className="struct-action-btn" 
              onClick={handleRunStructuring}
              disabled={loading || (!file && !jdText)}
            >
              {loading ? "Đang phân tích..." : `Bắt đầu trích xuất`}
            </button>
          </aside>
        )}

        {/* Cột hiển thị kết quả bên phải */}
        <main className="struct-results-panel">
          {(activeTab === 'cv' ? cvStructuredData : jdStructuredData) ? (
            <>
              <div className="results-panel-head">
                <h3>Chi tiết các View dữ liệu cấu trúc</h3>
                <button className="clear-data-btn" onClick={() => activeTab === 'cv' ? setCvStructuredData(null) : setJdStructuredData(null)}>Xóa</button>
              </div>
              {renderStructuredSections()}
            </>
          ) : (
            <div className="struct-empty-state">
              <div className="empty-state-icon">🔬</div>
              <p>Dữ liệu bóc tách sẽ hiện ở đây sau khi bạn chạy Matching hoặc bấm Trích xuất.</p>
            </div>
          )}
        </main>
      </div>
    </div>
  );
}