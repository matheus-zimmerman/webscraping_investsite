"""
🤖 SISTEMA DE WEB SCRAPING DE AÇÕES - INVESTSITE
================================================

Este script automatiza o processo de:
1. Acessar https://www.investsite.com.br/seleciona_acoes.php
2. Clicar no botão "Procurar Ações"
3. Selecionar "Todos" na tabela de resultados
4. Extrair TODOS os códigos das ações da primeira coluna da tabela
5. Fazer scraping dos dados de TODAS as ações (115+ campos cada)
6. Salvar em Excel com dados completos

🆕 VERSÃO COMPLETA: Busca automática de TODAS as ações
   - Não há limitações de quantidade
   - Extrai todos os códigos disponíveis na tabela
   - Processa todas as ações encontradas
   - Suporte a Selenium e requests

Autor: Matheus Zimmerman
Data: 19/08/2025
"""

import os
import time
import glob
import pandas as pd
from datetime import datetime
import requests
from bs4 import BeautifulSoup
from concurrent.futures import ThreadPoolExecutor, as_completed
from threading import Lock
import re

# Tentativa de importar Selenium (opcional)
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False

class DataCleaner:
    """Classe para limpeza e formatação automática dos dados"""
    
    @staticmethod
    def clean_currency_to_float(value):
        """
        Remove R$ e converte para float
        Exemplo: 'R$ 25,50' -> 25.50, '- R$ 0,18' -> -0.18
        """
        if not value or value == 'N/A' or value == '-':
            return None
        try:
            original_value = str(value).strip()
            
            # Detecta se é negativo (pode estar antes ou depois do R$)
            is_negative = False
            if original_value.startswith('-') or original_value.startswith('- ') or 'R$ -' in original_value or 'R$-' in original_value:
                is_negative = True
            
            # Remove R$, sinais e normaliza
            clean_val = original_value.replace('R$', '').replace('R ', '').replace('-', '').replace(' ', '').strip()
            
            # Remove pontos de milhares mas mantém vírgula decimal
            # Identifica se a vírgula é decimal (últimos 3 caracteres) ou separador de milhares
            if ',' in clean_val:
                parts = clean_val.split(',')
                if len(parts[-1]) <= 2:  # Vírgula decimal
                    # Remove pontos de milhares e substitui vírgula por ponto
                    clean_val = clean_val.replace('.', '').replace(',', '.')
                else:  # Vírgula de milhares
                    clean_val = clean_val.replace(',', '').replace('.', '')
            else:
                clean_val = clean_val.replace('.', '')
            
            # Extrai apenas números e ponto decimal (sem sinal, pois já tratamos)
            match = re.search(r'([\d.]+)', clean_val)
            if match:
                number = float(match.group(1))
                result = round(number, 2)
                return -result if is_negative else result
        except Exception as e:
            print(f"⚠️  Erro ao limpar moeda '{value}': {e}")
        return None
    
    @staticmethod
    def clean_currency_with_scale_to_float(value):
        """
        Remove R$ e converte considerando escala (K, M, B, mil)
        Exemplos: 
        'R$ 1,5 M' -> 1500000.00
        'R$ 250,30 mil' -> 250300.00
        'R$ 2,1 B' -> 2100000000.00
        '- R$ 7,15 B' -> -7150000000.00
        '-R$ 1,5 B' -> -1500000000.00
        """
        if not value or value == 'N/A' or value == '-':
            return None
        try:
            original_value = str(value).strip()
            
            # Detecta se é negativo (pode estar antes ou depois do R$)
            is_negative = False
            if original_value.startswith('-') or original_value.startswith('- ') or 'R$ -' in original_value or 'R$-' in original_value:
                is_negative = True
            
            # Remove R$, sinais e normaliza
            clean_val = original_value.replace('R$', '').replace('R ', '').replace('-', '').replace(' ', '').strip().upper()
            
            # Detecta escala (ordem importante: MIL antes de M)
            scale_multiplier = 1
            if 'B' in clean_val:
                scale_multiplier = 1_000_000_000  # Bilhão
                clean_val = clean_val.replace('B', '').strip()
            elif 'MIL' in clean_val:
                scale_multiplier = 1_000  # Mil (formato brasileiro)
                clean_val = clean_val.replace('MIL', '').strip()
            elif 'M' in clean_val:
                scale_multiplier = 1_000_000  # Milhão
                clean_val = clean_val.replace('M', '').strip()
            elif 'K' in clean_val:
                scale_multiplier = 1_000  # Mil (formato internacional)
                clean_val = clean_val.replace('K', '').strip()
            
            # Trata formatação brasileira de números
            if ',' in clean_val and '.' in clean_val:
                # Formato: 1.234.567,89 - pontos são separadores de milhares
                clean_val = clean_val.replace('.', '').replace(',', '.')
            elif ',' in clean_val:
                parts = clean_val.split(',')
                if len(parts[-1]) <= 2:  # Vírgula decimal
                    clean_val = clean_val.replace(',', '.')
                else:  # Vírgula de milhares
                    clean_val = clean_val.replace(',', '')
            elif '.' in clean_val:
                parts = clean_val.split('.')
                if len(parts[-1]) <= 2:  # Ponto decimal (formato americano)
                    pass  # Já está correto
                else:  # Ponto de milhares
                    clean_val = clean_val.replace('.', '')
                    
            # Extrai número (apenas positivo, pois já tratamos o sinal)
            match = re.search(r'([\d.]+)', clean_val)
            if match:
                number = float(match.group(1))
                result = round(number * scale_multiplier, 2)
                return -result if is_negative else result
        except Exception as e:
            print(f"⚠️  Erro ao limpar moeda com escala '{value}': {e}")
        return None
    
    @staticmethod
    def clean_percentage_to_float(value):
        """
        Remove % e converte para float
        Trata casos especiais: '-18.000,00%' -> -18.00 (dividindo por 1000)
        """
        if not value or value == 'N/A' or value == '-':
            return None
        try:
            # Remove % e espaços
            clean_val = str(value).replace('%', '').strip()
            
            # CASO ESPECIAL: Percentuais com separador de milhares
            # O site InvestSite formata percentuais com 3 casas extras
            # Ex: -18.000,00% = -18000.00 mas deveria ser -18.00%
            if '.' in clean_val and ',' in clean_val:
                # Formato brasileiro com separador de milhares em percentual
                # Remove pontos (separadores de milhares) e substitui vírgula por ponto
                clean_val = clean_val.replace('.', '').replace(',', '.')
                
                # TODOS os casos com separador de milhares devem ser divididos por 1000
                # Isso corrige a formatação incorreta do site
                temp_result = float(clean_val)
                clean_val = str(temp_result / 1000)
                        
            elif ',' in clean_val:
                # Apenas vírgula: assume que é decimal brasileiro normal
                clean_val = clean_val.replace(',', '.')
            elif '.' in clean_val:
                # Apenas ponto: verifica se é decimal ou separador
                parts = clean_val.split('.')
                if len(parts[-1]) <= 2:  # Ponto decimal (formato americano)
                    pass  # Já está correto
                else:  # Ponto de milhares sem vírgula (ex: 18.000)
                    # Também precisa ser dividido por 1000 se for muito grande
                    temp_result = float(clean_val.replace('.', ''))
                    if abs(temp_result) >= 1000:  # Provavelmente formatação incorreta
                        clean_val = str(temp_result / 1000)
                    else:
                        clean_val = clean_val.replace('.', '')
                    
            # Extrai número (incluindo negativos)
            match = re.search(r'([-+]?[\d.]+)', clean_val)
            if match:
                return round(float(match.group(1)), 2)
        except Exception as e:
            print(f"⚠️  Erro ao limpar percentual '{value}': {e}")
        return None
    
    @staticmethod
    def clean_ratio_to_float(value):
        """
        Converte ratios/múltiplos para float
        Exemplo: '8,50' -> 8.50, '1.234,56' -> 1234.56
        """
        if not value or value == 'N/A' or value == '-':
            return None
        try:
            clean_val = str(value).strip()
            
            # Trata formatação brasileira de números
            if ',' in clean_val and '.' in clean_val:
                # Formato: 1.234,56 - ponto é separador de milhares
                clean_val = clean_val.replace('.', '').replace(',', '.')
            elif ',' in clean_val:
                parts = clean_val.split(',')
                if len(parts[-1]) <= 2:  # Vírgula decimal
                    clean_val = clean_val.replace(',', '.')
                else:  # Vírgula de milhares
                    clean_val = clean_val.replace(',', '')
            elif '.' in clean_val:
                parts = clean_val.split('.')
                if len(parts[-1]) <= 2:  # Ponto decimal (formato americano)
                    pass  # Já está correto
                else:  # Ponto de milhares
                    clean_val = clean_val.replace('.', '')
                    
            # Extrai número (incluindo negativos)
            match = re.search(r'([-+]?[\d.]+)', clean_val)
            if match:
                return round(float(match.group(1)), 2)
        except Exception as e:
            print(f"⚠️  Erro ao limpar ratio '{value}': {e}")
        return None
    
    @staticmethod
    def clean_date_to_format(value):
        """
        Converte datas para formato DD/MM/YYYY
        """
        if not value or value == 'N/A' or value == '-':
            return None
        try:
            # Tenta diferentes formatos de data
            date_str = str(value).strip()
            
            # Formatos comuns: DD/MM/YYYY, YYYY-MM-DD, DD-MM-YYYY
            for fmt in ['%d/%m/%Y', '%Y-%m-%d', '%d-%m-%Y', '%d/%m/%y']:
                try:
                    date_obj = datetime.strptime(date_str, fmt)
                    return date_obj.strftime('%d/%m/%Y')
                except:
                    continue
        except:
            pass
        return value  # Retorna original se não conseguir converter
    
    @staticmethod
    def clean_integer(value):
        """
        Converte para número inteiro
        Exemplo: '1.250.000.000' -> 1250000000
        """
        if not value or value == 'N/A' or value == '-':
            return None
        try:
            # Remove pontos e vírgulas de separadores de milhares
            clean_val = str(value).replace('.', '').replace(',', '').strip()
            # Remove outros caracteres não numéricos exceto sinais
            clean_val = re.sub(r'[^\d\-+]', '', clean_val)
            # Extrai apenas números
            match = re.search(r'([-+]?\d+)', clean_val)
            if match:
                return int(match.group(1))
        except Exception as e:
            print(f"⚠️  Erro ao limpar inteiro '{value}': {e}")
        return None

class StocksScraper:
    def __init__(self, use_selenium=True, max_workers=5, batch_size=20):
        """
        Inicializa o scraper com otimizações
        
        Args:
            use_selenium (bool): Se True, tenta usar Selenium. Se False ou não disponível, usa requests
            max_workers (int): Número de threads para processamento paralelo
            batch_size (int): Tamanho dos lotes para processamento
        """
        self.use_selenium = use_selenium and SELENIUM_AVAILABLE
        self.max_workers = max_workers
        self.batch_size = batch_size
        self.stocks_data = []
        self.download_dir = os.path.abspath(".")
        self.data_lock = Lock()  # Para thread safety
        
        if not self.use_selenium:
            # Configura sessão requests otimizada
            self.session = requests.Session()
            self.session.headers.update({
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
            })
            # Pool de conexões otimizado
            adapter = requests.adapters.HTTPAdapter(
                pool_connections=20,
                pool_maxsize=20,
                max_retries=3
            )
            self.session.mount('http://', adapter)
            self.session.mount('https://', adapter)
        
        print(f"🚀 Scraper inicializado - Modo: {'Selenium' if self.use_selenium else 'Requests'}")
        print(f"⚡ Otimizações: {max_workers} threads, lotes de {batch_size} ações")
    
    def get_stock_codes_from_table(self):
        """Busca códigos das ações diretamente da tabela do InvestSite"""
        url = "https://www.investsite.com.br/seleciona_acoes.php"
        
        try:
            if self.use_selenium:
                return self._get_codes_with_selenium(url)
            else:
                return self._get_codes_with_requests(url)
        except Exception as e:
            print(f"❌ Erro ao buscar códigos da tabela: {e}")
            return []
    
    def _get_codes_with_selenium(self, url):
        """Busca códigos usando Selenium"""
        driver = self.setup_selenium_driver()
        if not driver:
            return []
            
        try:
            print("🌐 Acessando página do InvestSite...")
            driver.get(url)
            time.sleep(3)
            
            # Clica no botão "Procurar Ações"
            print("🔍 Clicando em 'Procurar Ações'...")
            search_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(@class, 'btn-primary') and contains(text(), 'Procurar Ações')]")
            search_button.click()
            
            # Aguarda a página carregar
            print("⏳ Aguardando tabela carregar...")
            time.sleep(10)
            
            # Seleciona "Todos" no seletor de quantidade
            print("📋 Selecionando 'Todos' na tabela...")
            try:
                select_element = driver.find_element(By.CSS_SELECTOR, "select.datatable-selector[name='per-page']")
                from selenium.webdriver.support.ui import Select
                select = Select(select_element)
                select.select_by_value("-1")  # Valor "Todos"
                time.sleep(5)  # Aguarda recarregar a tabela
                print("✅ Tabela expandida para mostrar todas as ações")
            except Exception as e:
                print(f"⚠️  Não foi possível expandir tabela: {e}")
            
            # Busca todos os códigos na primeira coluna
            print("📊 Extraindo códigos das ações...")
            stock_codes = []
            
            # Procura por links na primeira coluna (formato: /principais_indicadores.php?cod_negociacao=CODIGO)
            code_links = driver.find_elements(By.CSS_SELECTOR, "td.text-start.text-nowrap.itm1 a")
            
            for link in code_links:
                href = link.get_attribute('href')
                if href and 'cod_negociacao=' in href:
                    code = href.split('cod_negociacao=')[1]
                    if code and len(code) >= 4:  # Códigos de ação têm pelo menos 4 caracteres
                        stock_codes.append(code)
            
            print(f"✅ {len(stock_codes)} códigos encontrados na tabela")
            if stock_codes:
                print(f"📋 Primeiros códigos: {', '.join(stock_codes[:10])}")
                if len(stock_codes) > 10:
                    print(f"   ... e mais {len(stock_codes) - 10} códigos")
            
            return stock_codes
                
        except Exception as e:
            print(f"❌ Erro ao buscar códigos com Selenium: {e}")
            return []
        finally:
            driver.quit()
    
    def _get_codes_with_requests(self, url):
        """Busca códigos usando requests"""
        try:
            print("🌐 Acessando página do InvestSite...")
            response = self.session.get(url)
            response.raise_for_status()
            
            # Primeira requisição - simula clique em "Procurar Ações"
            print("🔍 Procurando formulário correto...")
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Procura o formulário correto (com action selecao_acoes.php)
            form = None
            forms = soup.find_all('form')
            for f in forms:
                action = f.get('action', '')
                if 'selecao_acoes.php' in action:
                    form = f
                    break
            
            if not form:
                print("❌ Formulário de seleção não encontrado")
                return []
            
            form_action = form.get('action', url)
            if not form_action.startswith('http'):
                form_action = f"https://www.investsite.com.br/{form_action.lstrip('/')}"
            
            print(f"📋 Formulário encontrado: {form_action}")
            
            # Coleta dados do formulário
            form_data = {}
            for input_field in form.find_all(['input', 'select']):
                name = input_field.get('name')
                if name:
                    if input_field.name == 'input':
                        inp_type = input_field.get('type', '')
                        if inp_type == 'checkbox':
                            # Para checkboxes, verifica se está marcado
                            if input_field.get('checked'):
                                form_data[name] = input_field.get('value', 'on')
                        else:
                            form_data[name] = input_field.get('value', '')
                    else:  # select
                        selected = input_field.find('option', {'selected': True})
                        if selected:
                            form_data[name] = selected.get('value', '')
                        else:
                            first_option = input_field.find('option')
                            form_data[name] = first_option.get('value', '') if first_option else ''
            
            print("📊 Enviando busca...")
            search_response = self.session.get(form_action, params=form_data)
            search_response.raise_for_status()
            
            # Aguarda um pouco
            print("⏳ Aguardando processamento...")
            time.sleep(3)
            
            # Analisa a página de resultados
            search_soup = BeautifulSoup(search_response.content, 'html.parser')
            
            print("📋 Extraindo códigos das ações da tabela...")
            stock_codes = []
            
            # Procura por tabelas que podem conter os dados
            tables = search_soup.find_all('table')
            print(f"📊 {len(tables)} tabelas encontradas na página")
            
            for table_idx, table in enumerate(tables):
                rows = table.find_all('tr')
                print(f"   Tabela {table_idx + 1}: {len(rows)} linhas")
                
                # Analisa linhas da tabela
                for row_idx, row in enumerate(rows[1:], 1):  # Pula cabeçalho
                    cells = row.find_all(['td', 'th'])
                    if cells:
                        # Procura links na primeira célula
                        first_cell = cells[0]
                        links = first_cell.find_all('a')
                        
                        for link in links:
                            href = link.get('href', '')
                            if 'cod_negociacao=' in href:
                                code = href.split('cod_negociacao=')[1].split('&')[0]  # Remove parâmetros extras
                                if code and len(code) >= 4:
                                    stock_codes.append(code)
                                    if len(stock_codes) % 50 == 0:  # Mostra progresso a cada 50 códigos
                                        print(f"      📊 {len(stock_codes)} códigos processados...")
            
            print(f"✅ {len(stock_codes)} códigos encontrados na tabela")
            if stock_codes:
                print(f"📋 Primeiros códigos: {', '.join(stock_codes[:10])}")
                if len(stock_codes) > 10:
                    print(f"   ... e mais {len(stock_codes) - 10} códigos")
            
            return stock_codes
                
        except Exception as e:
            print(f"❌ Erro ao buscar códigos com requests: {e}")
            return []

    def download_stocks_excel(self):
        """Faz download automático da planilha do InvestSite (método legado)"""
        url = "https://www.investsite.com.br/seleciona_acoes.php"
        
        try:
            if self.use_selenium:
                return self._download_with_selenium(url)
            else:
                return self._download_with_requests(url)
        except Exception as e:
            print(f"❌ Erro no download: {e}")
            return None
    
    def _download_with_selenium(self, url):
        """Download usando Selenium"""
        driver = self.setup_selenium_driver()
        if not driver:
            return None
            
        try:
            print("🌐 Acessando página do InvestSite...")
            driver.get(url)
            time.sleep(3)
            
            # Clica no botão "Procurar Ações"
            print("🔍 Clicando em 'Procurar Ações'...")
            search_button = driver.find_element(By.XPATH, "//button[@type='submit' and contains(@class, 'btn-primary') and contains(text(), 'Procurar Ações')]")
            search_button.click()
            
            # Aguarda a página carregar (15 segundos)
            print("⏳ Aguardando página carregar (15 segundos)...")
            time.sleep(15)
            
            # Clica no botão de download do Excel
            print("📥 Clicando no botão de download do Excel...")
            download_button = driver.find_element(By.ID, "botao_arquivo")
            download_button.click()
            
            print("⏳ Aguardando download...")
            time.sleep(10)  # Aguarda o download
            
            # Procura arquivo baixado
            downloaded_files = glob.glob(os.path.join(self.download_dir, "*.xlsx"))
            if downloaded_files:
                latest_file = max(downloaded_files, key=os.path.getctime)
                print(f"✅ Arquivo baixado: {os.path.basename(latest_file)}")
                return latest_file
            else:
                print("❌ Nenhum arquivo Excel encontrado após download")
                return None
                
        except Exception as e:
            print(f"❌ Erro no download com Selenium: {e}")
            return None
        finally:
            driver.quit()
    
    def _download_with_requests(self, url):
        """Download usando requests - simula o processo de download"""
        try:
            print("🌐 Acessando página do InvestSite...")
            response = self.session.get(url)
            response.raise_for_status()
            
            # Primeira requisição - simula clique em "Procurar Ações"
            print("🔍 Simulando clique em 'Procurar Ações'...")
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Procura o formulário de busca
            form = soup.find('form')
            if form:
                form_action = form.get('action', url)
                if not form_action.startswith('http'):
                    form_action = f"https://www.investsite.com.br/{form_action.lstrip('/')}"
                
                # Coleta dados do formulário
                form_data = {}
                for input_field in form.find_all(['input', 'select']):
                    name = input_field.get('name')
                    if name:
                        if input_field.name == 'input':
                            value = input_field.get('value', '')
                        else:  # select
                            selected = input_field.find('option', {'selected': True})
                            if selected:
                                value = selected.get('value', '')
                            else:
                                first_option = input_field.find('option')
                                value = first_option.get('value', '') if first_option else ''
                        form_data[name] = value
                
                print("📊 Enviando busca...")
                search_response = self.session.post(form_action, data=form_data)
                search_response.raise_for_status()
                
                # Aguarda um pouco (simula o tempo de processamento)
                print("⏳ Aguardando processamento...")
                time.sleep(5)
                
                # Procura pelo link de download na página de resultados
                search_soup = BeautifulSoup(search_response.content, 'html.parser')
                
                # Procura o botão de download do Excel
                download_button = search_soup.find('button', {'id': 'botao_arquivo'})
                if download_button:
                    # Tenta encontrar um link próximo ou dentro do botão
                    parent = download_button.parent
                    download_link = parent.find('a') if parent else None
                    
                    if not download_link:
                        download_link = search_soup.find('a', href=lambda x: x and '.xlsx' in x)
                    
                    if download_link:
                        download_url = download_link['href']
                        if not download_url.startswith('http'):
                            download_url = f"https://www.investsite.com.br/{download_url.lstrip('/')}"
                        
                        print(f"📥 Baixando planilha de: {download_url}")
                        excel_response = self.session.get(download_url)
                        excel_response.raise_for_status()
                        
                        # Salva o arquivo
                        filename = f"stocks_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                        filepath = os.path.join(self.download_dir, filename)
                        
                        with open(filepath, 'wb') as f:
                            f.write(excel_response.content)
                        
                        print(f"✅ Arquivo baixado: {filename}")
                        return filepath
                
                # Se não encontrou o botão, tenta uma abordagem alternativa
                print("🔄 Tentando abordagem alternativa...")
                # Faz uma nova requisição para a mesma página após alguns segundos
                time.sleep(3)
                final_response = self.session.get(form_action)
                final_soup = BeautifulSoup(final_response.content, 'html.parser')
                
                # Procura qualquer link para Excel
                excel_links = final_soup.find_all('a', href=lambda x: x and '.xlsx' in x)
                if excel_links:
                    excel_url = excel_links[0]['href']
                    if not excel_url.startswith('http'):
                        excel_url = f"https://www.investsite.com.br/{excel_url.lstrip('/')}"
                    
                    print(f"📥 Baixando planilha de: {excel_url}")
                    excel_response = self.session.get(excel_url)
                    excel_response.raise_for_status()
                    
                    # Salva o arquivo
                    filename = f"stocks_download_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
                    filepath = os.path.join(self.download_dir, filename)
                    
                    with open(filepath, 'wb') as f:
                        f.write(excel_response.content)
                    
                    print(f"✅ Arquivo baixado: {filename}")
                    return filepath
            
            print("❌ Não foi possível encontrar o formulário ou link de download")
            return None
                
        except Exception as e:
            print(f"❌ Erro no download com requests: {e}")
            return None
    
    def read_stock_codes_from_excel(self, excel_file=None):
        """Lê códigos das ações da planilha a partir da célula A4"""
        if not excel_file:
            # Procura arquivo Excel existente (exclui nossos próprios outputs)
            excel_files = [f for f in glob.glob("*.xlsx") if not f.startswith("stocks_data_")]
            
            if not excel_files:
                print("📥 Fazendo download da planilha...")
                excel_file = self.download_stocks_excel()
                if not excel_file:
                    print("\\n💡 INSTRUÇÕES PARA DOWNLOAD MANUAL:")
                    print("1. Acesse: https://www.investsite.com.br/seleciona_acoes.php")
                    print("2. Clique no botão 'Procurar Ações'")
                    print("3. Aguarde a página carregar (15 segundos)")
                    print("4. Clique em 'Baixar Arquivo Excel'")
                    print("5. Salve o arquivo nesta pasta e execute novamente")
                    return []
            else:
                excel_file = max(excel_files, key=os.path.getctime)
                print(f"📁 Usando arquivo existente: {os.path.basename(excel_file)}")
        
        try:
            print(f"📖 Lendo códigos das ações de: {os.path.basename(excel_file)}")
            
            # Lê a planilha sem header para acessar células específicas
            df = pd.read_excel(excel_file, header=None)
            
            # Detecta o tipo de arquivo baseado no conteúdo da primeira linha
            first_cell = str(df.iloc[0, 0]).strip() if not df.empty else ""
            
            if first_cell.lower() == "código":
                # É nosso arquivo de output, lê a partir da A2
                print("📊 Detectado arquivo de output próprio, lendo códigos da coluna A...")
                start_row = 1  # A2 (índice 1)
            else:
                # É arquivo de input do InvestSite, lê a partir da A4
                print("📊 Detectado arquivo de input do InvestSite, lendo a partir de A4...")
                start_row = 3  # A4 (índice 3)
            
            # Pega valores da coluna A a partir da linha determinada
            stock_codes = []
            for i in range(start_row, len(df)):
                cell_value = df.iloc[i, 0]  # Coluna A
                
                if pd.isna(cell_value) or str(cell_value).strip() == '':
                    break  # Para quando encontra célula vazia
                
                code = str(cell_value).strip()
                if code and len(code) >= 4:  # Códigos de ação têm pelo menos 4 caracteres
                    stock_codes.append(code)
            
            print(f"✅ {len(stock_codes)} códigos de ações encontrados")
            
            # Mostra os primeiros códigos encontrados
            if stock_codes:
                print(f"📋 Primeiros códigos: {', '.join(stock_codes[:10])}")
                if len(stock_codes) > 10:
                    print(f"   ... e mais {len(stock_codes) - 10} códigos")
            
            return stock_codes
            
        except Exception as e:
            print(f"❌ Erro ao ler planilha: {e}")
            return []
    
    def setup_selenium_driver(self):
        """Configura o driver Selenium"""
        if not self.use_selenium:
            return None
            
        download_path = os.path.join(os.getcwd(), "downloads")
        os.makedirs(download_path, exist_ok=True)
        
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        
        # Configurações de download
        prefs = {
            "download.default_directory": download_path,
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        try:
            service = Service(ChromeDriverManager().install())
            driver = webdriver.Chrome(service=service, options=chrome_options)
            print("✅ Chrome driver configurado")
            return driver
        except Exception as e:
            print(f"❌ Erro ao configurar Selenium: {e}")
            print("🔄 Mudando para modo requests...")
            self.use_selenium = False
            return None
    
    def download_excel_file_selenium(self, driver):
        """Baixa arquivo Excel usando Selenium"""
        try:
            print("🌐 Acessando site InvestSite...")
            driver.get("https://www.investsite.com.br/seleciona_acoes.php")
            
            # Clica em "Procurar Ações"
            print("🔍 Clicando em 'Procurar Ações'...")
            search_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[@type='submit' and contains(text(), 'Procurar Ações')]"))
            )
            search_btn.click()
            
            time.sleep(5)
            
            # Clica no botão de download
            print("📥 Baixando arquivo Excel...")
            download_btn = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.ID, "botao_arquivo"))
            )
            download_btn.click()
            
            time.sleep(10)
            
            # Procura arquivo baixado
            download_path = os.path.join(os.getcwd(), "downloads")
            today = datetime.now().strftime("%Y%m%d")
            expected_file = os.path.join(download_path, f"Stock_Screener_{today}.xlsx")
            
            if os.path.exists(expected_file):
                print(f"✅ Arquivo baixado: Stock_Screener_{today}.xlsx")
                return expected_file
            else:
                # Procura arquivo mais recente
                excel_files = [f for f in os.listdir(download_path) 
                              if f.startswith("Stock_Screener_") and f.endswith(".xlsx")]
                if excel_files:
                    latest = max(excel_files, key=lambda x: os.path.getmtime(os.path.join(download_path, x)))
                    return os.path.join(download_path, latest)
                    
            return None
            
        except Exception as e:
            print(f"❌ Erro no download: {e}")
            return None
    
    def get_stock_codes(self):
        """Obtém códigos das ações diretamente da tabela do InvestSite"""
        
        print("🎯 FUNCIONALIDADE COMPLETA: Buscando TODAS as ações da tabela do InvestSite")
        print("📋 Método: Acessa página → Clica 'Procurar Ações' → Seleciona 'Todos' → Extrai TODOS os códigos")
        print("⚡ SEM LIMITAÇÕES: Processará todas as ações disponíveis")
        print("=" * 60)
        
        # Busca códigos diretamente da tabela
        stock_codes = self.get_stock_codes_from_table()
        
        if stock_codes:
            print(f"\n✅ {len(stock_codes)} códigos obtidos da tabela do InvestSite")
            return stock_codes
        
        # Fallback 1: Tenta método antigo (planilha)
        print("\n⚠️  Tentando método alternativo (planilha)...")
        stock_codes = self.read_stock_codes_from_excel()
        
        if stock_codes:
            print(f"✅ {len(stock_codes)} códigos obtidos da planilha")
            return stock_codes
        
        # Fallback 2: Usa códigos de exemplo se nada funcionar
        print("\n🎯 Usando códigos de exemplo para demonstração:")
        example_codes = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "WEGE3", "MGLU3", "TTEN3", "B3SA3", "RENT3"]
        print(f"📋 Códigos de exemplo: {', '.join(example_codes)}")
        return example_codes
    
    def scrape_stock_data(self, stock_code):
        """Faz scraping dos dados de uma ação - VERSÃO OTIMIZADA"""
        url = f"https://www.investsite.com.br/principais_indicadores.php?cod_negociacao={stock_code}"
        
        try:
            if self.use_selenium:
                # Implementação Selenium (simplificada para este exemplo)
                response = requests.get(url, timeout=8)
            else:
                response = self.session.get(url, timeout=8)
            
            response.raise_for_status()
            soup = BeautifulSoup(response.content, 'html.parser')
            
            stock_data = {"Código": stock_code}
            
            # 1. Tabela de dados básicos da empresa
            table_basic = soup.find('table', {'id': 'tabela_resumo_empresa'})
            if table_basic:
                rows = table_basic.find_all('tr')
                for row in rows:
                    cells = row.find_all('td')
                    if len(cells) == 2:
                        key = cells[0].text.strip()
                        value = BeautifulSoup(str(cells[1]), 'html.parser').get_text().strip()
                        stock_data[key] = value
            
            # 2. Tabela de preços relativos, market cap, EV e dividend yield
            table_prices = soup.find('table', {'id': 'tabela_resumo_empresa_precos_relativos'})
            if table_prices:
                tbody = table_prices.find('tbody', {'id': 'tabela_resumo_empresa_precos_relativos_tbody'})
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            key = cells[0].text.strip()
                            value_cell = cells[1]
                            
                            link = value_cell.find('a')
                            if link:
                                value_text = link.get_text().strip()
                                # Check if it's a currency with scale (B, M, mil, K) - preserve full text
                                import re
                                if re.search(r'[-\s]*R\$.*[BMK]|\bmil\b', value_text):
                                    value = value_text
                                else:
                                    # For other values, extract numbers preserving negative sign
                                    is_negative = value_text.strip().startswith('-')
                                    numbers = re.findall(r'[0-9]+[.,]?[0-9]*[%]?', value_text)
                                    if numbers:
                                        value = numbers[0]
                                        if is_negative:
                                            value = f"-{value}"
                                    else:
                                        value = value_text
                            else:
                                value = value_cell.get_text().strip()
                            
                            key_formatted = f"Indicador - {key}"
                            stock_data[key_formatted] = value
            
            # 3. Tabela de DRE - Últimos 12 Meses
            table_dre_12m = soup.find('table', {'id': 'tabela_resumo_empresa_dre_12meses'})
            if table_dre_12m:
                tbody = table_dre_12m.find('tbody', {'id': 'tabela_resumo_empresa_dre_12meses_tbody'})
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            key = cells[0].text.strip()
                            value_cell = cells[1]
                            
                            link = value_cell.find('a')
                            if link:
                                value_text = link.get_text().strip()
                                import re
                                # CORRIGIDO: Sempre preserva valores monetários (com ou sem escala)
                                if re.search(r'[-\s]*R\$', value_text):
                                    value = value_text  # Preserva todo o valor monetário incluindo sinal negativo
                                else:
                                    # For other values, extract numbers as before
                                    value_match = re.search(r'([-+]?[\d.,]+%?)', value_text)
                                    if value_match:
                                        value = value_match.group(1)
                                    else:
                                        value = value_text
                            else:
                                value = value_cell.get_text().strip()
                            
                            key_formatted = f"DRE 12M - {key}"
                            stock_data[key_formatted] = value
            
            # 4. Tabela de DRE - Último Trimestre (3 Meses)
            table_dre_3m = soup.find('table', {'id': 'tabela_resumo_empresa_dre_3meses'})
            if table_dre_3m:
                tbody = table_dre_3m.find('tbody', {'id': 'tabela_resumo_empresa_dre_3meses_tbody'})
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            key = cells[0].text.strip()
                            value_cell = cells[1]
                            
                            link = value_cell.find('a')
                            if link:
                                value_text = link.get_text().strip()
                                import re
                                # CORRIGIDO: Sempre preserva valores monetários (com ou sem escala)
                                if re.search(r'[-\s]*R\$', value_text):
                                    value = value_text  # Preserva todo o valor monetário incluindo sinal negativo
                                else:
                                    # For other values, extract numbers as before
                                    value_match = re.search(r'([-+]?[\d.,]+%?)', value_text)
                                    if value_match:
                                        value = value_match.group(1)
                                    else:
                                        value = value_text
                            else:
                                value = value_cell.get_text().strip()
                            
                            key_formatted = f"DRE 3M - {key}"
                            stock_data[key_formatted] = value
            
            # 5. Tabela de Comportamento de Preço e Volume da Ação
            table_precos = soup.find('table', {'id': 'tabela_resumo_empresa_precos'})
            if table_precos:
                tbody = table_precos.find('tbody')
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            key = cells[0].text.strip()
                            value = cells[1].get_text().strip()
                            key_formatted = f"Preço/Volume - {key}"
                            stock_data[key_formatted] = value
            
            # 6. Tabela de Retornos, Margens e Outras Medidas
            table_margens = soup.find('table', {'id': 'tabela_resumo_empresa_margens_retornos'})
            if table_margens:
                tbody = table_margens.find('tbody', {'id': 'tabela_resumo_empresa_margens_retornos_tbody'})
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            key = cells[0].text.strip()
                            value_cell = cells[1]
                            
                            link = value_cell.find('a')
                            if link:
                                value_text = link.get_text().strip()
                                import re
                                value_match = re.search(r'([-+]?[\d.,]+%?)', value_text)
                                if value_match:
                                    value = value_match.group(1)
                                else:
                                    value = value_text
                            else:
                                value = value_cell.get_text().strip()
                            
                            key_formatted = f"Retorno/Margem - {key}"
                            stock_data[key_formatted] = value
            
            # 7. Tabela de Resumo Balanço Patrimonial
            table_bp = soup.find('table', {'id': 'tabela_resumo_empresa_bp'})
            if table_bp:
                tbody = table_bp.find('tbody', {'id': 'tabela_resumo_empresa_bp_tbody'})
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            key = cells[0].text.strip()
                            value_cell = cells[1]
                            
                            link = value_cell.find('a')
                            if link:
                                value_text = link.get_text().strip()
                                import re
                                # Check if it's a currency with scale (B, M, mil, K) - preserve full text
                                if re.search(r'[-\s]*R\$.*[BMK]|\bmil\b', value_text):
                                    value = value_text
                                else:
                                    # For other values, extract numbers as before
                                    value_match = re.search(r'([-+]?[\d.,]+%?)', value_text)
                                    if value_match:
                                        value = value_match.group(1)
                                    else:
                                        value = value_text
                            else:
                                value = value_cell.get_text().strip()
                            
                            key_formatted = f"Balanço - {key}"
                            stock_data[key_formatted] = value
            
            # 8. Tabela de Resumo Fluxo de Caixa Últimos Doze Meses
            table_fc_12m = soup.find('table', {'id': 'tabela_resumo_empresa_fc_12meses'})
            if table_fc_12m:
                tbody = table_fc_12m.find('tbody', {'id': 'tabela_resumo_empresa_fc_12meses_tbody'})
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            key = cells[0].text.strip()
                            value_cell = cells[1]
                            
                            link = value_cell.find('a')
                            if link:
                                value_text = link.get_text().strip()
                                import re
                                value_match = re.search(r'([-+]?\s*R\$\s*[\d.,]+\s*[BMK]?)', value_text)
                                if value_match:
                                    value = value_match.group(1)
                                else:
                                    value = value_text
                            else:
                                value = value_cell.get_text().strip()
                            
                            key_formatted = f"FC 12M - {key}"
                            stock_data[key_formatted] = value
            
            # 9. Tabela de Resumo Fluxo de Caixa Último Trimestre
            table_fc_3m = soup.find('table', {'id': 'tabela_resumo_empresa_fc_3meses'})
            if table_fc_3m:
                tbody = table_fc_3m.find('tbody', {'id': 'tabela_resumo_empresa_fc_3meses_tbody'})
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            key = cells[0].text.strip()
                            value_cell = cells[1]
                            
                            link = value_cell.find('a')
                            if link:
                                value_text = link.get_text().strip()
                                import re
                                value_match = re.search(r'([-+]?\s*R\$\s*[\d.,]+\s*[BMK]?)', value_text)
                                if value_match:
                                    value = value_match.group(1)
                                else:
                                    value = value_text
                            else:
                                value = value_cell.get_text().strip()
                            
                            key_formatted = f"FC 3M - {key}"
                            stock_data[key_formatted] = value
            
            # 10. Tabela de Cálculo Experimental de CAPEX e Fluxo de Caixa Livre
            table_experimental = soup.find('table', {'id': 'tabela_resumo_empresa_experimental'})
            if table_experimental:
                tbody = table_experimental.find('tbody', {'id': 'tabela_resumo_empresa_experimental_tbody'})
                if tbody:
                    rows = tbody.find_all('tr')
                    for row in rows:
                        cells = row.find_all('td')
                        if len(cells) == 2:
                            key = cells[0].text.strip()
                            value_cell = cells[1]
                            
                            link = value_cell.find('a')
                            if link:
                                value_text = link.get_text().strip()
                                import re
                                value_match = re.search(r'([-+]?\s*R\$\s*[\d.,]+\s*[BMK]?)', value_text)
                                if value_match:
                                    value = value_match.group(1)
                                else:
                                    value = value_text
                            else:
                                value = value_cell.get_text().strip()
                            
                            key_formatted = f"CAPEX/FCL - {key}"
                            stock_data[key_formatted] = value
            
            # 🆕 NOVO: Calcular Earnings Yield
            earnings_yield = self.calculate_earnings_yield(stock_data)
            if earnings_yield:
                stock_data["Earnings Yield (%)"] = earnings_yield
            
            # 🆕 NOVO: Limpeza automática dos dados
            cleaned_data = self.clean_stock_data(stock_data)
            
            # Verifica se conseguiu extrair dados
            if len(cleaned_data) <= 1:  # Apenas o código
                return {"Código": stock_code, "Status": "Nenhuma tabela encontrada"}
            
            return cleaned_data
            
        except Exception as e:
            return {"Código": stock_code, "Erro": str(e)}
    
    def calculate_earnings_yield(self, stock_data):
        """
        Calcula o Earnings Yield = (Lucro/Ação ÷ Último Preço) × 100
        """
        try:
            # Busca o lucro por ação
            lucro_por_acao = None
            for key in stock_data.keys():
                if "Lucro/Ação" in key or "lucro por ação" in key.lower():
                    lucro_str = stock_data[key]
                    # Usar a função de limpeza do DataCleaner para conversão correta
                    try:
                        lucro_por_acao = DataCleaner.clean_currency_to_float(lucro_str)
                        break
                    except:
                        continue
            
            # Busca o último preço de fechamento
            ultimo_preco = None
            preco_key = stock_data.get('Último Preço de Fechamento', '')
            if preco_key:
                # Usar a função de limpeza do DataCleaner para conversão correta
                try:
                    ultimo_preco = DataCleaner.clean_currency_to_float(preco_key)
                except:
                    ultimo_preco = None
            
            # Calcula o Earnings Yield se ambos os valores existem
            if lucro_por_acao is not None and ultimo_preco is not None and ultimo_preco > 0:
                earnings_yield = (lucro_por_acao / ultimo_preco) * 100
                return f"{earnings_yield:.2f}%"
            
            return "N/A"
            
        except Exception as e:
            print(f"⚠️  Erro ao calcular Earnings Yield para {stock_data.get('Código', 'N/A')}: {e}")
            return "N/A"
    
    def clean_stock_data(self, stock_data):
        """
        Aplica limpeza automática em todos os campos especificados
        """
        cleaned_data = stock_data.copy()
        
        # Dicionário de campos e suas funções de limpeza
        cleaning_rules = {
            # Preços básicos
            "Último Preço de Fechamento": DataCleaner.clean_currency_to_float,
            "Volume Financeiro Transacionado": DataCleaner.clean_currency_with_scale_to_float,
            
            # Indicadores de múltiplos
            "Indicador - Preço/Lucro": DataCleaner.clean_ratio_to_float,
            "Indicador - Preço/VPA": DataCleaner.clean_ratio_to_float,
            "Indicador - Preço/Receita Líquida": DataCleaner.clean_ratio_to_float,
            "Indicador - Preço/FCO": DataCleaner.clean_ratio_to_float,
            "Indicador - Preço/FCF": DataCleaner.clean_ratio_to_float,
            "Indicador - Preço/Ativo Total": DataCleaner.clean_ratio_to_float,
            "Indicador - Preço/EBIT": DataCleaner.clean_ratio_to_float,
            "Indicador - Preço/Capital Giro": DataCleaner.clean_ratio_to_float,
            "Indicador - Preço/NCAV": DataCleaner.clean_ratio_to_float,
            "Indicador - EV/EBIT": DataCleaner.clean_ratio_to_float,
            "Indicador - EV/EBITDA": DataCleaner.clean_ratio_to_float,
            "Indicador - EV/Receita Líquida": DataCleaner.clean_ratio_to_float,
            "Indicador - EV/FCO": DataCleaner.clean_ratio_to_float,
            "Indicador - EV/FCF": DataCleaner.clean_ratio_to_float,
            "Indicador - EV/Ativo Total": DataCleaner.clean_ratio_to_float,
            
            # Market Cap e Enterprise Value
            "Indicador - Market Cap Empresa": DataCleaner.clean_currency_with_scale_to_float,
            "Indicador - Enterprise Value": DataCleaner.clean_currency_with_scale_to_float,
            
            # Datas
            "Indicador - Data Demonstração Financeira Atual": DataCleaner.clean_date_to_format,
            "Indicador - Data do Preço da Ação": DataCleaner.clean_date_to_format,
            
            # Preços e yields
            "Indicador - Preço Atual da Ação": DataCleaner.clean_currency_to_float,
            "Indicador - Dividend Yield": DataCleaner.clean_percentage_to_float,
            
            # DRE 12M
            "DRE 12M - Receita Líquida": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 12M - Resultado Bruto": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 12M - EBIT": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 12M - Depreciação e Amortização": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 12M - EBITDA": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 12M - Lucro Líquido": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 12M - Lucro/Ação": DataCleaner.clean_currency_with_scale_to_float,  # CORRIGIDO: agora usa função com escala
            
            # DRE 3M
            "DRE 3M - Receita Líquida": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 3M - Resultado Bruto": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 3M - EBIT": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 3M - Depreciação e Amortização": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 3M - EBITDA": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 3M - Lucro Líquido": DataCleaner.clean_currency_with_scale_to_float,
            "DRE 3M - Lucro/Ação": DataCleaner.clean_currency_with_scale_to_float,  # CORRIGIDO: agora usa função com escala
            
            # Retornos e Margens - Percentuais
            "Retorno/Margem - Retorno s/ Capital Tangível Inicial": DataCleaner.clean_percentage_to_float,
            "Retorno/Margem - Retorno s/ Capital Investido Inicial": DataCleaner.clean_percentage_to_float,
            "Retorno/Margem - Retorno s/ Capital Tangível Inicial Pré-Impostos": DataCleaner.clean_percentage_to_float,
            "Retorno/Margem - Retorno s/ Capital Investido Inicial Pré-Impostos": DataCleaner.clean_percentage_to_float,
            "Retorno/Margem - Retorno s/ Patrimônio Líquido Inicial": DataCleaner.clean_percentage_to_float,
            "Retorno/Margem - Retorno s/ Ativo Inicial": DataCleaner.clean_percentage_to_float,
            "Retorno/Margem - Margem Bruta": DataCleaner.clean_percentage_to_float,
            "Retorno/Margem - Margem Líquida": DataCleaner.clean_percentage_to_float,
            "Retorno/Margem - Margem EBIT": DataCleaner.clean_percentage_to_float,
            "Retorno/Margem - Margem EBITDA": DataCleaner.clean_percentage_to_float,
            
            # Retornos e Margens - Ratios
            "Retorno/Margem - Giro do Ativo Inicial": DataCleaner.clean_ratio_to_float,
            "Retorno/Margem - Alavancagem Financeira": DataCleaner.clean_ratio_to_float,
            "Retorno/Margem - Passivo/Patrimônio Líquido": DataCleaner.clean_ratio_to_float,
            "Retorno/Margem - Dívida Líquida/EBITDA": DataCleaner.clean_ratio_to_float,
            
            # Balanço - Valores financeiros
            "Balanço - Caixa e Equivalentes de Caixa": DataCleaner.clean_currency_with_scale_to_float,
            "Balanço - Ativo Total": DataCleaner.clean_currency_with_scale_to_float,
            "Balanço - Dívida de Curto Prazo": DataCleaner.clean_currency_with_scale_to_float,
            "Balanço - Dívida de Longo Prazo": DataCleaner.clean_currency_with_scale_to_float,
            "Balanço - Dívida Bruta": DataCleaner.clean_currency_with_scale_to_float,
            "Balanço - Dívida Líquida": DataCleaner.clean_currency_with_scale_to_float,
            "Balanço - Patrimônio Líquido": DataCleaner.clean_currency_with_scale_to_float,
            "Balanço - Valor Patrimonial da Ação": DataCleaner.clean_currency_with_scale_to_float,
            
            # Balanço - Ações (inteiros)
            "Balanço - Ações Ordinárias": DataCleaner.clean_integer,
            "Balanço - Ações Preferenciais": DataCleaner.clean_integer,
            "Balanço - Total": DataCleaner.clean_integer,
            "Balanço - Ações Ordinárias em Tesouraria": DataCleaner.clean_integer,
            "Balanço - Ações Preferenciais em Tesouraria": DataCleaner.clean_integer,
            "Balanço - Total em Tesouraria": DataCleaner.clean_integer,
            "Balanço - Ações Ordinárias (Exceto Tesouraria)": DataCleaner.clean_integer,
            "Balanço - Ações Preferenciais (Exceto Tesouraria)": DataCleaner.clean_integer,
            "Balanço - Total (Exceto Tesouraria)": DataCleaner.clean_integer,
            
            # Fluxo de Caixa 12M
            "FC 12M - Fluxo de Caixa Operacional": DataCleaner.clean_currency_with_scale_to_float,
            "FC 12M - Fluxo de Caixa de Investimentos": DataCleaner.clean_currency_with_scale_to_float,
            "FC 12M - Fluxo de Caixa de Financiamentos": DataCleaner.clean_currency_with_scale_to_float,
            "FC 12M - Aumento (Redução) de Caixa e Equivalentes": DataCleaner.clean_currency_with_scale_to_float,
            
            # Fluxo de Caixa 3M
            "FC 3M - Fluxo de Caixa Operacional": DataCleaner.clean_currency_with_scale_to_float,
            "FC 3M - Fluxo de Caixa de Investimentos": DataCleaner.clean_currency_with_scale_to_float,
            "FC 3M - Fluxo de Caixa de Financiamentos": DataCleaner.clean_currency_with_scale_to_float,
            "FC 3M - Aumento (Redução) de Caixa e Equivalentes": DataCleaner.clean_currency_with_scale_to_float,
            
            # CAPEX e FCL
            "CAPEX/FCL - CAPEX 3 meses": DataCleaner.clean_currency_with_scale_to_float,
            "CAPEX/FCL - Fluxo de Caixa Livre 3 meses": DataCleaner.clean_currency_with_scale_to_float,
            "CAPEX/FCL - CAPEX 12 meses": DataCleaner.clean_currency_with_scale_to_float,
            "CAPEX/FCL - Fluxo de Caixa Livre 12 meses": DataCleaner.clean_currency_with_scale_to_float,
            
            # Earnings Yield
            "Earnings Yield (%)": DataCleaner.clean_percentage_to_float,
            
            # Preço/Volume
            "Preço/Volume - Menor Preço 52 semanas": DataCleaner.clean_currency_to_float,
            "Preço/Volume - Maior Preço 52 semanas": DataCleaner.clean_currency_to_float,
            "Preço/Volume - Variação 2025": DataCleaner.clean_percentage_to_float,
            "Preço/Volume - Variação 1 ano": DataCleaner.clean_percentage_to_float,
            "Preço/Volume - Variação 2 anos(total)": DataCleaner.clean_percentage_to_float,
            "Preço/Volume - Variação 2 anos(anual)": DataCleaner.clean_percentage_to_float,
            "Preço/Volume - Variação 3 anos(total)": DataCleaner.clean_percentage_to_float,
            "Preço/Volume - Variação 3 anos(anual)": DataCleaner.clean_percentage_to_float,
            "Preço/Volume - Variação 4 anos(total)": DataCleaner.clean_percentage_to_float,
            "Preço/Volume - Variação 4 anos(anual)": DataCleaner.clean_percentage_to_float,
            "Preço/Volume - Variação 5 anos(total)": DataCleaner.clean_percentage_to_float,
            "Preço/Volume - Variação 5 anos(anual)": DataCleaner.clean_percentage_to_float,
            "Preço/Volume - Volume Diário Médio (3 meses)": DataCleaner.clean_currency_with_scale_to_float,
        }
        
        # Aplica limpeza para cada campo
        for field_name, cleaning_function in cleaning_rules.items():
            if field_name in cleaned_data and cleaned_data[field_name]:
                try:
                    original_value = cleaned_data[field_name]
                    cleaned_value = cleaning_function(original_value)
                    
                    # Só substitui se a limpeza foi bem-sucedida
                    if cleaned_value is not None:
                        cleaned_data[field_name] = cleaned_value
                        
                except Exception as e:
                    print(f"⚠️  Erro ao limpar campo '{field_name}': {e}")
                    # Mantém valor original em caso de erro
                    pass
        
        return cleaned_data
    
    def scrape_all_stocks(self, stock_codes):
        """Faz scraping de todas as ações - VERSÃO PARALELA OTIMIZADA"""
        print(f"\n🔄 Iniciando scraping OTIMIZADO de {len(stock_codes)} ações...")
        print(f"⚡ Usando {self.max_workers} threads paralelas em lotes de {self.batch_size}")
        
        total_processed = 0
        start_time = time.time()
        
        # Processa em lotes para não sobrecarregar o servidor
        for batch_start in range(0, len(stock_codes), self.batch_size):
            batch_end = min(batch_start + self.batch_size, len(stock_codes))
            batch = stock_codes[batch_start:batch_end]
            
            print(f"\n📦 Processando lote {batch_start//self.batch_size + 1} "
                  f"(ações {batch_start+1}-{batch_end} de {len(stock_codes)})")
            
            # Processamento paralelo do lote atual
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Submete todas as tarefas do lote
                future_to_code = {
                    executor.submit(self.scrape_stock_data, code): code 
                    for code in batch
                }
                
                # Coleta resultados conforme completam
                batch_results = []
                for future in as_completed(future_to_code):
                    code = future_to_code[future]
                    total_processed += 1
                    
                    try:
                        result = future.result()
                        batch_results.append(result)
                        
                        # Indica progresso
                        if "Erro" in result:
                            status = "❌"
                        else:
                            status = "✅"
                        
                        # Calcula velocidade
                        elapsed = time.time() - start_time
                        speed = total_processed / elapsed if elapsed > 0 else 0
                        
                        print(f"  📈 [{total_processed}/{len(stock_codes)}] {code} {status} "
                              f"({speed:.1f} ações/min)")
                        
                    except Exception as e:
                        batch_results.append({"Código": code, "Erro": str(e)})
                        print(f"  📈 [{total_processed}/{len(stock_codes)}] {code} ❌ (Exceção)")
                
                # Adiciona resultados do lote de forma thread-safe
                with self.data_lock:
                    self.stocks_data.extend(batch_results)
            
            # Pausa entre lotes para ser respeitoso com o servidor
            if batch_end < len(stock_codes):
                print(f"⏳ Pausa de 2 segundos entre lotes...")
                time.sleep(2)
        
        # Estatísticas finais
        elapsed = time.time() - start_time
        avg_speed = len(stock_codes) / elapsed if elapsed > 0 else 0
        
        print(f"\n🎉 Scraping concluído!")
        print(f"   📊 {len(self.stocks_data)} ações processadas")
        print(f"   ⏱️ Tempo total: {elapsed:.1f} segundos")
        print(f"   ⚡ Velocidade média: {avg_speed:.1f} ações/min")
        print(f"   🚀 Otimização: ~{(1.5 * len(stock_codes)) / elapsed:.1f}x mais rápido!")
    
    def scrape_all_stocks_legacy(self, stock_codes):
        """Versão sequencial original (para comparação)"""
        print(f"\n🔄 Iniciando scraping sequencial de {len(stock_codes)} ações...")
        
        for i, code in enumerate(stock_codes, 1):
            print(f"📈 [{i}/{len(stock_codes)}] {code}", end=" ")
            
            stock_data = self.scrape_stock_data(code)
            self.stocks_data.append(stock_data)
            
            # Indica sucesso ou erro
            if "Erro" in stock_data:
                print("❌")
            else:
                print("✅")
            
            time.sleep(1.5)  # Pausa entre requisições
        
        print(f"\n🎉 Scraping concluído! {len(self.stocks_data)} ações processadas")
    
    def save_results(self):
        """Salva os resultados apenas em Excel com formatação adequada"""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        df = pd.DataFrame(self.stocks_data)
        
        # Arquivo de saída - apenas Excel
        excel_file = f"stocks_data_{timestamp}.xlsx"
        
        try:
            # Salva em Excel com writer para controle de formatação
            with pd.ExcelWriter(excel_file, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Stocks')
                
                # Obtém a worksheet para aplicar formatação
                worksheet = writer.sheets['Stocks']
                
                # Define formato numérico para campos monetários grandes
                from openpyxl.styles import NamedStyle
                
                # Formato para números grandes (sem notação científica)
                number_format = NamedStyle(name='big_numbers')
                number_format.number_format = '0.00'
                
                # Campos que devem ter formato numérico específico
                financial_fields = [
                    'Indicador - Market Cap Empresa',
                    'Indicador - Enterprise Value',
                    'DRE 12M - Receita Líquida',
                    'DRE 12M - EBITDA',
                    'DRE 12M - Lucro Líquido'
                ]
                
                # Aplica formatação às colunas relevantes
                for col_idx, col_name in enumerate(df.columns, 1):
                    if any(field in col_name for field in financial_fields):
                        for row_idx in range(2, len(df) + 2):  # Skip header
                            cell = worksheet.cell(row=row_idx, column=col_idx)
                            if isinstance(cell.value, (int, float)):
                                cell.number_format = '0.00'
            
            print(f"\n💾 Dados salvos em:")
            print(f"   📄 EXCEL: {excel_file}")
            
            return excel_file
            
        except Exception as e:
            print(f"❌ Erro ao salvar: {e}")
            # Fallback para salvamento simples
            try:
                df.to_excel(excel_file, index=False)
                print(f"   📄 EXCEL (formato simples): {excel_file}")
                return excel_file
            except:
                return None
    
    def show_summary(self):
        """Mostra resumo dos dados coletados"""
        if not self.stocks_data:
            return
        
        print(f"\n📊 RESUMO DOS DADOS COLETADOS")
        print("=" * 50)
        
        # Estatísticas gerais
        total_stocks = len(self.stocks_data)
        successful = len([s for s in self.stocks_data if "Erro" not in s])
        errors = total_stocks - successful
        
        print(f"Total de ações: {total_stocks}")
        print(f"Sucessos: {successful}")
        print(f"Erros: {errors}")
        
        # Preview dos dados
        if successful > 0:
            print(f"\n📋 Preview das primeiras 3 ações:")
            for i, stock in enumerate([s for s in self.stocks_data if "Erro" not in s][:3], 1):
                print(f"\n{i}. {stock.get('Código', 'N/A')}")
                empresa = stock.get('Empresa', 'N/A')
                preco = stock.get('Último Preço de Fechamento', 'N/A')
                setor = stock.get('Setor', 'N/A')
                
                # Indicadores financeiros
                preco_lucro = stock.get('Indicador - Preço/Lucro', 'N/A')
                preco_vpa = stock.get('Indicador - Preço/VPA', 'N/A')
                dividend_yield = stock.get('Indicador - Dividend Yield', 'N/A')
                earnings_yield = stock.get('Earnings Yield (%)', 'N/A')  # NOVO CAMPO
                
                # Dados de DRE
                receita_12m = stock.get('DRE 12M - Receita Líquida', 'N/A')
                ebitda_12m = stock.get('DRE 12M - EBITDA', 'N/A')
                lucro_12m = stock.get('DRE 12M - Lucro Líquido', 'N/A')
                
                print(f"   Empresa: {empresa}")
                print(f"   Preço: {preco}")
                print(f"   Setor: {setor}")
                print(f"   P/L: {preco_lucro}")
                print(f"   P/VPA: {preco_vpa}")
                print(f"   Dividend Yield: {dividend_yield}")
                print(f"   🆕 Earnings Yield: {earnings_yield}")  # NOVO CAMPO
                print(f"   Receita 12M: {receita_12m}")
                print(f"   EBITDA 12M: {ebitda_12m}")
                print(f"   Lucro 12M: {lucro_12m}")
                print(f"   🧹 Dados automaticamente limpos e formatados!")
        
        # Mostra campos coletados
        if self.stocks_data:
            sample_stock = next((s for s in self.stocks_data if "Erro" not in s), None)
            if sample_stock:
                basic_fields = [k for k in sample_stock.keys() if not k.startswith(('Indicador -', 'DRE ', 'Preço/Volume -', 'Retorno/Margem -', 'Balanço -', 'FC ', 'CAPEX/FCL -'))]
                indicator_fields = [k for k in sample_stock.keys() if k.startswith('Indicador -')]
                dre_12m_fields = [k for k in sample_stock.keys() if k.startswith('DRE 12M -')]
                dre_3m_fields = [k for k in sample_stock.keys() if k.startswith('DRE 3M -')]
                price_volume_fields = [k for k in sample_stock.keys() if k.startswith('Preço/Volume -')]
                margin_return_fields = [k for k in sample_stock.keys() if k.startswith('Retorno/Margem -')]
                balance_fields = [k for k in sample_stock.keys() if k.startswith('Balanço -')]
                fc_12m_fields = [k for k in sample_stock.keys() if k.startswith('FC 12M -')]
                fc_3m_fields = [k for k in sample_stock.keys() if k.startswith('FC 3M -')]
                capex_fields = [k for k in sample_stock.keys() if k.startswith('CAPEX/FCL -')]
                
                print(f"\n📈 Campos coletados por ação:")
                print(f"   • Dados básicos: {len(basic_fields)} campos")
                print(f"   • Indicadores financeiros: {len(indicator_fields)} campos")
                print(f"   • DRE 12 meses: {len(dre_12m_fields)} campos")
                print(f"   • DRE 3 meses: {len(dre_3m_fields)} campos")
                print(f"   • Comportamento preço/volume: {len(price_volume_fields)} campos")
                print(f"   • Retornos e margens: {len(margin_return_fields)} campos")
                print(f"   • Balanço patrimonial: {len(balance_fields)} campos")
                print(f"   • Fluxo de caixa 12M: {len(fc_12m_fields)} campos")
                print(f"   • Fluxo de caixa 3M: {len(fc_3m_fields)} campos")
                print(f"   • CAPEX e FCL: {len(capex_fields)} campos")
                print(f"   • Total: {len(sample_stock)} campos")
                
                print(f"\n💰 Indicadores DRE 12M coletados:")
                for field in dre_12m_fields:
                    field_name = field.replace('DRE 12M - ', '')
                    print(f"   • {field_name}")
                
                print(f"\n📊 Indicadores DRE 3M coletados:")
                for field in dre_3m_fields:
                    field_name = field.replace('DRE 3M - ', '')
                    print(f"   • {field_name}")
                
                if price_volume_fields:
                    print(f"\n📈 Dados de preço/volume coletados:")
                    for field in price_volume_fields[:5]:  # Mostra só os primeiros 5
                        field_name = field.replace('Preço/Volume - ', '')
                        print(f"   • {field_name}")
                
                if balance_fields:
                    print(f"\n🏛️ Dados de balanço patrimonial coletados:")
                    for field in balance_fields[:5]:  # Mostra só os primeiros 5
                        field_name = field.replace('Balanço - ', '')
                        print(f"   • {field_name}")
    
    def run(self):
        """Executa o processo completo"""
        print("🤖 SISTEMA DE SCRAPING DE AÇÕES - INVESTSITE")
        print("=" * 50)
        
        try:
            # 1. Obter códigos das ações
            stock_codes = self.get_stock_codes()
            
            if not stock_codes:
                print("❌ Nenhum código de ação encontrado")
                return
            
            # 2. Fazer scraping
            self.scrape_all_stocks(stock_codes)
            
            # 3. Salvar resultados
            files = self.save_results()
            
            # 4. Mostrar resumo
            self.show_summary()
            
            print(f"\n✅ PROCESSO CONCLUÍDO COM SUCESSO!")
            
        except KeyboardInterrupt:
            print("\n⏹️  Processo interrompido pelo usuário")
        except Exception as e:
            print(f"\n❌ Erro durante execução: {e}")

def main():
    """Função principal com opções de otimização"""
    
    print("🚀 SISTEMA OTIMIZADO DE SCRAPING DE AÇÕES - INVESTSITE")
    print("=" * 60)
    print()
    
    print("Escolha o modo de operação:")
    print("1. 🚀 OTIMIZADO (Paralelo com 5 threads)")
    print("2. ⚡ SUPER OTIMIZADO (Paralelo com 8 threads)")
    print("3. 🐌 SEQUENCIAL (Original, mais lento)")
    print("4. 🔧 PERSONALIZADO")
    
    try:
        choice = input("\nDigite sua escolha (1, 2, 3 ou 4): ").strip()
        
        if choice == "1":
            max_workers = 5
            batch_size = 20
            use_selenium = False
        elif choice == "2":
            max_workers = 8
            batch_size = 30
            use_selenium = False
        elif choice == "3":
            max_workers = 1
            batch_size = 1
            use_selenium = False
        elif choice == "4":
            print("\n🔧 CONFIGURAÇÃO PERSONALIZADA:")
            try:
                max_workers = int(input("Número de threads paralelas (1-10): ").strip())
                max_workers = max(1, min(10, max_workers))
                
                batch_size = int(input("Tamanho do lote (5-50): ").strip())
                batch_size = max(5, min(50, batch_size))
                
                selenium_choice = input("Usar Selenium? (s/n): ").strip().lower()
                use_selenium = selenium_choice == 's'
            except:
                print("⚠️  Configuração inválida, usando padrão otimizado")
                max_workers = 5
                batch_size = 20
                use_selenium = False
        else:
            print("⚠️  Escolha inválida, usando modo otimizado padrão")
            max_workers = 5
            batch_size = 20
            use_selenium = False
        
        print(f"\n✅ Configuração selecionada:")
        print(f"   🔧 Threads: {max_workers}")
        print(f"   📦 Lote: {batch_size} ações")
        print(f"   🌐 Selenium: {'Sim' if use_selenium else 'Não (mais rápido)'}")
        print()
        
    except:
        max_workers = 5
        batch_size = 20
        use_selenium = False
    
    scraper = StocksScraper(
        use_selenium=use_selenium, 
        max_workers=max_workers, 
        batch_size=batch_size
    )
    scraper.run()

if __name__ == "__main__":
    main()