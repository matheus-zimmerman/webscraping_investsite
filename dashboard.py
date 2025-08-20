#!/usr/bin/env python3
"""
📊 DASHBOARD INTERATIVO DE ANÁLISE DE AÇÕES
Sistema completo de análise e comparação de dados do mercado de ações brasileiro
"""

import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import os
import glob
from datetime import datetime, timedelta
import subprocess
import sys
import time

# Configuração da página
st.set_page_config(
    page_title="📊 Dashboard de Ações - InvestSite", 
    page_icon="📈",
    layout="wide",
    initial_sidebar_state="expanded"
)

class StockDashboard:
    def __init__(self):
        self.data = None
        self.filtered_data = None
        
    def load_latest_data(self):
        """Carrega o arquivo Excel mais recente"""
        try:
            # Procura por arquivos de dados
            files = glob.glob("stocks_data_*.xlsx")
            if not files:
                return None, "Nenhum arquivo de dados encontrado!"
            
            # Pega o arquivo mais recente
            latest_file = max(files, key=os.path.getctime)
            
            # Carrega os dados
            df = pd.read_excel(latest_file)
            
            # Informações do arquivo
            file_time = datetime.fromtimestamp(os.path.getctime(latest_file))
            age_hours = (datetime.now() - file_time).total_seconds() / 3600
            
            return df, f"✅ Dados carregados: {latest_file} ({len(df)} ações, {age_hours:.1f}h atrás)"
            
        except Exception as e:
            return None, f"❌ Erro ao carregar dados: {str(e)}"
    
    def run_scraper(self):
        """Executa o scraper para atualizar dados"""
        try:
            # Configura o ambiente para executar o scraper
            env = os.environ.copy()
            env['PYTHONPATH'] = os.getcwd()
            env['PYTHONIOENCODING'] = 'utf-8'  # Força UTF-8 no Windows
            
            # Cria um script temporário para executar o fluxo super otimizado
            script_content = '''import sys
import os
import io
sys.path.append(os.getcwd())

# Configura codificacao UTF-8 para Windows
if sys.platform == "win32":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

from stocks import StocksScraper

def run_super_optimized():
    """Executa o fluxo super otimizado (8 threads)"""
    scraper = StocksScraper(use_selenium=False, max_workers=8, batch_size=30)
    
    print("Iniciando atualizacao SUPER OTIMIZADA...")
    print("Configuracao: 8 threads, lotes de 30 acoes")
    
    # Obtém códigos das ações
    stock_codes = scraper.get_stock_codes()
    if not stock_codes:
        print("Erro ao obter codigos das acoes")
        return False
    
    print(f"{len(stock_codes)} acoes serao processadas")
    
    # Executa scraping
    scraper.scrape_all_stocks(stock_codes)
    
    # Salva resultados
    scraper.save_results()
    
    return True

if __name__ == "__main__":
    run_super_optimized()
'''
            
            # Salva o script temporário
            with open('temp_scraper.py', 'w', encoding='utf-8') as f:
                f.write(script_content)
            
            # Executa o scraper
            process = subprocess.run([sys.executable, 'temp_scraper.py'], 
                                   capture_output=True, text=True, timeout=600, env=env,
                                   encoding='utf-8', errors='ignore')
            
            # Remove o script temporário
            if os.path.exists('temp_scraper.py'):
                os.remove('temp_scraper.py')
            
            if process.returncode == 0:
                return True, "✅ Dados atualizados com sucesso!"
            else:
                return False, f"❌ Erro no scraping: {process.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "⏰ Timeout: Scraping demorou mais que 10 minutos"
        except Exception as e:
            return False, f"❌ Erro inesperado: {str(e)}"
    
    def create_comparison_charts(self, stock1_data, stock2_data, stock1_name, stock2_name):
        """Cria gráficos de comparação entre duas ações"""
        
        # Métricas para comparação
        comparison_metrics = [
            ('Indicador - Preço/Lucro', 'P/L'),
            ('Indicador - Preço/VPA', 'P/VPA'),
            ('Indicador - ROE', 'ROE (%)'),
            ('Indicador - Dividend Yield', 'Dividend Yield (%)'),
            ('DRE 12M - Receita Líquida', 'Receita 12M'),
            ('DRE 12M - Lucro Líquido', 'Lucro 12M'),
            ('DRE 12M - EBITDA', 'EBITDA 12M')
        ]
        
        # Prepara dados para comparação
        comparison_data = []
        for field, label in comparison_metrics:
            if field in stock1_data.columns and field in stock2_data.columns:
                val1 = stock1_data[field].iloc[0] if not pd.isna(stock1_data[field].iloc[0]) else 0
                val2 = stock2_data[field].iloc[0] if not pd.isna(stock2_data[field].iloc[0]) else 0
                
                comparison_data.append({
                    'Métrica': label,
                    stock1_name: val1,
                    stock2_name: val2
                })
        
        df_comparison = pd.DataFrame(comparison_data)
        
        # Gráfico de barras comparativo
        fig = go.Figure(data=[
            go.Bar(name=stock1_name, x=df_comparison['Métrica'], y=df_comparison[stock1_name]),
            go.Bar(name=stock2_name, x=df_comparison['Métrica'], y=df_comparison[stock2_name])
        ])
        
        fig.update_layout(
            title=f'📊 Comparação: {stock1_name} vs {stock2_name}',
            barmode='group',
            height=500,
            xaxis_tickangle=-45
        )
        
        return fig, df_comparison
    
    def create_time_comparison_chart(self, stock_data, stock_name):
        """Cria comparação entre dados 12M vs 3M"""
        
        metrics_12m_3m = [
            ('DRE 12M - Receita Líquida', 'DRE 3M - Receita Líquida', 'Receita Líquida'),
            ('DRE 12M - Lucro Líquido', 'DRE 3M - Lucro Líquido', 'Lucro Líquido'),
            ('DRE 12M - EBITDA', 'DRE 3M - EBITDA', 'EBITDA'),
            ('DRE 12M - EBIT', 'DRE 3M - EBIT', 'EBIT')
        ]
        
        comparison_data = []
        for field_12m, field_3m, label in metrics_12m_3m:
            if field_12m in stock_data.columns and field_3m in stock_data.columns:
                val_12m = stock_data[field_12m].iloc[0] if not pd.isna(stock_data[field_12m].iloc[0]) else 0
                val_3m = stock_data[field_3m].iloc[0] if not pd.isna(stock_data[field_3m].iloc[0]) else 0
                
                # Anualiza o valor 3M (multiplica por 4)
                val_3m_annual = val_3m * 4
                
                comparison_data.append({
                    'Métrica': label,
                    'Últimos 12 Meses': val_12m,
                    'Último Trimestre (Anualizado)': val_3m_annual
                })
        
        df_time = pd.DataFrame(comparison_data)
        
        fig = go.Figure(data=[
            go.Bar(name='Últimos 12 Meses', x=df_time['Métrica'], y=df_time['Últimos 12 Meses']),
            go.Bar(name='Último Trimestre (Anualizado)', x=df_time['Métrica'], y=df_time['Último Trimestre (Anualizado)'])
        ])
        
        fig.update_layout(
            title=f'📈 {stock_name}: Comparação Temporal (12M vs 3M Anualizado)',
            barmode='group',
            height=500
        )
        
        return fig, df_time
    
    def get_available_filters(self, df):
        """Retorna filtros disponíveis baseados nos dados"""
        filters = {}
        
        # Filtros categóricos
        categorical_fields = ['Situação Emissor', 'Setor', 'Empresa']
        
        for field in categorical_fields:
            if field in df.columns:
                unique_values = df[field].dropna().unique()
                if len(unique_values) > 1 and len(unique_values) < 50:  # Evita campos com muitos valores
                    filters[field] = sorted(unique_values)
        
        # Filtros numéricos
        numeric_fields = [
            'Indicador - Preço/Lucro',
            'Indicador - Preço/VPA', 
            'Indicador - ROE',
            'Indicador - Dividend Yield',
            'Indicador - Market Cap Empresa',
            'DRE 12M - Receita Líquida'
        ]
        
        for field in numeric_fields:
            if field in df.columns:
                values = df[field].dropna()
                if len(values) > 0:
                    filters[f"{field}_range"] = (float(values.min()), float(values.max()))
        
        return filters

def main():
    # Título principal
    st.title("📊 Dashboard Interativo de Análise de Ações")
    st.markdown("*Sistema completo de análise e comparação do mercado brasileiro*")
    
    # Inicializa o dashboard
    dashboard = StockDashboard()
    
    # Sidebar para controles
    st.sidebar.title("🎛️ Controles")
    
    # Botão de atualização de dados
    st.sidebar.markdown("### 🔄 Atualização de Dados")
    if st.sidebar.button("🚀 Atualizar Dados (Super Otimizado)", help="Executa scraping com 8 threads para atualizar todos os dados"):
        with st.spinner("⏳ Executando scraping... Isso pode demorar alguns minutos."):
            success, message = dashboard.run_scraper()
            if success:
                st.sidebar.success(message)
                st.rerun()
            else:
                st.sidebar.error(message)
    
    # Carrega dados
    data, status_message = dashboard.load_latest_data()
    
    if data is None:
        st.error(status_message)
        st.info("💡 Clique em 'Atualizar Dados' na sidebar para fazer o primeiro scraping")
        return
    
    st.sidebar.success(status_message)
    
    # Filtros na sidebar
    st.sidebar.markdown("### 🔍 Filtros")
    
    available_filters = dashboard.get_available_filters(data)
    applied_filters = {}
    
    # Filtros categóricos
    for field, values in available_filters.items():
        if not field.endswith('_range'):
            selected = st.sidebar.multiselect(
                f"📋 {field}", 
                values, 
                help=f"Filtrar por {field}"
            )
            if selected:
                applied_filters[field] = selected
    
    # Filtros numéricos
    for field, values in available_filters.items():
        if field.endswith('_range'):
            min_val, max_val = values
            field_name = field.replace('_range', '')
            selected_range = st.sidebar.slider(
                f"📊 {field_name.split(' - ')[-1] if ' - ' in field_name else field_name}",
                float(min_val), 
                float(max_val), 
                (float(min_val), float(max_val)),
                help=f"Filtrar por faixa de {field_name}"
            )
            if selected_range != (min_val, max_val):
                applied_filters[field_name] = selected_range
    
    # Aplica filtros
    filtered_data = data.copy()
    for field, filter_value in applied_filters.items():
        if field in data.columns:
            if isinstance(filter_value, tuple):  # Filtro numérico
                filtered_data = filtered_data[
                    (filtered_data[field] >= filter_value[0]) & 
                    (filtered_data[field] <= filter_value[1])
                ]
            else:  # Filtro categórico
                filtered_data = filtered_data[filtered_data[field].isin(filter_value)]
    
    dashboard.filtered_data = filtered_data
    
    # Estatísticas gerais
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("📈 Total de Ações", len(filtered_data))
    
    with col2:
        if 'Indicador - Market Cap Empresa' in filtered_data.columns:
            total_market_cap = filtered_data['Indicador - Market Cap Empresa'].sum()
            st.metric("💰 Market Cap Total", f"R$ {total_market_cap/1e12:.1f}T")
    
    with col3:
        if 'Indicador - Dividend Yield' in filtered_data.columns:
            avg_dy = filtered_data['Indicador - Dividend Yield'].mean()
            st.metric("💎 DY Médio", f"{avg_dy:.2f}%")
    
    with col4:
        if 'Indicador - Preço/Lucro' in filtered_data.columns:
            avg_pl = filtered_data['Indicador - Preço/Lucro'].mean()
            st.metric("📊 P/L Médio", f"{avg_pl:.1f}")
    
    # Tabs para diferentes análises
    tab1, tab2, tab3, tab4, tab5 = st.tabs([
        "📊 Visão Geral", 
        "🔍 Análise Individual", 
        "⚖️ Comparação Entre Ações",
        "📈 Análise Temporal (12M vs 3M)",
        "📋 Dados Brutos"
    ])
    
    with tab1:
        st.header("📊 Visão Geral do Mercado")
        
        # Gráficos de distribuição
        col1, col2 = st.columns(2)
        
        with col1:
            if 'Indicador - Preço/Lucro' in filtered_data.columns:
                fig = px.histogram(
                    filtered_data, 
                    x='Indicador - Preço/Lucro', 
                    title="📈 Distribuição P/L",
                    nbins=30
                )
                st.plotly_chart(fig, use_container_width=True, key="pl_histogram")
        
        with col2:
            if 'Indicador - Dividend Yield' in filtered_data.columns:
                fig = px.histogram(
                    filtered_data, 
                    x='Indicador - Dividend Yield', 
                    title="💎 Distribuição Dividend Yield",
                    nbins=30
                )
                st.plotly_chart(fig, use_container_width=True, key="dy_histogram")
        
        # Top ações
        st.subheader("🏆 Top Ações")
        
        col1, col2 = st.columns(2)
        
        with col1:
            if 'Indicador - Dividend Yield' in filtered_data.columns:
                top_dy = filtered_data.nlargest(10, 'Indicador - Dividend Yield')[['Código', 'Empresa', 'Indicador - Dividend Yield']]
                st.markdown("**💎 Maiores Dividend Yields**")
                st.dataframe(top_dy, use_container_width=True)
        
        with col2:
            if 'Indicador - Market Cap Empresa' in filtered_data.columns:
                top_market_cap = filtered_data.nlargest(10, 'Indicador - Market Cap Empresa')[['Código', 'Empresa', 'Indicador - Market Cap Empresa']]
                st.markdown("**💰 Maiores Market Caps**")
                st.dataframe(top_market_cap, use_container_width=True)
    
    with tab2:
        st.header("🔍 Análise Individual de Ação")
        
        # Seleção de ação
        available_stocks = sorted(filtered_data['Código'].unique()) if 'Código' in filtered_data.columns else []
        
        if available_stocks:
            selected_stock = st.selectbox("📈 Escolha uma ação:", available_stocks)
            
            if selected_stock:
                stock_data = filtered_data[filtered_data['Código'] == selected_stock]
                
                if not stock_data.empty:
                    # Informações básicas
                    col1, col2, col3 = st.columns(3)
                    
                    with col1:
                        empresa = stock_data['Empresa'].iloc[0] if 'Empresa' in stock_data.columns else 'N/A'
                        st.markdown(f"**🏢 Empresa:** {empresa}")
                        
                        preco = stock_data['Último Preço de Fechamento'].iloc[0] if 'Último Preço de Fechamento' in stock_data.columns else 'N/A'
                        st.markdown(f"**💰 Preço:** R$ {preco}")
                    
                    with col2:
                        setor = stock_data['Setor'].iloc[0] if 'Setor' in stock_data.columns else 'N/A'
                        st.markdown(f"**🏭 Setor:** {setor}")
                        
                        pl = stock_data['Indicador - Preço/Lucro'].iloc[0] if 'Indicador - Preço/Lucro' in stock_data.columns else 'N/A'
                        st.markdown(f"**📊 P/L:** {pl}")
                    
                    with col3:
                        dy = stock_data['Indicador - Dividend Yield'].iloc[0] if 'Indicador - Dividend Yield' in stock_data.columns else 'N/A'
                        st.markdown(f"**💎 DY:** {dy}%")
                        
                        earnings_yield = stock_data['Earnings Yield (%)'].iloc[0] if 'Earnings Yield (%)' in stock_data.columns else 'N/A'
                        st.markdown(f"**📈 Earnings Yield:** {earnings_yield}")
                    
                    # Gráfico temporal da própria ação
                    fig, df_time = dashboard.create_time_comparison_chart(stock_data, selected_stock)
                    st.plotly_chart(fig, use_container_width=True, key=f"individual_time_comparison_{selected_stock}")
                    
                    # Tabela com dados detalhados
                    st.subheader(f"📋 Dados Detalhados - {selected_stock}")
                    
                    # Seleciona campos mais relevantes
                    relevant_fields = [
                        'Código', 'Empresa', 'Setor',
                        'Último Preço de Fechamento',
                        'Indicador - Preço/Lucro', 'Indicador - Preço/VPA', 'Indicador - ROE',
                        'Indicador - Dividend Yield', 'Earnings Yield (%)',
                        'DRE 12M - Receita Líquida', 'DRE 12M - Lucro Líquido', 'DRE 12M - EBITDA',
                        'DRE 3M - Receita Líquida', 'DRE 3M - Lucro Líquido', 'DRE 3M - EBITDA'
                    ]
                    
                    # Filtra apenas campos que existem
                    existing_fields = [f for f in relevant_fields if f in stock_data.columns]
                    detailed_data = stock_data[existing_fields].T
                    detailed_data.columns = ['Valor']
                    
                    st.dataframe(detailed_data, use_container_width=True)
        else:
            st.info("📊 Nenhuma ação disponível com os filtros aplicados")
    
    with tab3:
        st.header("⚖️ Comparação Entre Ações")
        
        available_stocks = sorted(filtered_data['Código'].unique()) if 'Código' in filtered_data.columns else []
        
        if len(available_stocks) >= 2:
            col1, col2 = st.columns(2)
            
            with col1:
                stock1 = st.selectbox("📈 Primeira ação:", available_stocks, key="stock1")
            
            with col2:
                stock2 = st.selectbox("📉 Segunda ação:", [s for s in available_stocks if s != stock1], key="stock2")
            
            if stock1 and stock2:
                stock1_data = filtered_data[filtered_data['Código'] == stock1]
                stock2_data = filtered_data[filtered_data['Código'] == stock2]
                
                # Gráfico de comparação
                fig, comparison_df = dashboard.create_comparison_charts(
                    stock1_data, stock2_data, stock1, stock2
                )
                st.plotly_chart(fig, use_container_width=True, key=f"comparison_{stock1}_{stock2}")
                
                # Tabela de comparação
                st.subheader(f"📊 Tabela Comparativa: {stock1} vs {stock2}")
                st.dataframe(comparison_df, use_container_width=True)
        else:
            st.info("📊 Pelo menos 2 ações são necessárias para comparação")
    
    with tab4:
        st.header("📈 Análise Temporal: 12 Meses vs Trimestre")
        
        available_stocks = sorted(filtered_data['Código'].unique()) if 'Código' in filtered_data.columns else []
        
        if available_stocks:
            selected_stocks = st.multiselect(
                "📈 Escolha ações para análise temporal:", 
                available_stocks,
                default=available_stocks[:3] if len(available_stocks) >= 3 else available_stocks
            )
            
            for stock in selected_stocks:
                stock_data = filtered_data[filtered_data['Código'] == stock]
                if not stock_data.empty:
                    fig, df_time = dashboard.create_time_comparison_chart(stock_data, stock)
                    st.plotly_chart(fig, use_container_width=True, key=f"temporal_analysis_{stock}")
        else:
            st.info("📊 Nenhuma ação disponível para análise temporal")
    
    with tab5:
        st.header("📋 Dados Brutos")
        st.markdown(f"**Total de registros:** {len(filtered_data)}")
        
        # Opção de download
        csv = filtered_data.to_csv(index=False)
        st.download_button(
            label="💾 Download dos dados filtrados (CSV)",
            data=csv,
            file_name=f"acoes_filtradas_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
            mime="text/csv"
        )
        
        # Exibe dados
        st.dataframe(filtered_data, use_container_width=True)

if __name__ == "__main__":
    main()
