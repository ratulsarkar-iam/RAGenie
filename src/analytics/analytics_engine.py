import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional, Tuple
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.preprocessing import StandardScaler, LabelEncoder
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, accuracy_score, classification_report
from scipy import stats
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class AnalyticsEngine:
    
    def __init__(self):
        self.scaler = StandardScaler()
        self.label_encoders = {}
        self.models = {}
    
    def get_basic_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        logger.info("Calculating basic statistics")
        
        def clean_nan(obj):
            """Recursively replace NaN with None for JSON serialization."""
            if isinstance(obj, dict):
                return {k: clean_nan(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [clean_nan(item) for item in obj]
            elif isinstance(obj, float):
                if np.isnan(obj) or np.isinf(obj):
                    return None
                return obj
            return obj
        
        stats_dict = {
            'summary': clean_nan(df.describe().to_dict()),
            'shape': df.shape,
            'columns': list(df.columns),
            'dtypes': {col: str(dtype) for col, dtype in df.dtypes.items()},
            'missing_values': {k: int(v) for k, v in df.isnull().sum().to_dict().items()},
            'missing_percentage': clean_nan((df.isnull().sum() / len(df) * 100).to_dict())
        }
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            stats_dict['correlation_matrix'] = clean_nan(df[numeric_cols].corr().to_dict())
        
        return stats_dict
    
    def get_advanced_statistics(self, df: pd.DataFrame) -> Dict[str, Any]:
        logger.info("Calculating advanced statistics")
        
        def safe_float(value):
            """Convert to float and handle NaN/Inf."""
            if pd.isna(value) or np.isinf(value):
                return None
            return float(value)
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        
        advanced_stats = {}
        
        for col in numeric_cols:
            col_data = df[col].dropna()
            
            if len(col_data) > 0:
                advanced_stats[col] = {
                    'mean': safe_float(col_data.mean()),
                    'median': safe_float(col_data.median()),
                    'mode': safe_float(col_data.mode()[0]) if len(col_data.mode()) > 0 else None,
                    'std': safe_float(col_data.std()),
                    'variance': safe_float(col_data.var()),
                    'skewness': safe_float(col_data.skew()),
                    'kurtosis': safe_float(col_data.kurtosis()),
                    'min': safe_float(col_data.min()),
                    'max': safe_float(col_data.max()),
                    'range': safe_float(col_data.max() - col_data.min()),
                    'q1': safe_float(col_data.quantile(0.25)),
                    'q3': safe_float(col_data.quantile(0.75)),
                    'iqr': safe_float(col_data.quantile(0.75) - col_data.quantile(0.25))
                }
        
        return advanced_stats
    
    def detect_outliers(self, df: pd.DataFrame, method: str = 'iqr') -> Dict[str, Any]:
        logger.info(f"Detecting outliers using {method} method")
        
        def safe_float(value):
            """Convert to float and handle NaN/Inf."""
            if pd.isna(value) or np.isinf(value):
                return None
            return float(value)
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        outliers = {}
        
        for col in numeric_cols:
            col_data = df[col].dropna()
            
            if len(col_data) == 0:
                outliers[col] = {
                    'count': 0,
                    'percentage': 0.0,
                    'indices': []
                }
                continue
            
            if method == 'iqr':
                Q1 = col_data.quantile(0.25)
                Q3 = col_data.quantile(0.75)
                IQR = Q3 - Q1
                lower_bound = Q1 - 1.5 * IQR
                upper_bound = Q3 + 1.5 * IQR
                
                outlier_mask = (df[col] < lower_bound) | (df[col] > upper_bound)
                outlier_indices = df[outlier_mask].index.tolist()
                
            elif method == 'zscore':
                z_scores = np.abs(stats.zscore(col_data))
                outlier_mask = z_scores > 3
                outlier_indices = col_data[outlier_mask].index.tolist()
            
            else:
                raise ValueError(f"Unknown outlier detection method: {method}")
            
            outliers[col] = {
                'count': len(outlier_indices),
                'percentage': safe_float((len(outlier_indices) / len(df)) * 100),
                'indices': outlier_indices[:100]
            }
        
        return outliers
    
    def perform_regression(
        self, 
        df: pd.DataFrame, 
        target_column: str,
        feature_columns: Optional[List[str]] = None,
        model_type: str = 'linear',
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        logger.info(f"Performing {model_type} regression on {target_column}")
        
        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found in dataframe")
        
        if feature_columns is None:
            feature_columns = [col for col in df.select_dtypes(include=[np.number]).columns 
                             if col != target_column]
        
        df_clean = df[feature_columns + [target_column]].dropna()
        
        X = df_clean[feature_columns]
        y = df_clean[target_column]
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )
        
        if model_type == 'linear':
            model = LinearRegression()
        elif model_type == 'random_forest':
            model = RandomForestRegressor(n_estimators=100, random_state=42)
        else:
            raise ValueError(f"Unknown regression model type: {model_type}")
        
        model.fit(X_train, y_train)
        
        y_pred_train = model.predict(X_train)
        y_pred_test = model.predict(X_test)
        
        train_mse = mean_squared_error(y_train, y_pred_train)
        test_mse = mean_squared_error(y_test, y_pred_test)
        train_r2 = r2_score(y_train, y_pred_train)
        test_r2 = r2_score(y_test, y_pred_test)
        
        results = {
            'model_type': model_type,
            'target': target_column,
            'features': feature_columns,
            'metrics': {
                'train_mse': float(train_mse),
                'test_mse': float(test_mse),
                'train_r2': float(train_r2),
                'test_r2': float(test_r2),
                'train_rmse': float(np.sqrt(train_mse)),
                'test_rmse': float(np.sqrt(test_mse))
            },
            'predictions': {
                'actual': y_test.tolist()[:50],
                'predicted': y_pred_test.tolist()[:50]
            }
        }
        
        if model_type == 'linear':
            results['coefficients'] = {
                feature: float(coef) 
                for feature, coef in zip(feature_columns, model.coef_)
            }
            results['intercept'] = float(model.intercept_)
        elif model_type == 'random_forest':
            results['feature_importance'] = {
                feature: float(importance)
                for feature, importance in zip(feature_columns, model.feature_importances_)
            }
        
        self.models[f"{model_type}_{target_column}"] = model
        
        return results
    
    def perform_classification(
        self,
        df: pd.DataFrame,
        target_column: str,
        feature_columns: Optional[List[str]] = None,
        model_type: str = 'logistic',
        test_size: float = 0.2
    ) -> Dict[str, Any]:
        logger.info(f"Performing {model_type} classification on {target_column}")
        
        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found in dataframe")
        
        if feature_columns is None:
            feature_columns = [col for col in df.select_dtypes(include=[np.number]).columns 
                             if col != target_column]
        
        df_clean = df[feature_columns + [target_column]].dropna()
        
        X = df_clean[feature_columns]
        y = df_clean[target_column]
        
        le = LabelEncoder()
        y_encoded = le.fit_transform(y)
        
        X_train, X_test, y_train, y_test = train_test_split(
            X, y_encoded, test_size=test_size, random_state=42
        )
        
        if model_type == 'logistic':
            model = LogisticRegression(max_iter=1000, random_state=42)
        elif model_type == 'random_forest':
            model = RandomForestClassifier(n_estimators=100, random_state=42)
        else:
            raise ValueError(f"Unknown classification model type: {model_type}")
        
        model.fit(X_train, y_train)
        
        y_pred_train = model.predict(X_train)
        y_pred_test = model.predict(X_test)
        
        train_acc = accuracy_score(y_train, y_pred_train)
        test_acc = accuracy_score(y_test, y_pred_test)
        
        results = {
            'model_type': model_type,
            'target': target_column,
            'features': feature_columns,
            'classes': le.classes_.tolist(),
            'metrics': {
                'train_accuracy': float(train_acc),
                'test_accuracy': float(test_acc)
            }
        }
        
        if model_type == 'random_forest':
            results['feature_importance'] = {
                feature: float(importance)
                for feature, importance in zip(feature_columns, model.feature_importances_)
            }
        
        self.models[f"{model_type}_{target_column}"] = model
        self.label_encoders[target_column] = le
        
        return results
    
    def predict_future(
        self,
        df: pd.DataFrame,
        target_column: str,
        time_column: Optional[str] = None,
        periods: int = 10
    ) -> Dict[str, Any]:
        logger.info(f"Predicting future values for {target_column}")
        
        if target_column not in df.columns:
            raise ValueError(f"Target column '{target_column}' not found")
        
        if time_column and time_column in df.columns:
            df_sorted = df.sort_values(time_column)
        else:
            df_sorted = df.copy()
        
        y = df_sorted[target_column].dropna()
        
        if len(y) < 2:
            raise ValueError("Not enough data points for prediction")
        
        X = np.arange(len(y)).reshape(-1, 1)
        
        model = LinearRegression()
        model.fit(X, y)
        
        future_X = np.arange(len(y), len(y) + periods).reshape(-1, 1)
        predictions = model.predict(future_X)
        
        trend = 'increasing' if model.coef_[0] > 0 else 'decreasing'
        
        return {
            'target': target_column,
            'historical_values': y.tolist()[-20:],
            'predictions': predictions.tolist(),
            'trend': trend,
            'slope': float(model.coef_[0]),
            'intercept': float(model.intercept_),
            'periods': periods
        }
    
    def get_data_insights(self, df: pd.DataFrame) -> Dict[str, Any]:
        logger.info("Generating data insights")
        
        def safe_float(value):
            """Convert to float and handle NaN/Inf."""
            if pd.isna(value) or np.isinf(value):
                return None
            return float(value)
        
        insights = {
            'total_rows': len(df),
            'total_columns': len(df.columns),
            'numeric_columns': len(df.select_dtypes(include=[np.number]).columns),
            'categorical_columns': len(df.select_dtypes(include=['object', 'category']).columns),
            'missing_data_percentage': safe_float((df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100),
            'duplicate_rows': int(df.duplicated().sum())
        }
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) >= 2:
            corr_matrix = df[numeric_cols].corr()
            
            high_correlations = []
            for i in range(len(corr_matrix.columns)):
                for j in range(i+1, len(corr_matrix.columns)):
                    corr_val = corr_matrix.iloc[i, j]
                    if not pd.isna(corr_val) and not np.isinf(corr_val) and abs(corr_val) > 0.7:
                        high_correlations.append({
                            'column1': corr_matrix.columns[i],
                            'column2': corr_matrix.columns[j],
                            'correlation': float(corr_val)
                        })
            
            insights['high_correlations'] = high_correlations
        
        return insights
