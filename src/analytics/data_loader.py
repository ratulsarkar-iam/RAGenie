import pandas as pd
import numpy as np
from pathlib import Path
from typing import Union, Dict, Any, List, Optional
import PyPDF2
import io
import re
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class DataLoader:
    
    SUPPORTED_FORMATS = {
        '.csv': 'csv',
        '.xlsx': 'excel',
        '.xls': 'excel',
        '.txt': 'text',
        '.pdf': 'pdf',
        '.json': 'json',
        '.tsv': 'tsv'
    }
    
    def __init__(self):
        pass
    
    def load_data(self, file_path: Union[str, Path], **kwargs) -> pd.DataFrame:
        file_path = Path(file_path)
        
        if not file_path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")
        
        ext = file_path.suffix.lower()
        
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(
                f"Unsupported file format: {ext}. "
                f"Supported formats: {', '.join(self.SUPPORTED_FORMATS.keys())}"
            )
        
        file_type = self.SUPPORTED_FORMATS[ext]
        
        try:
            if file_type == 'csv':
                return self._load_csv(file_path, **kwargs)
            elif file_type == 'excel':
                return self._load_excel(file_path, **kwargs)
            elif file_type == 'text':
                return self._load_text(file_path, **kwargs)
            elif file_type == 'pdf':
                return self._load_pdf(file_path, **kwargs)
            elif file_type == 'json':
                return self._load_json(file_path, **kwargs)
            elif file_type == 'tsv':
                return self._load_tsv(file_path, **kwargs)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        
        except Exception as e:
            logger.error(f"Error loading file {file_path}: {str(e)}")
            raise
    
    def _load_csv(self, file_path: Path, **kwargs) -> pd.DataFrame:
        logger.info(f"Loading CSV file: {file_path}")
        
        encoding = kwargs.get('encoding', 'utf-8')
        delimiter = kwargs.get('delimiter', ',')
        
        try:
            df = pd.read_csv(file_path, encoding=encoding, delimiter=delimiter)
        except UnicodeDecodeError:
            df = pd.read_csv(file_path, encoding='latin-1', delimiter=delimiter)
        
        logger.info(f"Loaded CSV with shape: {df.shape}")
        return df
    
    def _load_excel(self, file_path: Path, **kwargs) -> pd.DataFrame:
        logger.info(f"Loading Excel file: {file_path}")
        
        sheet_name = kwargs.get('sheet_name', 0)
        
        df = pd.read_excel(file_path, sheet_name=sheet_name, engine='openpyxl')
        
        logger.info(f"Loaded Excel with shape: {df.shape}")
        return df
    
    def _load_text(self, file_path: Path, **kwargs) -> pd.DataFrame:
        logger.info(f"Loading text file: {file_path}")
        
        delimiter = kwargs.get('delimiter', None)
        
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        if delimiter:
            lines = content.strip().split('\n')
            data = [line.split(delimiter) for line in lines]
            df = pd.DataFrame(data[1:], columns=data[0] if data else None)
        else:
            lines = content.strip().split('\n')
            df = pd.DataFrame({'text': lines})
        
        logger.info(f"Loaded text file with shape: {df.shape}")
        return df
    
    def _load_pdf(self, file_path: Path, **kwargs) -> pd.DataFrame:
        logger.info(f"Loading PDF file: {file_path}")
        
        extract_tables = kwargs.get('extract_tables', False)
        
        with open(file_path, 'rb') as f:
            pdf_reader = PyPDF2.PdfReader(f)
            
            if extract_tables:
                try:
                    import pdfplumber
                    with pdfplumber.open(file_path) as pdf:
                        all_tables = []
                        for page in pdf.pages:
                            tables = page.extract_tables()
                            if tables:
                                for table in tables:
                                    if table and len(table) > 1:
                                        df_table = pd.DataFrame(table[1:], columns=table[0])
                                        all_tables.append(df_table)
                        
                        if all_tables:
                            df = pd.concat(all_tables, ignore_index=True)
                            logger.info(f"Extracted {len(all_tables)} tables from PDF")
                            return df
                except ImportError:
                    logger.warning("pdfplumber not available, falling back to text extraction")
            
            text_data = []
            for page_num, page in enumerate(pdf_reader.pages):
                text = page.extract_text()
                if text:
                    text_data.append({
                        'page': page_num + 1,
                        'text': text.strip()
                    })
            
            df = pd.DataFrame(text_data)
        
        logger.info(f"Loaded PDF with shape: {df.shape}")
        return df
    
    def _load_json(self, file_path: Path, **kwargs) -> pd.DataFrame:
        logger.info(f"Loading JSON file: {file_path}")
        
        orient = kwargs.get('orient', 'records')
        
        df = pd.read_json(file_path, orient=orient)
        
        logger.info(f"Loaded JSON with shape: {df.shape}")
        return df
    
    def _load_tsv(self, file_path: Path, **kwargs) -> pd.DataFrame:
        logger.info(f"Loading TSV file: {file_path}")
        
        df = pd.read_csv(file_path, delimiter='\t')
        
        logger.info(f"Loaded TSV with shape: {df.shape}")
        return df
    
    def load_from_bytes(self, file_bytes: bytes, filename: str, **kwargs) -> pd.DataFrame:
        ext = Path(filename).suffix.lower()
        
        if ext not in self.SUPPORTED_FORMATS:
            raise ValueError(f"Unsupported file format: {ext}")
        
        file_type = self.SUPPORTED_FORMATS[ext]
        
        try:
            if file_type == 'csv':
                return pd.read_csv(io.BytesIO(file_bytes), **kwargs)
            elif file_type == 'excel':
                return pd.read_excel(io.BytesIO(file_bytes), engine='openpyxl', **kwargs)
            elif file_type == 'json':
                return pd.read_json(io.BytesIO(file_bytes), **kwargs)
            elif file_type == 'tsv':
                return pd.read_csv(io.BytesIO(file_bytes), delimiter='\t', **kwargs)
            elif file_type == 'text':
                content = file_bytes.decode('utf-8')
                lines = content.strip().split('\n')
                return pd.DataFrame({'text': lines})
            elif file_type == 'pdf':
                pdf_reader = PyPDF2.PdfReader(io.BytesIO(file_bytes))
                text_data = []
                for page_num, page in enumerate(pdf_reader.pages):
                    text = page.extract_text()
                    if text:
                        text_data.append({
                            'page': page_num + 1,
                            'text': text.strip()
                        })
                return pd.DataFrame(text_data)
            else:
                raise ValueError(f"Unsupported file type: {file_type}")
        
        except Exception as e:
            logger.error(f"Error loading file from bytes: {str(e)}")
            raise
    
    def get_data_info(self, df: pd.DataFrame) -> Dict[str, Any]:
        info = {
            'shape': df.shape,
            'columns': list(df.columns),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'null_counts': df.isnull().sum().to_dict(),
            'memory_usage': df.memory_usage(deep=True).sum(),
            'numeric_columns': list(df.select_dtypes(include=[np.number]).columns),
            'categorical_columns': list(df.select_dtypes(include=['object', 'category']).columns),
            'datetime_columns': list(df.select_dtypes(include=['datetime64']).columns)
        }
        
        return info
    
    def auto_detect_types(self, df: pd.DataFrame) -> pd.DataFrame:
        df_copy = df.copy()
        
        for col in df_copy.columns:
            if df_copy[col].dtype == 'object':
                try:
                    df_copy[col] = pd.to_datetime(df_copy[col])
                    logger.info(f"Converted column '{col}' to datetime")
                    continue
                except (ValueError, TypeError):
                    pass
                
                try:
                    df_copy[col] = pd.to_numeric(df_copy[col])
                    logger.info(f"Converted column '{col}' to numeric")
                    continue
                except (ValueError, TypeError):
                    pass
        
        return df_copy
