from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import List, Dict, Any, Optional
import pandas as pd
import json
from pathlib import Path
import uuid
import tempfile
import os
import glob

from ..analytics.data_loader import DataLoader
from ..analytics.analytics_engine import AnalyticsEngine
from ..analytics.visualizer import Visualizer
from ..core.logging_config import get_logger
from ..rag.page_index_store import PageIndexStore
from ..rag.chunker import DocumentChunker
from ..ingestion.pipeline import IngestionPipeline
from ..config.loader import load_config

logger = get_logger(__name__)

router = APIRouter(prefix="/analytics", tags=["analytics"])

data_loader = DataLoader()
analytics_engine = AnalyticsEngine()
visualizer = Visualizer()

# Page index components will be accessed from app_state (shared with main app)
# This ensures documents added here are immediately available in chat
page_index_store = None
ingestion_pipeline = None
config = None

def get_page_index_components():
    """Get page_index components from app_state to ensure synchronization with chat."""
    global page_index_store, ingestion_pipeline, config
    
    # Import here to avoid circular dependency
    from .app import app_state
    
    if page_index_store is None:
        page_index_store = app_state.get("rag_store")
        config = app_state.get("config")
        
        if page_index_store and config:
            chunker = app_state.get("chunker")
            if not chunker:
                chunker = DocumentChunker(config.rag)
                app_state["chunker"] = chunker
            
            ingestion_pipeline = app_state.get("ingestion_pipeline")
            if not ingestion_pipeline:
                ingestion_pipeline = IngestionPipeline(page_index_store, chunker)
                app_state["ingestion_pipeline"] = ingestion_pipeline
            
            logger.info("Using shared page_index from app_state")
        else:
            logger.warning("Page index not available in app_state")
    
    return page_index_store, ingestion_pipeline, config

# Components are lazily initialized on first route use via get_page_index_components()

# Store only file paths and metadata, not DataFrames
datasets = {}  # {dataset_id: {'file_path': str, 'filename': str, 'info': dict, 'in_page_index': bool}}

# Path to persistent storage
DATASETS_STORAGE_PATH = Path("data/analytics/datasets.json")

def save_datasets_to_file():
    """Save datasets metadata to persistent storage."""
    try:
        DATASETS_STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(DATASETS_STORAGE_PATH, 'w') as f:
            json.dump(datasets, f, indent=2, default=str)
        logger.info(f"Saved {len(datasets)} datasets to {DATASETS_STORAGE_PATH}")
    except Exception as e:
        logger.error(f"Failed to save datasets: {e}")

def load_datasets_from_file():
    """Load datasets metadata from persistent storage."""
    global datasets
    try:
        if DATASETS_STORAGE_PATH.exists():
            with open(DATASETS_STORAGE_PATH, 'r') as f:
                datasets = json.load(f)
            logger.info(f"Loaded {len(datasets)} datasets from {DATASETS_STORAGE_PATH}")
            
            # Verify files still exist and sync with page_index
            invalid_ids = []
            for dataset_id, dataset_info in datasets.items():
                file_path = Path(dataset_info['file_path'])
                if not file_path.exists():
                    logger.warning(f"Dataset file no longer exists: {dataset_info['filename']}")
                    invalid_ids.append(dataset_id)
                else:
                    # Check if it's in page_index (will be checked on first API call)
                    datasets[dataset_id]['in_page_index'] = dataset_info.get('in_page_index', False)
            
            # Remove invalid datasets
            for dataset_id in invalid_ids:
                del datasets[dataset_id]
            
            if invalid_ids:
                save_datasets_to_file()
        else:
            logger.info("No existing datasets file found, starting fresh")
    except Exception as e:
        logger.error(f"Failed to load datasets: {e}")
        datasets = {}

# Load datasets on startup
load_datasets_from_file()

def load_dataset(dataset_id: str) -> pd.DataFrame:
    """Lazy load dataset from file path when needed."""
    if dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    file_path = datasets[dataset_id]['file_path']
    
    if not Path(file_path).exists():
        raise HTTPException(status_code=404, detail=f"File not found at path: {file_path}")
    
    try:
        df = data_loader.load_data(file_path)
        df = data_loader.auto_detect_types(df)
        return df
    except Exception as e:
        logger.error(f"Error loading dataset from {file_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error loading dataset: {str(e)}")


class AnalysisRequest(BaseModel):
    dataset_id: str
    analysis_type: str
    params: Optional[Dict[str, Any]] = {}


class PredictionRequest(BaseModel):
    dataset_id: str
    target_column: str
    feature_columns: Optional[List[str]] = None
    model_type: str = "linear"


class VisualizationRequest(BaseModel):
    dataset_id: str
    plot_type: str
    params: Dict[str, Any]


@router.post("/upload")
async def upload_data_file(file: UploadFile = File(...)):
    """Upload a file - stores in permanent location for browser-selected files.
    Note: Files selected via browser picker must be copied since browser can't access original paths.
    Use 'Register File Path' or 'Register Folder' to reference files at their original locations.
    """
    logger.info(f"Uploading data file: {file.filename}")
    
    try:
        # Save file to permanent upload directory (not temp)
        # Browser-selected files must be copied since we can't access their original paths
        upload_dir = Path("data/analytics/uploads")
        upload_dir.mkdir(parents=True, exist_ok=True)
        
        # Keep original filename, handle duplicates by adding counter
        file_path = upload_dir / file.filename
        counter = 1
        base_name = file_path.stem
        extension = file_path.suffix
        while file_path.exists():
            file_path = upload_dir / f"{base_name}_{counter}{extension}"
            counter += 1
        
        # Save uploaded file
        content = await file.read()
        with open(file_path, 'wb') as f:
            f.write(content)
        
        # Load once to get metadata
        df = data_loader.load_from_bytes(content, file.filename)
        df = data_loader.auto_detect_types(df)
        info = data_loader.get_data_info(df)
        
        dataset_id = str(uuid.uuid4())
        
        # Ensure page_index components are initialized
        page_idx_store, ingest_pipeline, cfg = get_page_index_components()
        
        # Add ALL uploaded documents to page_index
        in_page_index = False
        if ingest_pipeline:
            try:
                ingest_pipeline.ingest_file(str(file_path))
                page_idx_store.save()
                in_page_index = True
                logger.info(f"Added {file.filename} to shared page_index (available in chat)")
            except Exception as e:
                logger.warning(f"Could not add to page_index: {e}")
        
        # Store only file path and metadata
        datasets[dataset_id] = {
            'file_path': str(file_path),
            'filename': file.filename,
            'info': info,
            'in_page_index': in_page_index
        }
        
        # Save to persistent storage
        save_datasets_to_file()
        
        logger.info(f"Dataset uploaded successfully: {dataset_id} at {file_path}")
        
        return {
            'status': 'success',
            'dataset_id': dataset_id,
            'filename': file.filename,
            'file_path': str(file_path),
            'shape': [int(x) for x in df.shape],
            'columns': [str(col) for col in df.columns],
            'in_page_index': in_page_index,
            'info': {
                'shape': [int(x) for x in info['shape']],
                'columns': info['columns'],
                'dtypes': info['dtypes'],
                'null_counts': {str(k): int(v) for k, v in info['null_counts'].items()},
                'memory_usage': int(info['memory_usage']),
                'numeric_columns': info['numeric_columns'],
                'categorical_columns': info['categorical_columns'],
                'datetime_columns': info['datetime_columns']
            }
        }
    
    except Exception as e:
        logger.error(f"Error uploading data file: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/register-path")
async def register_file_path(file_path: str):
    """Register an existing file by its path."""
    logger.info(f"Registering file from path: {file_path}")
    
    path = Path(file_path)
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"File not found: {file_path}")
    
    if not path.is_file():
        raise HTTPException(status_code=400, detail=f"Path is not a file: {file_path}")
    
    try:
        # Load once to get metadata
        df = data_loader.load_data(path)
        df = data_loader.auto_detect_types(df)
        info = data_loader.get_data_info(df)
        
        dataset_id = str(uuid.uuid4())
        
        # Ensure page_index components are initialized
        page_idx_store, ingest_pipeline, cfg = get_page_index_components()
        
        # Add ALL registered documents to page_index
        in_page_index = False
        if ingest_pipeline:
            try:
                ingest_pipeline.ingest_file(str(path))
                page_idx_store.save()
                in_page_index = True
                logger.info(f"Added {path.name} to shared page_index (available in chat)")
            except Exception as e:
                logger.warning(f"Could not add to page_index: {e}")
        
        datasets[dataset_id] = {
            'file_path': str(path.absolute()),
            'filename': path.name,
            'info': info,
            'in_page_index': in_page_index
        }
        
        # Save to persistent storage
        save_datasets_to_file()
        
        logger.info(f"File registered: {path.name}")
        
        return {
            'status': 'success',
            'dataset_id': dataset_id,
            'filename': path.name,
            'file_path': str(path.absolute()),
            'shape': [int(x) for x in df.shape],
            'columns': [str(col) for col in df.columns]
        }
    
    except Exception as e:
        logger.error(f"Error registering file: {str(e)}")
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/register-folder")
async def register_folder_path(folder_path: str, pattern: str = "*"):
    """Register all supported files from a folder."""
    logger.info(f"Registering files from folder: {folder_path} with pattern: {pattern}")
    
    try:
        path = Path(folder_path).expanduser().resolve()
    except Exception as e:
        logger.error(f"Invalid path format: {folder_path} - {str(e)}")
        raise HTTPException(status_code=400, detail=f"Invalid path format: {str(e)}")
    
    if not path.exists():
        raise HTTPException(status_code=404, detail=f"Folder not found: {folder_path}")
    
    if not path.is_dir():
        raise HTTPException(status_code=400, detail=f"Path is not a directory: {folder_path}")
    
    registered = []
    errors = []
    
    try:
        # Get all files matching pattern
        files_found = list(path.glob(pattern))
        logger.info(f"Found {len(files_found)} files matching pattern '{pattern}'")
        
        for file_path in files_found:
            if not file_path.is_file():
                continue
            
            # Check if file extension is supported
            if file_path.suffix.lower() not in data_loader.SUPPORTED_FORMATS:
                logger.debug(f"Skipping unsupported file: {file_path.name}")
                continue
            
            try:
                # Load once to get metadata
                df = data_loader.load_data(file_path)
                df = data_loader.auto_detect_types(df)
                info = data_loader.get_data_info(df)
                
                dataset_id = str(uuid.uuid4())
                
                # Ensure page_index components are initialized
                page_idx_store, ingest_pipeline, cfg = get_page_index_components()
                
                # Add ALL registered documents to page_index
                in_page_index = False
                if ingest_pipeline:
                    try:
                        ingest_pipeline.ingest_file(str(file_path))
                        page_idx_store.save()
                        in_page_index = True
                        logger.info(f"Added {file_path.name} to shared page_index (available in chat)")
                    except Exception as e:
                        logger.warning(f"Could not add to page_index: {e}")
                
                datasets[dataset_id] = {
                    'file_path': str(file_path.absolute()),
                    'filename': file_path.name,
                    'info': info,
                    'in_page_index': in_page_index
                }
                
                # Save to persistent storage
                save_datasets_to_file()
                
                registered.append({
                    'dataset_id': dataset_id,
                    'filename': file_path.name,
                    'file_path': str(file_path.absolute()),
                    'shape': [int(x) for x in df.shape],
                    'columns': [str(col) for col in df.columns]
                })
                
                logger.info(f"Registered file: {file_path.name}")
            
            except Exception as e:
                error_msg = f"Error loading {file_path.name}: {str(e)}"
                logger.error(error_msg)
                errors.append(error_msg)
        
        # Save to persistent storage
        save_datasets_to_file()
        
        if len(registered) == 0 and len(errors) == 0:
            return {
                'status': 'success',
                'registered_count': 0,
                'error_count': 0,
                'datasets': [],
                'errors': [],
                'message': f"No supported files found in folder. Supported formats: {', '.join(data_loader.SUPPORTED_FORMATS)}"
            }
        
        return {
            'status': 'success',
            'registered_count': len(registered),
            'error_count': len(errors),
            'datasets': registered,
            'errors': errors
        }
    
    except Exception as e:
        logger.error(f"Error processing folder {folder_path}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing folder: {str(e)}")


@router.get("/datasets")
async def list_datasets():
    return {
        'datasets': [
            {
                'dataset_id': dataset_id,
                'filename': data['filename'],
                'file_path': data['file_path'],
                'shape': [int(x) for x in data['info']['shape']],
                'columns': data['info']['columns']
            }
            for dataset_id, data in datasets.items()
        ]
    }


@router.get("/datasets/{dataset_id}")
async def get_dataset_info(dataset_id: str):
    if dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    data = datasets[dataset_id]
    df = load_dataset(dataset_id)  # Lazy load from file path
    
    return {
        'dataset_id': dataset_id,
        'filename': data['filename'],
        'file_path': data['file_path'],
        'shape': [int(x) for x in df.shape],
        'columns': [str(col) for col in df.columns],
        'info': data['info'],
        'preview': df.head(10).to_dict(orient='records')
    }


@router.delete("/datasets/{dataset_id}")
async def delete_dataset(dataset_id: str):
    if dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    dataset_info = datasets[dataset_id]
    
    # Ensure page_index components are initialized
    page_idx_store, ingest_pipeline, cfg = get_page_index_components()
    
    # Remove from page_index if it was added
    if dataset_info.get('in_page_index', False) and page_idx_store:
        try:
            # Find document by filename and delete
            docs = page_idx_store.list_documents()
            for doc in docs:
                if doc.filename == dataset_info['filename']:
                    page_idx_store.delete_document(doc.doc_id)
                    page_idx_store.save()
                    logger.info(f"Removed {dataset_info['filename']} from shared page_index")
                    break
        except Exception as e:
            logger.warning(f"Could not remove from page_index: {e}")
    
    # Delete physical file if it exists
    file_path = Path(dataset_info['file_path'])
    if file_path.exists():
        try:
            file_path.unlink()
            logger.info(f"Deleted physical file: {file_path}")
        except Exception as e:
            logger.warning(f"Could not delete physical file: {e}")
    
    del datasets[dataset_id]
    
    # Save to persistent storage
    save_datasets_to_file()
    
    return {'status': 'deleted', 'dataset_id': dataset_id, 'filename': dataset_info['filename']}


@router.post("/analyze/basic")
async def analyze_basic(request: AnalysisRequest):
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = load_dataset(request.dataset_id)  # Lazy load from file path
    
    try:
        stats = analytics_engine.get_basic_statistics(df)
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'statistics': stats
        }
    
    except Exception as e:
        logger.error(f"Error in basic analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/advanced")
async def analyze_advanced(request: AnalysisRequest):
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = load_dataset(request.dataset_id)  # Lazy load from file path
    
    try:
        stats = analytics_engine.get_advanced_statistics(df)
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'statistics': stats
        }
    
    except Exception as e:
        logger.error(f"Error in advanced analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/outliers")
async def detect_outliers(request: AnalysisRequest):
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = load_dataset(request.dataset_id)  # Lazy load from file path
    method = request.params.get('method', 'iqr')
    
    try:
        outliers = analytics_engine.detect_outliers(df, method=method)
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'method': method,
            'outliers': outliers
        }
    
    except Exception as e:
        logger.error(f"Error detecting outliers: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/insights")
async def get_insights(request: AnalysisRequest):
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = load_dataset(request.dataset_id)  # Lazy load from file path
    
    try:
        insights = analytics_engine.get_data_insights(df)
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'insights': insights
        }
    
    except Exception as e:
        logger.error(f"Error generating insights: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/regression")
async def predict_regression(request: PredictionRequest):
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = load_dataset(request.dataset_id)  # Lazy load from file path
    
    try:
        results = analytics_engine.perform_regression(
            df,
            target_column=request.target_column,
            feature_columns=request.feature_columns,
            model_type=request.model_type
        )
        
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'results': results
        }
    
    except Exception as e:
        logger.error(f"Error in regression: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/classification")
async def predict_classification(request: PredictionRequest):
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = load_dataset(request.dataset_id)  # Lazy load from file path
    
    try:
        results = analytics_engine.perform_classification(
            df,
            target_column=request.target_column,
            feature_columns=request.feature_columns,
            model_type=request.model_type
        )
        
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'results': results
        }
    
    except Exception as e:
        logger.error(f"Error in classification: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/future")
async def predict_future(request: AnalysisRequest):
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = load_dataset(request.dataset_id)  # Lazy load from file path
    
    target_column = request.params.get('target_column')
    time_column = request.params.get('time_column')
    periods = request.params.get('periods', 10)
    
    if not target_column:
        raise HTTPException(status_code=400, detail="target_column is required")
    
    try:
        results = analytics_engine.predict_future(
            df,
            target_column=target_column,
            time_column=time_column,
            periods=periods
        )
        
        prediction_plot = visualizer.create_prediction_plot(
            results['historical_values'],
            results['predictions'],
            title=f"Prediction for {target_column}"
        )
        
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'results': results,
            'plot': prediction_plot
        }
    
    except Exception as e:
        logger.error(f"Error in future prediction: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/visualize")
async def create_visualization(request: VisualizationRequest):
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = load_dataset(request.dataset_id)  # Lazy load from file path
    
    try:
        plot_type = request.plot_type
        params = request.params
        
        if plot_type == 'histogram':
            plot = visualizer.create_histogram(df, **params)
        elif plot_type == 'scatter':
            plot = visualizer.create_scatter_plot(df, **params)
        elif plot_type == 'line':
            plot = visualizer.create_line_plot(df, **params)
        elif plot_type == 'bar':
            plot = visualizer.create_bar_chart(df, **params)
        elif plot_type == 'box':
            plot = visualizer.create_box_plot(df, **params)
        elif plot_type == 'pie':
            plot = visualizer.create_pie_chart(df, **params)
        elif plot_type == 'heatmap':
            plot = visualizer.create_correlation_heatmap(df, **params)
        elif plot_type == 'timeseries':
            plot = visualizer.create_time_series(df, **params)
        else:
            raise HTTPException(status_code=400, detail=f"Unknown plot type: {plot_type}")
        
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'plot': plot
        }
    
    except Exception as e:
        logger.error(f"Error creating visualization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/visualize/auto")
async def auto_visualize(request: AnalysisRequest):
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = load_dataset(request.dataset_id)  # Lazy load from file path
    
    try:
        plots = visualizer.auto_visualize(df)
        
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'plots': plots
        }
    
    except Exception as e:
        logger.error(f"Error in auto visualization: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/summarize")
async def summarize_document(request: AnalysisRequest):
    """Generate a summary/NLP analysis of the document using LLM."""
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    dataset_info = datasets[request.dataset_id]
    file_path = Path(dataset_info['file_path'])
    
    try:
        # Read file content
        if file_path.suffix.lower() in ['.txt', '.md', '.markdown']:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
        elif file_path.suffix.lower() == '.pdf':
            # For PDF, try to extract text
            try:
                from ..ingestion.loaders import DocumentLoader
                loader = DocumentLoader()
                doc = loader.load_file(str(file_path))
                content = doc.content
            except:
                content = "PDF content extraction not available"
        else:
            # For data files, create a summary from the dataframe
            df = load_dataset(request.dataset_id)
            content = f"Dataset: {dataset_info['filename']}\n"
            content += f"Shape: {df.shape[0]} rows × {df.shape[1]} columns\n\n"
            content += f"Columns: {', '.join(df.columns)}\n\n"
            content += f"First few rows:\n{df.head().to_string()}\n\n"
            content += f"Summary statistics:\n{df.describe().to_string()}"
        
        # Get basic statistics
        lines = content.split('\n')
        total_lines = len(lines)
        total_chars = len(content)
        total_words = len(content.split())
        
        # Truncate content for LLM if too long (keep first 4000 words)
        words = content.split()
        if len(words) > 4000:
            truncated_content = ' '.join(words[:4000])
            logger.info(f"Truncated content from {len(words)} to 4000 words for LLM summarization")
        else:
            truncated_content = content
        
        # Use LLM to generate summary
        import re
        from collections import Counter
        from ..chat.orchestrator import ChatOrchestrator
        
        llm_summary = None
        keywords_list = []
        
        try:
            # Get shared components
            page_idx_store, ingest_pipeline, cfg = get_page_index_components()
            
            # Use ChatOrchestrator for better LLM handling
            logger.info("Initializing ChatOrchestrator for summarization")
            orchestrator = ChatOrchestrator(cfg)
            
            # Create summarization prompt
            prompt = f"""Analyze and summarize the following document. Provide:

1. A concise summary (2-3 paragraphs) in markdown format
2. Key topics or themes (list 5-10 main topics)
3. Important keywords (list 10-15 significant terms)

Document content:
{truncated_content}

Please format your response as:

## Summary
[Your summary here in markdown]

## Key Topics
- Topic 1
- Topic 2
...

## Keywords
keyword1, keyword2, keyword3, ..."""

            # Get LLM response using simple chat
            logger.info("Calling LLM for document summarization")
            response = orchestrator.chat_simple(prompt)
            llm_summary = response
            
            logger.info(f"LLM summarization successful, response length: {len(llm_summary)}")
            
            # Extract keywords from LLM response
            keywords_match = re.search(r'## Keywords\s*\n(.+?)(?:\n\n|\Z)', llm_summary, re.DOTALL)
            if keywords_match:
                keywords_text = keywords_match.group(1).strip()
                keywords_list = [kw.strip() for kw in keywords_text.split(',')][:10]
                logger.info(f"Extracted {len(keywords_list)} keywords from LLM response")
            else:
                logger.warning("Could not extract keywords from LLM response")
            
        except Exception as e:
            logger.error(f"LLM summarization failed with error: {type(e).__name__}: {str(e)}", exc_info=True)
            # Fallback to simple preview
            llm_summary = f"## Document Preview\n\n{' '.join(words[:500])}..."
            
            # Simple keyword extraction as fallback
            words_clean = re.findall(r'\b[a-zA-Z]{4,}\b', content.lower())
            word_freq = Counter(words_clean)
            stop_words = {'that', 'this', 'with', 'from', 'have', 'been', 'were', 'will', 'would', 'could', 'should', 'their', 'there', 'these', 'those', 'what', 'when', 'where', 'which', 'while'}
            keywords_list = [word for word, count in word_freq.most_common(20) if word not in stop_words][:10]
            logger.info("Using fallback keyword extraction")
        
        summary = {
            'filename': dataset_info['filename'],
            'file_type': file_path.suffix,
            'statistics': {
                'total_lines': total_lines,
                'total_characters': total_chars,
                'total_words': total_words,
            },
            'preview': llm_summary,
            'keywords': [{'word': kw, 'frequency': 0} for kw in keywords_list],
            'in_page_index': dataset_info.get('in_page_index', False)
        }
        
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'summary': summary
        }
    
    except Exception as e:
        logger.error(f"Error summarizing document: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analyze/complete")
async def complete_analysis(request: AnalysisRequest):
    if request.dataset_id not in datasets:
        raise HTTPException(status_code=404, detail="Dataset not found")
    
    df = load_dataset(request.dataset_id)  # Lazy load from file path
    
    try:
        basic_stats = analytics_engine.get_basic_statistics(df)
        advanced_stats = analytics_engine.get_advanced_statistics(df)
        insights = analytics_engine.get_data_insights(df)
        outliers = analytics_engine.detect_outliers(df)
        plots = visualizer.auto_visualize(df)
        
        return {
            'status': 'success',
            'dataset_id': request.dataset_id,
            'basic_statistics': basic_stats,
            'advanced_statistics': advanced_stats,
            'insights': insights,
            'outliers': outliers,
            'visualizations': plots
        }
    
    except Exception as e:
        logger.error(f"Error in complete analysis: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
