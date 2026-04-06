import pandas as pd
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns
import plotly.graph_objects as go
import plotly.express as px
from typing import Dict, Any, List, Optional, Tuple
import io
import base64
from pathlib import Path
from ..core.logging_config import get_logger

logger = get_logger(__name__)


class Visualizer:
    
    def __init__(self, output_dir: str = "static/analytics"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        
        sns.set_style("whitegrid")
        plt.rcParams['figure.figsize'] = (10, 6)
    
    def create_histogram(
        self, 
        df: pd.DataFrame, 
        column: str,
        bins: int = 30,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(f"Creating histogram for {column}")
        
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found in dataframe")
        
        fig = go.Figure()
        
        fig.add_trace(go.Histogram(
            x=df[column].dropna(),
            nbinsx=bins,
            name=column,
            marker_color='steelblue'
        ))
        
        fig.update_layout(
            title=title or f'Distribution of {column}',
            xaxis_title=column,
            yaxis_title='Frequency',
            template='plotly_white',
            height=500
        )
        
        return {
            'type': 'histogram',
            'column': column,
            'plotly_json': fig.to_json()
        }
    
    def create_scatter_plot(
        self,
        df: pd.DataFrame,
        x_column: str,
        y_column: str,
        color_column: Optional[str] = None,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(f"Creating scatter plot: {x_column} vs {y_column}")
        
        if x_column not in df.columns or y_column not in df.columns:
            raise ValueError(f"Columns not found in dataframe")
        
        if color_column and color_column in df.columns:
            fig = px.scatter(
                df,
                x=x_column,
                y=y_column,
                color=color_column,
                title=title or f'{y_column} vs {x_column}',
                template='plotly_white',
                height=500
            )
        else:
            fig = px.scatter(
                df,
                x=x_column,
                y=y_column,
                title=title or f'{y_column} vs {x_column}',
                template='plotly_white',
                height=500
            )
        
        return {
            'type': 'scatter',
            'x_column': x_column,
            'y_column': y_column,
            'plotly_json': fig.to_json()
        }
    
    def create_line_plot(
        self,
        df: pd.DataFrame,
        x_column: str,
        y_columns: List[str],
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(f"Creating line plot for {y_columns}")
        
        fig = go.Figure()
        
        for y_col in y_columns:
            if y_col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df[x_column] if x_column in df.columns else df.index,
                    y=df[y_col],
                    mode='lines+markers',
                    name=y_col
                ))
        
        fig.update_layout(
            title=title or 'Line Plot',
            xaxis_title=x_column if x_column in df.columns else 'Index',
            yaxis_title='Value',
            template='plotly_white',
            height=500
        )
        
        return {
            'type': 'line',
            'x_column': x_column,
            'y_columns': y_columns,
            'plotly_json': fig.to_json()
        }
    
    def create_bar_chart(
        self,
        df: pd.DataFrame,
        x_column: str,
        y_column: str,
        title: Optional[str] = None,
        orientation: str = 'v'
    ) -> Dict[str, Any]:
        logger.info(f"Creating bar chart: {x_column} vs {y_column}")
        
        if orientation == 'v':
            fig = px.bar(
                df,
                x=x_column,
                y=y_column,
                title=title or f'{y_column} by {x_column}',
                template='plotly_white',
                height=500
            )
        else:
            fig = px.bar(
                df,
                x=y_column,
                y=x_column,
                orientation='h',
                title=title or f'{y_column} by {x_column}',
                template='plotly_white',
                height=500
            )
        
        return {
            'type': 'bar',
            'x_column': x_column,
            'y_column': y_column,
            'plotly_json': fig.to_json()
        }
    
    def create_box_plot(
        self,
        df: pd.DataFrame,
        columns: List[str],
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(f"Creating box plot for {columns}")
        
        fig = go.Figure()
        
        for col in columns:
            if col in df.columns:
                fig.add_trace(go.Box(
                    y=df[col].dropna(),
                    name=col
                ))
        
        fig.update_layout(
            title=title or 'Box Plot',
            yaxis_title='Value',
            template='plotly_white',
            height=500
        )
        
        return {
            'type': 'box',
            'columns': columns,
            'plotly_json': fig.to_json()
        }
    
    def create_correlation_heatmap(
        self,
        df: pd.DataFrame,
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info("Creating correlation heatmap")
        
        numeric_df = df.select_dtypes(include=[np.number])
        
        if numeric_df.empty:
            raise ValueError("No numeric columns found for correlation")
        
        corr_matrix = numeric_df.corr()
        
        fig = go.Figure(data=go.Heatmap(
            z=corr_matrix.values,
            x=corr_matrix.columns,
            y=corr_matrix.columns,
            colorscale='RdBu',
            zmid=0,
            text=corr_matrix.values.round(2),
            texttemplate='%{text}',
            textfont={"size": 10},
            colorbar=dict(title="Correlation")
        ))
        
        fig.update_layout(
            title=title or 'Correlation Heatmap',
            template='plotly_white',
            height=600,
            width=700
        )
        
        return {
            'type': 'heatmap',
            'plotly_json': fig.to_json()
        }
    
    def create_pie_chart(
        self,
        df: pd.DataFrame,
        column: str,
        title: Optional[str] = None,
        top_n: Optional[int] = None
    ) -> Dict[str, Any]:
        logger.info(f"Creating pie chart for {column}")
        
        if column not in df.columns:
            raise ValueError(f"Column '{column}' not found")
        
        value_counts = df[column].value_counts()
        
        if top_n:
            value_counts = value_counts.head(top_n)
        
        fig = go.Figure(data=[go.Pie(
            labels=value_counts.index,
            values=value_counts.values,
            hole=0.3
        )])
        
        fig.update_layout(
            title=title or f'Distribution of {column}',
            template='plotly_white',
            height=500
        )
        
        return {
            'type': 'pie',
            'column': column,
            'plotly_json': fig.to_json()
        }
    
    def create_time_series(
        self,
        df: pd.DataFrame,
        time_column: str,
        value_columns: List[str],
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info(f"Creating time series plot")
        
        fig = go.Figure()
        
        for col in value_columns:
            if col in df.columns:
                fig.add_trace(go.Scatter(
                    x=df[time_column],
                    y=df[col],
                    mode='lines',
                    name=col
                ))
        
        fig.update_layout(
            title=title or 'Time Series',
            xaxis_title=time_column,
            yaxis_title='Value',
            template='plotly_white',
            height=500,
            hovermode='x unified'
        )
        
        return {
            'type': 'timeseries',
            'time_column': time_column,
            'value_columns': value_columns,
            'plotly_json': fig.to_json()
        }
    
    def create_prediction_plot(
        self,
        historical_values: List[float],
        predictions: List[float],
        title: Optional[str] = None
    ) -> Dict[str, Any]:
        logger.info("Creating prediction plot")
        
        historical_x = list(range(len(historical_values)))
        prediction_x = list(range(len(historical_values), len(historical_values) + len(predictions)))
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=historical_x,
            y=historical_values,
            mode='lines+markers',
            name='Historical',
            line=dict(color='steelblue')
        ))
        
        fig.add_trace(go.Scatter(
            x=prediction_x,
            y=predictions,
            mode='lines+markers',
            name='Predicted',
            line=dict(color='orange', dash='dash')
        ))
        
        fig.update_layout(
            title=title or 'Prediction Plot',
            xaxis_title='Time Period',
            yaxis_title='Value',
            template='plotly_white',
            height=500
        )
        
        return {
            'type': 'prediction',
            'plotly_json': fig.to_json()
        }
    
    def create_multi_plot_dashboard(
        self,
        df: pd.DataFrame,
        plot_configs: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        logger.info("Creating multi-plot dashboard")
        
        plots = []
        
        for config in plot_configs:
            plot_type = config.get('type')
            
            try:
                if plot_type == 'histogram':
                    plot = self.create_histogram(df, **config.get('params', {}))
                elif plot_type == 'scatter':
                    plot = self.create_scatter_plot(df, **config.get('params', {}))
                elif plot_type == 'line':
                    plot = self.create_line_plot(df, **config.get('params', {}))
                elif plot_type == 'bar':
                    plot = self.create_bar_chart(df, **config.get('params', {}))
                elif plot_type == 'box':
                    plot = self.create_box_plot(df, **config.get('params', {}))
                elif plot_type == 'pie':
                    plot = self.create_pie_chart(df, **config.get('params', {}))
                elif plot_type == 'heatmap':
                    plot = self.create_correlation_heatmap(df, **config.get('params', {}))
                else:
                    logger.warning(f"Unknown plot type: {plot_type}")
                    continue
                
                plots.append(plot)
            
            except Exception as e:
                logger.error(f"Error creating {plot_type} plot: {str(e)}")
        
        return plots
    
    def auto_visualize(self, df: pd.DataFrame) -> List[Dict[str, Any]]:
        logger.info("Auto-generating visualizations")
        
        plots = []
        
        numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
        categorical_cols = df.select_dtypes(include=['object', 'category']).columns.tolist()
        
        if len(numeric_cols) >= 2:
            try:
                plots.append(self.create_correlation_heatmap(df))
            except Exception as e:
                logger.error(f"Error creating heatmap: {e}")
        
        for col in numeric_cols[:3]:
            try:
                plots.append(self.create_histogram(df, col))
            except Exception as e:
                logger.error(f"Error creating histogram for {col}: {e}")
        
        if len(numeric_cols) >= 2:
            try:
                plots.append(self.create_scatter_plot(df, numeric_cols[0], numeric_cols[1]))
            except Exception as e:
                logger.error(f"Error creating scatter plot: {e}")
        
        for col in categorical_cols[:2]:
            try:
                plots.append(self.create_pie_chart(df, col, top_n=10))
            except Exception as e:
                logger.error(f"Error creating pie chart for {col}: {e}")
        
        if len(numeric_cols) >= 1:
            try:
                plots.append(self.create_box_plot(df, numeric_cols[:4]))
            except Exception as e:
                logger.error(f"Error creating box plot: {e}")
        
        return plots
