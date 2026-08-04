import { authHeader } from './authToken';

const API_BASE_URL = 'http://localhost:8000';

function authFetch(url: string, options: RequestInit = {}): Promise<Response> {
  return fetch(url, {
    ...options,
    headers: { ...(options.headers || {}), ...authHeader() },
  });
}

export interface DatasetInfo {
  dataset_id: string;
  filename: string;
  file_path?: string;
  shape: number[];
  columns: string[];
  info?: any;
  preview?: any[];
  in_page_index?: boolean;
}

export interface AnalysisResult {
  status: string;
  dataset_id: string;
  statistics?: any;
  insights?: any;
  outliers?: any;
  results?: any;
  plot?: any;
  plots?: any[];
  visualizations?: any[];
  summary?: any;
}

export const analyticsAPI = {
  async uploadDataFile(file: File): Promise<DatasetInfo> {
    const formData = new FormData();
    formData.append('file', file);

    const response = await authFetch(`${API_BASE_URL}/analytics/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to upload file');
    }

    return response.json();
  },

  async registerFilePath(filePath: string): Promise<DatasetInfo> {
    const response = await authFetch(`${API_BASE_URL}/analytics/register-path`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ file_path: filePath }),
    });

    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Failed to register file path');
    }

    return response.json();
  },

  async registerFolderPath(folderPath: string, pattern: string = '*'): Promise<{
    status: string;
    registered_count: number;
    error_count: number;
    datasets: DatasetInfo[];
    errors: string[];
    message?: string;
  }> {
    const response = await authFetch(`${API_BASE_URL}/analytics/register-folder`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ folder_path: folderPath, pattern }),
    });

    if (!response.ok) {
      try {
        const error = await response.json();
        throw new Error(error.detail || JSON.stringify(error) || 'Failed to register folder');
      } catch (e) {
        if (e instanceof Error && e.message !== 'Failed to register folder') {
          throw e;
        }
        throw new Error(`Failed to register folder: ${response.statusText}`);
      }
    }

    return response.json();
  },

  async listDatasets(): Promise<{ datasets: DatasetInfo[] }> {
    const response = await authFetch(`${API_BASE_URL}/analytics/datasets`);
    if (!response.ok) throw new Error('Failed to fetch datasets');
    return response.json();
  },

  async getDatasetInfo(datasetId: string): Promise<DatasetInfo> {
    const response = await authFetch(`${API_BASE_URL}/analytics/datasets/${datasetId}`);
    if (!response.ok) throw new Error('Failed to fetch dataset info');
    return response.json();
  },

  async deleteDataset(datasetId: string): Promise<void> {
    const response = await authFetch(`${API_BASE_URL}/analytics/datasets/${datasetId}`, {
      method: 'DELETE',
    });
    if (!response.ok) throw new Error('Failed to delete dataset');
  },

  async analyzeBasic(datasetId: string): Promise<AnalysisResult> {
    const response = await authFetch(`${API_BASE_URL}/analytics/analyze/basic`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: datasetId, analysis_type: 'basic' }),
    });
    if (!response.ok) throw new Error('Failed to analyze data');
    return response.json();
  },

  async analyzeAdvanced(datasetId: string): Promise<AnalysisResult> {
    const response = await authFetch(`${API_BASE_URL}/analytics/analyze/advanced`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: datasetId, analysis_type: 'advanced' }),
    });
    if (!response.ok) throw new Error('Failed to analyze data');
    return response.json();
  },

  async detectOutliers(datasetId: string, method: string = 'iqr'): Promise<AnalysisResult> {
    const response = await authFetch(`${API_BASE_URL}/analytics/analyze/outliers`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ 
        dataset_id: datasetId, 
        analysis_type: 'outliers',
        params: { method }
      }),
    });
    if (!response.ok) throw new Error('Failed to detect outliers');
    return response.json();
  },

  async getInsights(datasetId: string): Promise<AnalysisResult> {
    const response = await authFetch(`${API_BASE_URL}/analytics/analyze/insights`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: datasetId, analysis_type: 'insights' }),
    });
    if (!response.ok) throw new Error('Failed to get insights');
    return response.json();
  },

  async performRegression(
    datasetId: string,
    targetColumn: string,
    featureColumns?: string[],
    modelType: string = 'linear'
  ): Promise<AnalysisResult> {
    const response = await authFetch(`${API_BASE_URL}/analytics/predict/regression`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_id: datasetId,
        target_column: targetColumn,
        feature_columns: featureColumns,
        model_type: modelType,
      }),
    });
    if (!response.ok) throw new Error('Failed to perform regression');
    return response.json();
  },

  async predictFuture(
    datasetId: string,
    targetColumn: string,
    timeColumn?: string,
    periods: number = 10
  ): Promise<AnalysisResult> {
    const response = await authFetch(`${API_BASE_URL}/analytics/predict/future`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_id: datasetId,
        analysis_type: 'future',
        params: { target_column: targetColumn, time_column: timeColumn, periods },
      }),
    });
    if (!response.ok) throw new Error('Failed to predict future');
    return response.json();
  },

  async createVisualization(
    datasetId: string,
    plotType: string,
    params: any
  ): Promise<AnalysisResult> {
    const response = await authFetch(`${API_BASE_URL}/analytics/visualize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        dataset_id: datasetId,
        plot_type: plotType,
        params,
      }),
    });
    if (!response.ok) throw new Error('Failed to create visualization');
    return response.json();
  },

  async autoVisualize(datasetId: string): Promise<AnalysisResult> {
    const response = await authFetch(`${API_BASE_URL}/analytics/visualize/auto`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: datasetId, analysis_type: 'auto' }),
    });
    if (!response.ok) throw new Error('Failed to auto-visualize');
    return response.json();
  },

  async completeAnalysis(datasetId: string): Promise<AnalysisResult> {
    const response = await authFetch(`${API_BASE_URL}/analytics/analyze/complete`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: datasetId, analysis_type: 'complete' }),
    });
    if (!response.ok) throw new Error('Failed to perform complete analysis');
    return response.json();
  },

  async summarizeDocument(datasetId: string): Promise<AnalysisResult> {
    const response = await authFetch(`${API_BASE_URL}/analytics/analyze/summarize`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ dataset_id: datasetId, analysis_type: 'summarize' }),
    });
    if (!response.ok) throw new Error('Failed to summarize document');
    return response.json();
  },
};
