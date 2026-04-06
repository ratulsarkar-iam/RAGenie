import { useState, useEffect } from 'react';
import { Upload, BarChart3, TrendingUp, Brain, Eye, Trash2, FileSpreadsheet, FolderOpen, File } from 'lucide-react';
import { useTheme } from '../contexts/ThemeContext';
import { analyticsAPI, DatasetInfo, AnalysisResult } from '../api/analytics';
// @ts-ignore - will be installed
import Plot from 'react-plotly.js';
// @ts-ignore - will be installed
import ReactMarkdown from 'react-markdown';

interface AnalyticsProps {
  onDocumentAdded?: () => void;
}

export default function Analytics({ onDocumentAdded }: AnalyticsProps) {
  const { theme } = useTheme();
  const [datasets, setDatasets] = useState<DatasetInfo[]>([]);
  const [selectedDataset, setSelectedDataset] = useState<DatasetInfo | null>(null);
  const [uploading, setUploading] = useState(false);
  const [analyzing, setAnalyzing] = useState(false);
  const [analysisResults, setAnalysisResults] = useState<AnalysisResult | null>(null);
  const [activeTab, setActiveTab] = useState<'upload' | 'analyze' | 'visualize' | 'predict'>('upload');
  const [filePath, setFilePath] = useState('');
  const [folderPath, setFolderPath] = useState('');
  const [filePattern, setFilePattern] = useState('*');

  useEffect(() => {
    loadDatasets();
  }, []);

  const loadDatasets = async () => {
    try {
      const response = await analyticsAPI.listDatasets();
      setDatasets(response.datasets);
    } catch (error) {
      console.error('Failed to load datasets:', error);
    }
  };

  const handleFileUpload = async (event: React.ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0];
    if (!file) return;

    setUploading(true);
    try {
      const result = await analyticsAPI.uploadDataFile(file);
      await loadDatasets();
      setSelectedDataset(result);
      setActiveTab('analyze');
      // Trigger document list refresh in Sidebar
      if (result.in_page_index && onDocumentAdded) {
        onDocumentAdded();
      }
    } catch (error: any) {
      alert(`Upload failed: ${error.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleSelectFile = () => {
    console.log('Select File button clicked');
    // Trigger the hidden file input
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.csv,.xlsx,.xls,.json,.tsv,.txt,.pdf';
    input.style.display = 'none';
    
    input.onchange = async (e: Event) => {
      const file = (e.target as HTMLInputElement).files?.[0];
      if (!file) {
        console.log('No file selected');
        document.body.removeChild(input);
        return;
      }

      console.log('File selected:', file.name);
      setUploading(true);
      try {
        const result = await analyticsAPI.uploadDataFile(file);
        await loadDatasets();
        setSelectedDataset(result);
        setActiveTab('analyze');
        // Trigger document list refresh in Sidebar
        if (result.in_page_index && onDocumentAdded) {
          onDocumentAdded();
        }
      } catch (error: any) {
        alert(`Failed to upload file: ${error.message}`);
      } finally {
        setUploading(false);
        document.body.removeChild(input);
      }
    };
    
    // Append to body, click, then remove
    document.body.appendChild(input);
    input.click();
  };

  const handleRegisterFilePath = async () => {
    if (!filePath.trim()) {
      alert('Please enter a file path');
      return;
    }

    setUploading(true);
    try {
      const result = await analyticsAPI.registerFilePath(filePath);
      await loadDatasets();
      setSelectedDataset(result);
      setFilePath('');
      setActiveTab('analyze');
      // Trigger document list refresh in Sidebar
      if (result.in_page_index && onDocumentAdded) {
        onDocumentAdded();
      }
    } catch (error: any) {
      alert(`Failed to register file: ${error.message}`);
    } finally {
      setUploading(false);
    }
  };

  const handleSelectFolder = () => {
    console.log('Select Folder button clicked');
    // Trigger the hidden folder input
    const input = document.createElement('input');
    input.type = 'file';
    input.style.display = 'none';
    // @ts-ignore - webkitdirectory is supported in most browsers
    input.webkitdirectory = true;
    // @ts-ignore
    input.directory = true;
    input.multiple = true;
    
    input.onchange = async (e: Event) => {
      const files = (e.target as HTMLInputElement).files;
      if (!files || files.length === 0) {
        console.log('No files selected from folder');
        document.body.removeChild(input);
        return;
      }

      console.log(`Selected ${files.length} files from folder`);
      setUploading(true);
      let uploadedCount = 0;
      const errors: string[] = [];

      try {
        for (let i = 0; i < files.length; i++) {
          const file = files[i];
          const ext = file.name.split('.').pop()?.toLowerCase();
          
          // Check if file extension is supported
          if (ext && ['csv', 'xlsx', 'xls', 'json', 'tsv', 'txt', 'pdf'].includes(ext)) {
            try {
              await analyticsAPI.uploadDataFile(file);
              uploadedCount++;
            } catch (error: any) {
              errors.push(`${file.name}: ${error.message}`);
            }
          }
        }
        
        await loadDatasets();
        
        if (uploadedCount > 0) {
          alert(`Successfully uploaded ${uploadedCount} file(s)${errors.length > 0 ? ` (${errors.length} errors)` : ''}`);
        } else {
          alert('No supported files found in the selected folder');
        }
        
        if (errors.length > 0) {
          console.error('Upload errors:', errors);
        }
      } catch (error: any) {
        alert(`Failed to process folder: ${error.message}`);
      } finally {
        setUploading(false);
        document.body.removeChild(input);
      }
    };
    
    // Append to body, click, then it will be removed after selection
    document.body.appendChild(input);
    input.click();
  };

  const handleRegisterFolder = async () => {
    if (!folderPath.trim()) {
      alert('Please enter a folder path');
      return;
    }

    setUploading(true);
    try {
      const result = await analyticsAPI.registerFolderPath(folderPath, filePattern);
      await loadDatasets();
      
      if (result.registered_count > 0) {
        alert(`Successfully registered ${result.registered_count} file(s)${result.error_count > 0 ? ` (${result.error_count} errors)` : ''}`);
        setFolderPath('');
        setFilePattern('*');
        // Trigger document list refresh in Sidebar
        if (onDocumentAdded) {
          onDocumentAdded();
        }
      } else {
        const message = result.message || 'No files found or all files failed to load';
        alert(message);
      }
      
      if (result.errors && result.errors.length > 0) {
        console.error('Errors:', result.errors);
      }
    } catch (error: any) {
      alert(`Failed to register folder: ${error.message || String(error)}`);
    } finally {
      setUploading(false);
    }
  };

  const handleCompleteAnalysis = async () => {
    if (!selectedDataset) return;

    setAnalyzing(true);
    try {
      const result = await analyticsAPI.completeAnalysis(selectedDataset.dataset_id);
      setAnalysisResults(result);
      setActiveTab('visualize');
    } catch (error: any) {
      alert(`Analysis failed: ${error.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  const handleDeleteDataset = async (datasetId: string) => {
    try {
      await analyticsAPI.deleteDataset(datasetId);
      await loadDatasets();
      if (selectedDataset?.dataset_id === datasetId) {
        setSelectedDataset(null);
        setAnalysisResults(null);
      }
    } catch (error: any) {
      alert(`Delete failed: ${error.message}`);
    }
  };

  const handlePredictFuture = async (targetColumn: string) => {
    if (!selectedDataset) return;

    setAnalyzing(true);
    try {
      const result = await analyticsAPI.predictFuture(selectedDataset.dataset_id, targetColumn);
      setAnalysisResults(result);
    } catch (error: any) {
      alert(`Prediction failed: ${error.message}`);
    } finally {
      setAnalyzing(false);
    }
  };

  return (
    <div className={`flex-1 flex flex-col overflow-hidden ${
      theme === 'dark' ? 'bg-slate-900' : 'bg-gray-50'
    }`}>
      {/* Header */}
      <div className={`px-6 py-4 border-b ${
        theme === 'dark' ? 'bg-slate-800 border-slate-700' : 'bg-white border-gray-200'
      }`}>
        <h2 className={`text-2xl font-bold flex items-center gap-2 ${
          theme === 'dark' ? 'text-white' : 'text-slate-900'
        }`}>
          <BarChart3 className="w-7 h-7" />
          Data Analytics
        </h2>
        <p className={`text-sm mt-1 ${
          theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
        }`}>
          Upload data, analyze, predict, and visualize insights
        </p>
      </div>

      {/* Tabs */}
      <div className={`flex gap-2 px-6 py-3 border-b ${
        theme === 'dark' ? 'bg-slate-800/50 border-slate-700' : 'bg-gray-100 border-gray-200'
      }`}>
        {[
          { id: 'upload', label: 'Upload Data', icon: Upload },
          { id: 'analyze', label: 'Analyze', icon: Brain },
          { id: 'visualize', label: 'Visualize', icon: Eye },
          { id: 'predict', label: 'Predict', icon: TrendingUp },
        ].map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id as any)}
            className={`flex items-center gap-2 px-4 py-2 rounded-lg font-medium transition-all ${
              activeTab === tab.id
                ? theme === 'dark'
                  ? 'bg-blue-600 text-white'
                  : 'bg-blue-500 text-white'
                : theme === 'dark'
                ? 'bg-slate-700 text-slate-300 hover:bg-slate-600'
                : 'bg-white text-slate-700 hover:bg-gray-200'
            }`}
          >
            <tab.icon className="w-4 h-4" />
            {tab.label}
          </button>
        ))}
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-6">
        {activeTab === 'upload' && (
          <div className="max-w-4xl mx-auto">
            {/* Upload Section */}
            <div className={`rounded-xl p-8 border-2 border-dashed ${
              theme === 'dark'
                ? 'bg-slate-800 border-slate-600'
                : 'bg-white border-gray-300'
            }`}>
              <div className="text-center">
                <FileSpreadsheet className={`w-16 h-16 mx-auto mb-4 ${
                  theme === 'dark' ? 'text-slate-400' : 'text-slate-500'
                }`} />
                <h3 className={`text-xl font-semibold mb-2 ${
                  theme === 'dark' ? 'text-white' : 'text-slate-900'
                }`}>
                  Upload Your Data
                </h3>
                <p className={`mb-6 ${
                  theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                }`}>
                  Supported formats: CSV, Excel (.xlsx, .xls), JSON, TSV, TXT, PDF
                </p>
                <label className={`inline-flex items-center gap-2 px-6 py-3 rounded-lg font-medium cursor-pointer transition-all ${
                  theme === 'dark'
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-blue-500 hover:bg-blue-600 text-white'
                }`}>
                  <Upload className="w-5 h-5" />
                  {uploading ? 'Uploading...' : 'Choose File'}
                  <input
                    type="file"
                    className="hidden"
                    accept=".csv,.xlsx,.xls,.json,.tsv,.txt,.pdf"
                    onChange={handleFileUpload}
                    disabled={uploading}
                  />
                </label>
              </div>
            </div>

            {/* File Path Registration */}
            <div className={`mt-6 rounded-xl p-6 ${
              theme === 'dark' ? 'bg-slate-800' : 'bg-white'
            }`}>
              <div className="flex items-center gap-2 mb-4">
                <File className={`w-5 h-5 ${theme === 'dark' ? 'text-blue-400' : 'text-blue-600'}`} />
                <h3 className={`text-lg font-semibold ${
                  theme === 'dark' ? 'text-white' : 'text-slate-900'
                }`}>
                  Register File Path
                </h3>
              </div>
              <p className={`text-sm mb-4 ${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>
                Select a file or enter its absolute path
              </p>
              <div className="flex gap-3">
                <input
                  type="text"
                  value={filePath}
                  onChange={(e) => setFilePath(e.target.value)}
                  placeholder="/path/to/your/data.csv"
                  className={`flex-1 px-4 py-2 rounded-lg border ${
                    theme === 'dark'
                      ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500'
                      : 'bg-white border-gray-300 text-slate-900 placeholder-slate-400'
                  } focus:outline-none focus:ring-2 focus:ring-blue-500`}
                />
                <button
                  onClick={handleSelectFile}
                  disabled={uploading}
                  className={`px-6 py-2 rounded-lg font-medium transition-all whitespace-nowrap ${
                    theme === 'dark'
                      ? 'bg-green-600 hover:bg-green-700 text-white disabled:bg-slate-700 disabled:text-slate-500'
                      : 'bg-green-500 hover:bg-green-600 text-white disabled:bg-gray-300 disabled:text-gray-500'
                  }`}
                >
                  Select File
                </button>
                <button
                  onClick={handleRegisterFilePath}
                  disabled={uploading || !filePath.trim()}
                  className={`px-6 py-2 rounded-lg font-medium transition-all ${
                    theme === 'dark'
                      ? 'bg-blue-600 hover:bg-blue-700 text-white disabled:bg-slate-700 disabled:text-slate-500'
                      : 'bg-blue-500 hover:bg-blue-600 text-white disabled:bg-gray-300 disabled:text-gray-500'
                  }`}
                >
                  {uploading ? 'Registering...' : 'Register'}
                </button>
              </div>
            </div>

            {/* Folder Path Registration */}
            <div className={`mt-6 rounded-xl p-6 ${
              theme === 'dark' ? 'bg-slate-800' : 'bg-white'
            }`}>
              <div className="flex items-center gap-2 mb-4">
                <FolderOpen className={`w-5 h-5 ${theme === 'dark' ? 'text-purple-400' : 'text-purple-600'}`} />
                <h3 className={`text-lg font-semibold ${
                  theme === 'dark' ? 'text-white' : 'text-slate-900'
                }`}>
                  Register Folder
                </h3>
              </div>
              <p className={`text-sm mb-4 ${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>
                Select a folder or enter its absolute path
              </p>
              <div className="space-y-3">
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={folderPath}
                    onChange={(e) => setFolderPath(e.target.value)}
                    placeholder="/path/to/folder"
                    className={`flex-1 px-4 py-2 rounded-lg border ${
                      theme === 'dark'
                        ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500'
                        : 'bg-white border-gray-300 text-slate-900 placeholder-slate-400'
                    } focus:outline-none focus:ring-2 focus:ring-blue-500`}
                  />
                  <button
                    onClick={handleSelectFolder}
                    disabled={uploading}
                    className={`px-6 py-2 rounded-lg font-medium transition-all whitespace-nowrap ${
                      theme === 'dark'
                        ? 'bg-green-600 hover:bg-green-700 text-white disabled:bg-slate-700 disabled:text-slate-500'
                        : 'bg-green-500 hover:bg-green-600 text-white disabled:bg-gray-300 disabled:text-gray-500'
                    }`}
                  >
                    Select Folder
                  </button>
                </div>
                <div className="flex gap-3">
                  <input
                    type="text"
                    value={filePattern}
                    onChange={(e) => setFilePattern(e.target.value)}
                    placeholder="File pattern (e.g., *.csv, data_*.json)"
                    className={`flex-1 px-4 py-2 rounded-lg border ${
                      theme === 'dark'
                        ? 'bg-slate-700 border-slate-600 text-white placeholder-slate-500'
                        : 'bg-white border-gray-300 text-slate-900 placeholder-slate-400'
                    } focus:outline-none focus:ring-2 focus:ring-blue-500`}
                  />
                  <button
                    onClick={handleRegisterFolder}
                    disabled={uploading || !folderPath.trim()}
                    className={`px-6 py-2 rounded-lg font-medium transition-all ${
                      theme === 'dark'
                        ? 'bg-purple-600 hover:bg-purple-700 text-white disabled:bg-slate-700 disabled:text-slate-500'
                        : 'bg-purple-500 hover:bg-purple-600 text-white disabled:bg-gray-300 disabled:text-gray-500'
                    }`}
                  >
                    {uploading ? 'Loading...' : 'Load Folder'}
                  </button>
                </div>
                <p className={`text-xs ${
                  theme === 'dark' ? 'text-slate-500' : 'text-slate-500'
                }`}>
                  Use "Select Folder" for easy browsing, or enter path manually with pattern filter
                </p>
              </div>
            </div>

            {/* Datasets List - Compact Table View */}
            {datasets.length > 0 && (
              <div className={`mt-6 rounded-xl overflow-hidden ${
                theme === 'dark' ? 'bg-slate-800' : 'bg-white'
              }`}>
                <div className={`px-6 py-4 border-b ${
                  theme === 'dark' ? 'border-slate-700' : 'border-gray-200'
                }`}>
                  <h3 className={`text-lg font-semibold ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>
                    Your Datasets ({datasets.length})
                  </h3>
                </div>
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead className={`text-xs uppercase ${
                      theme === 'dark' ? 'bg-slate-700 text-slate-400' : 'bg-gray-50 text-gray-600'
                    }`}>
                      <tr>
                        <th className="px-6 py-3 text-left">Filename</th>
                        <th className="px-6 py-3 text-left">Location</th>
                        <th className="px-6 py-3 text-left">Rows</th>
                        <th className="px-6 py-3 text-left">Cols</th>
                        <th className="px-6 py-3 text-left">In Index</th>
                        <th className="px-6 py-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className={`divide-y ${
                      theme === 'dark' ? 'divide-slate-700' : 'divide-gray-200'
                    }`}>
                      {datasets.map((dataset) => (
                        <tr
                          key={dataset.dataset_id}
                          className={`${
                            selectedDataset?.dataset_id === dataset.dataset_id
                              ? theme === 'dark'
                                ? 'bg-blue-900/20'
                                : 'bg-blue-50'
                              : theme === 'dark'
                              ? 'hover:bg-slate-700/50'
                              : 'hover:bg-gray-50'
                          } transition-colors`}
                        >
                          <td className={`px-6 py-3 ${
                            theme === 'dark' ? 'text-white' : 'text-slate-900'
                          }`}>
                            <div className="flex items-center gap-2">
                              <FileSpreadsheet className="w-4 h-4 text-blue-500" />
                              <span className="font-medium truncate max-w-xs" title={dataset.filename}>
                                {dataset.filename}
                              </span>
                            </div>
                          </td>
                          <td className="px-6 py-3">
                            {dataset.file_path?.includes('/uploads/') ? (
                              <span 
                                className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                                  theme === 'dark'
                                    ? 'bg-amber-900/30 text-amber-400'
                                    : 'bg-amber-100 text-amber-800'
                                }`}
                                title="File copied to data/analytics/uploads (browser upload)"
                              >
                                Copy
                              </span>
                            ) : (
                              <span 
                                className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                                  theme === 'dark'
                                    ? 'bg-blue-900/30 text-blue-400'
                                    : 'bg-blue-100 text-blue-800'
                                }`}
                                title={`Original file at: ${dataset.file_path}`}
                              >
                                Original
                              </span>
                            )}
                          </td>
                          <td className={`px-6 py-3 text-sm ${
                            theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
                          }`}>
                            {dataset.shape[0].toLocaleString()}
                          </td>
                          <td className={`px-6 py-3 text-sm ${
                            theme === 'dark' ? 'text-slate-300' : 'text-slate-600'
                          }`}>
                            {dataset.shape[1]}
                          </td>
                          <td className="px-6 py-3">
                            {dataset.in_page_index ? (
                              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                                theme === 'dark'
                                  ? 'bg-green-900/30 text-green-400'
                                  : 'bg-green-100 text-green-800'
                              }`}>
                                ✓ Yes
                              </span>
                            ) : (
                              <span className={`inline-flex items-center px-2 py-1 rounded-full text-xs font-medium ${
                                theme === 'dark'
                                  ? 'bg-slate-700 text-slate-400'
                                  : 'bg-gray-100 text-gray-600'
                              }`}>
                                ✗ No
                              </span>
                            )}
                          </td>
                          <td className="px-6 py-3 text-right">
                            <div className="flex gap-2 justify-end">
                              <button
                                onClick={() => {
                                  setSelectedDataset(dataset);
                                  setActiveTab('analyze');
                                }}
                                className={`px-3 py-1 rounded text-sm font-medium ${
                                  theme === 'dark'
                                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                                    : 'bg-blue-500 hover:bg-blue-600 text-white'
                                }`}
                              >
                                Analyze
                              </button>
                              <button
                                onClick={() => handleDeleteDataset(dataset.dataset_id)}
                                className={`p-1.5 rounded ${
                                  theme === 'dark'
                                    ? 'bg-red-600 hover:bg-red-700 text-white'
                                    : 'bg-red-500 hover:bg-red-600 text-white'
                                }`}
                              >
                                <Trash2 className="w-4 h-4" />
                              </button>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'analyze' && selectedDataset && (
          <div className="max-w-6xl mx-auto">
            <div className={`rounded-xl p-6 mb-6 ${
              theme === 'dark' ? 'bg-slate-800' : 'bg-white'
            }`}>
              <h3 className={`text-lg font-semibold mb-4 ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>
                Dataset: {selectedDataset.filename}
              </h3>
              <div className="grid grid-cols-3 gap-4 mb-6">
                <div className={`p-4 rounded-lg ${
                  theme === 'dark' ? 'bg-slate-700' : 'bg-gray-100'
                }`}>
                  <p className={`text-sm ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>Rows</p>
                  <p className={`text-2xl font-bold ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>{selectedDataset.shape[0]}</p>
                </div>
                <div className={`p-4 rounded-lg ${
                  theme === 'dark' ? 'bg-slate-700' : 'bg-gray-100'
                }`}>
                  <p className={`text-sm ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>Columns</p>
                  <p className={`text-2xl font-bold ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>{selectedDataset.shape[1]}</p>
                </div>
                <div className={`p-4 rounded-lg ${
                  theme === 'dark' ? 'bg-slate-700' : 'bg-gray-100'
                }`}>
                  <p className={`text-sm ${
                    theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                  }`}>Numeric Columns</p>
                  <p className={`text-2xl font-bold ${
                    theme === 'dark' ? 'text-white' : 'text-slate-900'
                  }`}>{selectedDataset.info?.numeric_columns?.length || 0}</p>
                </div>
              </div>
              <button
                onClick={handleCompleteAnalysis}
                disabled={analyzing}
                className={`w-full py-3 rounded-lg font-medium flex items-center justify-center gap-2 ${
                  theme === 'dark'
                    ? 'bg-blue-600 hover:bg-blue-700 text-white'
                    : 'bg-blue-500 hover:bg-blue-600 text-white'
                } disabled:opacity-50`}
              >
                <Brain className="w-5 h-5" />
                {analyzing ? 'Analyzing...' : 'Run Complete Analysis'}
              </button>
            </div>

            {analysisResults?.insights && (
              <div className={`rounded-xl p-6 ${
                theme === 'dark' ? 'bg-slate-800' : 'bg-white'
              }`}>
                <h3 className={`text-lg font-semibold mb-4 ${
                  theme === 'dark' ? 'text-white' : 'text-slate-900'
                }`}>
                  Key Insights
                </h3>
                <div className="grid grid-cols-2 gap-4">
                  <div className={`p-4 rounded-lg ${
                    theme === 'dark' ? 'bg-slate-700' : 'bg-gray-100'
                  }`}>
                    <p className={`text-sm ${
                      theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                    }`}>Missing Data</p>
                    <p className={`text-xl font-bold ${
                      theme === 'dark' ? 'text-white' : 'text-slate-900'
                    }`}>{analysisResults.insights.missing_data_percentage?.toFixed(2)}%</p>
                  </div>
                  <div className={`p-4 rounded-lg ${
                    theme === 'dark' ? 'bg-slate-700' : 'bg-gray-100'
                  }`}>
                    <p className={`text-sm ${
                      theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                    }`}>Duplicate Rows</p>
                    <p className={`text-xl font-bold ${
                      theme === 'dark' ? 'text-white' : 'text-slate-900'
                    }`}>{analysisResults.insights.duplicate_rows}</p>
                  </div>
                </div>
              </div>
            )}
          </div>
        )}

        {activeTab === 'visualize' && analysisResults?.visualizations && (
          <div className="max-w-7xl mx-auto">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
              {analysisResults.visualizations.map((plot: any, index: number) => (
                <div
                  key={index}
                  className={`rounded-xl p-6 ${
                    theme === 'dark' ? 'bg-slate-800' : 'bg-white'
                  }`}
                >
                  <Plot
                    data={JSON.parse(plot.plotly_json).data}
                    layout={{
                      ...JSON.parse(plot.plotly_json).layout,
                      paper_bgcolor: theme === 'dark' ? '#1e293b' : '#ffffff',
                      plot_bgcolor: theme === 'dark' ? '#1e293b' : '#ffffff',
                      font: { color: theme === 'dark' ? '#e2e8f0' : '#1e293b' },
                    }}
                    config={{ responsive: true }}
                    style={{ width: '100%', height: '400px' }}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {activeTab === 'predict' && selectedDataset && (
          <div className="max-w-4xl mx-auto">
            <div className={`rounded-xl p-6 ${
              theme === 'dark' ? 'bg-slate-800' : 'bg-white'
            }`}>
              <h3 className={`text-lg font-semibold mb-4 ${
                theme === 'dark' ? 'text-white' : 'text-slate-900'
              }`}>
                Predict Future Values
              </h3>
              <p className={`mb-4 ${
                theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
              }`}>
                Select a numeric column to predict future trends
              </p>
              <div className="space-y-3">
                {selectedDataset.info?.numeric_columns?.map((col: string) => (
                  <button
                    key={col}
                    onClick={() => handlePredictFuture(col)}
                    disabled={analyzing}
                    className={`w-full p-4 rounded-lg text-left font-medium transition-all ${
                      theme === 'dark'
                        ? 'bg-slate-700 hover:bg-slate-600 text-white'
                        : 'bg-gray-100 hover:bg-gray-200 text-slate-900'
                    } disabled:opacity-50`}
                  >
                    {col}
                  </button>
                ))}
              </div>
            </div>

            {analysisResults?.plot && (
              <div className={`mt-6 rounded-xl p-6 ${
                theme === 'dark' ? 'bg-slate-800' : 'bg-white'
              }`}>
                <Plot
                  data={JSON.parse(analysisResults.plot.plotly_json).data}
                  layout={{
                    ...JSON.parse(analysisResults.plot.plotly_json).layout,
                    paper_bgcolor: theme === 'dark' ? '#1e293b' : '#ffffff',
                    plot_bgcolor: theme === 'dark' ? '#1e293b' : '#ffffff',
                    font: { color: theme === 'dark' ? '#e2e8f0' : '#1e293b' },
                  }}
                  config={{ responsive: true }}
                  style={{ width: '100%', height: '500px' }}
                />
                {analysisResults.results && (
                  <div className="mt-4">
                    <p className={`text-sm ${
                      theme === 'dark' ? 'text-slate-400' : 'text-slate-600'
                    }`}>
                      Trend: <span className="font-semibold">{analysisResults.results.trend}</span>
                    </p>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
