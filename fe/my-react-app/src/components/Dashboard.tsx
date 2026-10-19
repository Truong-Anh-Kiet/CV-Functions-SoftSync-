import { useEffect, useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNotify } from '../hooks/useNotify';
import { useModels } from '../hooks/useModels';
import { useSavedCvs } from '../hooks/useSavedCvs';
import { useUploadedFiles } from '../hooks/useUploadedFiles';
import { useMatching } from '../hooks/useMatching';
import { useCvSearch } from '../hooks/useCvSearch';
import type { MenuType, UploadedFile } from '../types/dashboard';
import type { MatchingResult } from '../types/matching';
import type { SavedDocument } from '../types/document';
import type { SearchCvResult } from '../types/search';
import { confirmSave, renameSavedCv, deleteSavedCv } from '../services/api';
import Sidebar from './dashboard/Sidebar';
import Toast from './dashboard/Toast';
import CvStorageSection from './dashboard/sections/CvStorageSection';
import CvJdMatchingSection from './dashboard/sections/CvJdMatchingSection';
import CvRankingSection from './dashboard/sections/CvRankingSection';
import CvComparisonSection from './dashboard/sections/CvComparisonSection';
import HybridSearchingSection from './dashboard/searching/HybridSearchingSection';
import SavedCvsModal from './dashboard/modals/SavedCvsModal';
import DeleteCvConfirmModal from './dashboard/modals/DeleteCvConfirmModal';
import FileViewerModal from './dashboard/modals/FileViewerModal';
import StructuredDataModal from './dashboard/modals/StructuredDataModal';
import CrossViewRankingModal, { type CrossViewTopK } from './dashboard/modals/CrossViewRankingModal';
import CellDetailModal, { type CellDetailState } from './dashboard/modals/CellDetailModal';
import CvDetailModal from './dashboard/modals/CvDetailModal';
import { CV_VIEW_KEYS, JD_VIEW_KEYS, VIEW_LABEL_MAP } from '../constants/views';
import './Dashboard.css';

const MENU_ITEMS: MenuType[] = ['CV Storage', 'CV-JD Matching', 'CV Ranking', 'CV Comparison', 'CV Searching'];

const SIDEBAR_COLLAPSED_KEY = 'aip491_sidebar_collapsed';

export default function Dashboard() {
  const { user, logout } = useAuth();
  const [activeMenu, setActiveMenu] = useState<MenuType>('CV Storage');
  const { notification, showNotify } = useNotify();
  const { files, setFiles, loading, handlePreviewUpload: hookPreviewUpload } = useUploadedFiles();
  const {
    matchingLoading,
    matchingResults,
    setMatchingResults,
    matchingMeta,
    saveCv,
    setSaveCv,
    jdMode,
    setJdMode,
    jdText,
    setJdText,
    handleRunMatching: hookRunMatching,
  } = useMatching();
  const {
    savedCvs,
    setSavedCvs,
    savedCvsLoading,
    fetchSavedCvs,
    editingCvId,
    setEditingCvId,
    editingCvName,
    setEditingCvName,
    cancelRename: handleCancelRenameCv,
    deleteTargetCv,
    setDeleteTargetCv,
  } = useSavedCvs(showNotify);
  const { modelOptions, selectedModel, setSelectedModel } = useModels();
  const {
    searchMode, setSearchMode,
    searchJdText, setSearchJdText,
    searchJdFile,
    searchTopK, setSearchTopK,
    searchMinScore, setSearchMinScore,
    searchAutoIndex, setSearchAutoIndex,
    searchRerank, setSearchRerank,
    searchRerankTopN, setSearchRerankTopN,
    searchLoading,
    reindexLoading,
    searchResults, setSearchResults,
    searchMeta, setSearchMeta,
    reindexSummary, setReindexSummary,
    resetSearchState: resetCvSearchState,
    handleSearchJdFileChange,
    handleReindexAllCvs: hookReindexAllCvs,
    handleRunCvSearch: hookRunCvSearch,
  } = useCvSearch();

  const [selectedSources, setSelectedSources] = useState<Set<'database' | 'web'>>(new Set(['database']));

  const [showSavedCvs, setShowSavedCvs] = useState(false);
  const [structuredModalOpen, setStructuredModalOpen] = useState(false);
  const [viewingFile, setViewingFile] = useState<UploadedFile | null>(null);
  const [crossViewModalOpen, setCrossViewModalOpen] = useState(false);
  const [crossViewResult, setCrossViewResult] = useState<MatchingResult | null>(null);
  const [crossViewTopK, setCrossViewTopK] = useState<CrossViewTopK>('10');
  const [cellDetail, setCellDetail] = useState<CellDetailState | null>(null);
  const [cvDetailResult, setCvDetailResult] = useState<SearchCvResult | null>(null);
  const [sidebarCollapsed, setSidebarCollapsed] = useState<boolean>(() => {
    if (typeof window === 'undefined') return false;
    return window.localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === '1';
  });

  useEffect(() => {
    if (typeof window === 'undefined') return;
    window.localStorage.setItem(SIDEBAR_COLLAPSED_KEY, sidebarCollapsed ? '1' : '0');
  }, [sidebarCollapsed]);

  const toggleSidebar = () => setSidebarCollapsed(prev => !prev);

  useEffect(() => {
    fetchSavedCvs();
  }, [fetchSavedCvs]);

  useEffect(() => {
    if (activeMenu === 'CV Searching') {
      fetchSavedCvs();
    }
  }, [activeMenu]);

  useEffect(() => {
    if (searchMeta && searchMeta.total_cvs !== savedCvs.length) {
      setSearchMeta(null);
    }
    if (reindexSummary && reindexSummary.total_cvs !== savedCvs.length) {
      setReindexSummary(null);
    }
  }, [savedCvs.length, searchMeta, reindexSummary]);

  const handleToggleSavedCvs = async () => {
    const nextValue = !showSavedCvs;
    setShowSavedCvs(nextValue);
    if (nextValue) {
      await fetchSavedCvs();
    }
  };

  const handleViewSavedCv = (document: SavedDocument) => {
    const previewUrl = document.url || document.cloudinary_url || document.preview_url;
    if (!previewUrl) {
      showNotify('CV này chưa có đường dẫn để xem.');
      return;
    }
    setViewingFile({
      id: `saved-${document.id}`,
      filename: document.filename,
      preview_url: previewUrl,
      isSaved: true,
      category: 'CV',
      section: 'CV Storage',
    });
  };

  const handleStartRenameCv = (document: SavedDocument) => {
    setEditingCvId(document.id);
    setEditingCvName(document.filename);
  };

  const handleSaveRenameCv = async (document: SavedDocument) => {
    const nextFilename = editingCvName.trim();
    if (!nextFilename) {
      showNotify('Tên CV không được để trống.');
      return;
    }
    try {
      const result = await renameSavedCv(document.id, nextFilename);
      if (!result.ok || result.status !== 'success') {
        throw new Error(result.detail || 'Không thể đổi tên CV');
      }
      const updatedDocument: SavedDocument = result.data!;
      setSavedCvs(prev => prev.map(item => item.id === document.id ? updatedDocument : item));
      setFiles(prev => prev.map(file => (
        file.filename === document.filename
          ? { ...file, filename: updatedDocument.filename, preview_url: updatedDocument.preview_url || file.preview_url }
          : file
      )));
      handleCancelRenameCv();
      showNotify('Đã đổi tên CV.');
    } catch (error) {
      showNotify('Không thể đổi tên CV');
    }
  };

  const handleRequestDeleteSavedCv = (document: SavedDocument) => {
    handleCancelRenameCv();
    setDeleteTargetCv(document);
  };

  const handleCancelDeleteSavedCv = () => {
    setDeleteTargetCv(null);
  };

  const handleConfirmDeleteSavedCv = async () => {
    if (!deleteTargetCv) return;
    const document = deleteTargetCv;
    try {
      const result = await deleteSavedCv(document.id);
      if (!result.ok || result.status !== 'success') {
        throw new Error(result.detail || 'Không thể xóa CV');
      }
      setSavedCvs(prev => prev.filter(item => item.id !== document.id));
      setFiles(prev => prev.filter(file => !(file.filename === document.filename && file.isSaved)));
      setSearchResults(prev => prev.filter(item => item.id !== document.id));
      setSearchMeta(null);
      setReindexSummary(null);
      setDeleteTargetCv(null);
      showNotify('Đã xóa CV khỏi kho lưu trữ.');
      await fetchSavedCvs();
    } catch (error) {
      showNotify('Không thể xóa CV');
    }
  };

  const handlePreviewUpload = (e: React.ChangeEvent<HTMLInputElement>, category: 'CV' | 'JD') =>
    hookPreviewUpload(e, category, {
      activeMenu,
      onSuccess: () => setMatchingResults([]),
      onError: showNotify,
    });

  const handleConfirmSave = async (filename: string, category: string) => {
    try {
      showNotify("Đang lưu vào hệ thống, vui lòng đợi...");
      const result = await confirmSave(filename, category);
      if (result.status === 'success') {
        showNotify(`Thành công! Đã lưu ${filename} vào Database.`);
        setFiles(prev => prev.map(f => f.filename === filename ? { ...f, isSaved: true } : f));
        resetCvSearchState();
        await fetchSavedCvs();
      } else {
        showNotify("Lỗi: " + (result.detail || "Không thể lưu file"));
      }
    } catch (error) {
      showNotify("Lỗi kết nối server khi lưu trữ!");
    }
  };

  const handleRunMatching = () => hookRunMatching({
    files,
    activeMenu,
    modelId: selectedModel,
    showNotify,
    onComplete: fetchSavedCvs,
  });

  const handleReindexAllCvs = () => hookReindexAllCvs({
    modelId: selectedModel,
    showNotify,
    onComplete: fetchSavedCvs,
  });

  const handleRunCvSearch = () => hookRunCvSearch({
    modelId: selectedModel,
    showNotify,
  });

  const removeFile = (id: string) => {
    setFiles(prev => prev.filter(f => f.id !== id));
    setMatchingResults([]);
  };

  const closeSavedCvsModal = () => {
    setShowSavedCvs(false);
    handleCancelRenameCv();
  };

  const handleViewSearchCv = (result: SearchCvResult) => {
    const previewUrl = result.preview_url || result.cloudinary_url;
    if (!previewUrl) {
      showNotify('CV này chưa có đường dẫn để xem.');
      return;
    }
    setViewingFile({
      id: `search-${result.id}`,
      filename: result.filename,
      preview_url: previewUrl,
      isSaved: true,
      category: 'CV',
      section: 'CV Searching',
    });
  };

  const handleViewDbCv = (result: SearchCvResult) => {
    setCvDetailResult(result);
  };

  const handleOpenCrossView = (result: MatchingResult) => {
    setCrossViewResult(result);
    setCrossViewTopK('10');
    setCrossViewModalOpen(true);
  };

  const extractStructuredField = (structured: unknown, key: string): string => {
    if (!structured || typeof structured !== 'object') return '(Không có dữ liệu)';
    const val = (structured as Record<string, unknown>)[key];
    if (val === undefined || val === null) return '(Không có trường này)';
    if (typeof val === 'string') return val.trim() || '(Trống)';
    if (Array.isArray(val)) return val.join('\n') || '(Trống)';
    return String(val);
  };

  const handleHeatmapCellClick = (
    rowIndex: number,
    colIndex: number,
    score: number,
    result: MatchingResult,
  ) => {
    const cvKey = CV_VIEW_KEYS[rowIndex];
    const jdKey = JD_VIEW_KEYS[colIndex];
    if (!cvKey || !jdKey) return;
    setCellDetail({
      cvKey,
      jdKey,
      cvLabel: VIEW_LABEL_MAP[cvKey] ?? cvKey,
      jdLabel: VIEW_LABEL_MAP[jdKey] ?? jdKey,
      score,
      cvEvidence: extractStructuredField(result.cv_structured, cvKey),
      jdEvidence: extractStructuredField(result.jd_structured, jdKey),
      rowIndex,
      colIndex,
    });
  };

  const matchingCv = files.find(f => f.category === 'CV' && f.section === 'CV-JD Matching');
  const matchingJd = files.find(f => f.category === 'JD' && f.section === 'CV-JD Matching');
  const primaryMatchingResult = matchingResults[0];

  const currentCvTotal = savedCvs.length;
  const currentSearchMeta = searchMeta?.total_cvs === currentCvTotal ? searchMeta : null;
  const currentReindexSummary = reindexSummary?.total_cvs === currentCvTotal ? reindexSummary : null;

  return (
    <div className="dashboard-layout">
      <Sidebar
        menuItems={MENU_ITEMS}
        activeMenu={activeMenu}
        onChangeMenu={setActiveMenu}
        userName={user?.name}
        userEmail={user?.email}
        onLogout={logout}
        collapsed={sidebarCollapsed}
        onToggleCollapse={toggleSidebar}
      />

      <main className="main-content">
        <header className={`content-header ${activeMenu === 'CV Searching' ? 'content-header-searching' : ''}`}>
          <h1>{activeMenu}</h1>
        </header>
        <Toast message={notification} />
        <div className="content-body">
          {activeMenu === 'CV Storage' && (
            <CvStorageSection
              files={files}
              loading={loading}
              activeMenu={activeMenu}
              savedCvsCount={savedCvs.length}
              onPreviewUpload={handlePreviewUpload}
              onPreview={setViewingFile}
              onConfirmSave={handleConfirmSave}
              onRemove={removeFile}
              onToggleSavedCvs={handleToggleSavedCvs}
            />
          )}

          {activeMenu === 'CV-JD Matching' && (
            <CvJdMatchingSection
              matchingCv={matchingCv}
              matchingJd={matchingJd}
              primaryMatchingResult={primaryMatchingResult}
              matchingLoading={matchingLoading}
              saveCv={saveCv}
              setSaveCv={setSaveCv}
              jdMode={jdMode}
              setJdMode={setJdMode}
              jdText={jdText}
              setJdText={setJdText}
              matchingMeta={matchingMeta}
              modelOptions={modelOptions}
              selectedModel={selectedModel}
              setSelectedModel={setSelectedModel}
              onPreviewUpload={handlePreviewUpload}
              onRemove={removeFile}
              onRunMatching={handleRunMatching}
              onOpenCrossView={handleOpenCrossView}
              onOpenStructured={() => setStructuredModalOpen(true)}
              selectedHeatmapCell={cellDetail ? { rowIndex: cellDetail.rowIndex, colIndex: cellDetail.colIndex } : null}
              onHeatmapCellClick={handleHeatmapCellClick}
            />
          )}

          {activeMenu === 'CV Ranking' && (
            <CvRankingSection
              modelOptions={modelOptions}
              selectedModel={selectedModel}
              setSelectedModel={setSelectedModel}
              showNotify={showNotify}
            />
          )}

          {activeMenu === 'CV Comparison' && (
            <CvComparisonSection
              modelOptions={modelOptions}
              selectedModel={selectedModel}
              setSelectedModel={setSelectedModel}
              showNotify={showNotify}
            />
          )}

          {activeMenu === 'CV Searching' && (
            <HybridSearchingSection
              searchMode={searchMode}
              setSearchMode={setSearchMode}
              searchJdText={searchJdText}
              setSearchJdText={setSearchJdText}
              searchJdFile={searchJdFile}
              searchTopK={searchTopK}
              setSearchTopK={setSearchTopK}
              searchMinScore={searchMinScore}
              setSearchMinScore={setSearchMinScore}
              searchAutoIndex={searchAutoIndex}
              setSearchAutoIndex={setSearchAutoIndex}
              searchRerank={searchRerank}
              setSearchRerank={setSearchRerank}
              searchRerankTopN={searchRerankTopN}
              setSearchRerankTopN={setSearchRerankTopN}
              searchLoading={searchLoading}
              reindexLoading={reindexLoading}
              searchResults={searchResults}
              searchMeta={searchMeta}
              currentSearchMeta={currentSearchMeta}
              currentReindexSummary={currentReindexSummary}
              currentCvTotal={currentCvTotal}
              savedCvsLength={savedCvs.length}
              modelOptions={modelOptions}
              selectedModel={selectedModel}
              setSelectedModel={setSelectedModel}
              onSearchJdFileChange={handleSearchJdFileChange}
              onRunCvSearch={handleRunCvSearch}
              onReindexAllCvs={handleReindexAllCvs}
              onViewSearchCv={handleViewSearchCv}
              onViewWebCv={handleViewSearchCv}
              onViewDbCv={handleViewDbCv}
              showNotify={showNotify}
              selectedSources={selectedSources}
              setSelectedSources={setSelectedSources}
            />
          )}
        </div>
      </main>

      <SavedCvsModal
        open={showSavedCvs}
        onClose={closeSavedCvsModal}
        savedCvs={savedCvs}
        savedCvsLoading={savedCvsLoading}
        editingCvId={editingCvId}
        editingCvName={editingCvName}
        onEditingNameChange={setEditingCvName}
        onStartRename={handleStartRenameCv}
        onCancelRename={handleCancelRenameCv}
        onSaveRename={handleSaveRenameCv}
        onView={handleViewSavedCv}
        onRequestDelete={handleRequestDeleteSavedCv}
      />

      <DeleteCvConfirmModal
        target={deleteTargetCv}
        onCancel={handleCancelDeleteSavedCv}
        onConfirm={handleConfirmDeleteSavedCv}
      />

      <FileViewerModal file={viewingFile} onClose={() => setViewingFile(null)} />

      <StructuredDataModal
        open={structuredModalOpen}
        onClose={() => setStructuredModalOpen(false)}
        result={primaryMatchingResult ?? null}
      />

      <CrossViewRankingModal
        open={crossViewModalOpen}
        result={crossViewResult}
        topK={crossViewTopK}
        onTopKChange={setCrossViewTopK}
        onClose={() => setCrossViewModalOpen(false)}
      />

      <CellDetailModal detail={cellDetail} onClose={() => setCellDetail(null)} />

      <CvDetailModal
        result={cvDetailResult}
        profile={null}
        searchMeta={searchMeta}
        onClose={() => setCvDetailResult(null)}
      />
    </div>
  );
}
