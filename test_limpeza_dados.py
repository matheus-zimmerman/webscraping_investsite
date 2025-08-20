"""
Teste do sistema de limpeza automática de dados
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from stocks import StocksScraper, DataCleaner

def test_data_cleaning():
    """Testa as funções de limpeza de dados"""
    print("🧪 TESTE DO SISTEMA DE LIMPEZA DE DADOS")
    print("=" * 50)
    
    # Dados de exemplo sujos
    test_data = {
        "Código": "TEST4",
        "Último Preço de Fechamento": "R$ 25,50",
        "Volume Financeiro Transacionado": "R$ 150,30 M",
        "Indicador - Preço/Lucro": "8,50",
        "Indicador - Dividend Yield": "15,30%",
        "DRE 12M - Receita Líquida": "R$ 2,5 B",
        "DRE 12M - EBITDA": "R$ 450,20 M",
        "Balanço - Ações Ordinárias": "1.250.000.000",
        "Retorno/Margem - Margem Líquida": "-5,25%",
        "Preço/Volume - Variação 1 ano": "+25,75%",
        "Earnings Yield (%)": "12,15%"
    }
    
    print("📋 DADOS ORIGINAIS (SUJOS):")
    print("-" * 30)
    for key, value in test_data.items():
        print(f"   {key}: '{value}'")
    
    # Aplicar limpeza
    scraper = StocksScraper(max_workers=1, batch_size=1)
    cleaned_data = scraper.clean_stock_data(test_data)
    
    print("\n🧹 DADOS APÓS LIMPEZA:")
    print("-" * 30)
    for key, value in cleaned_data.items():
        original = test_data.get(key, 'N/A')
        if original != str(value):
            print(f"   {key}: {value} (era: '{original}')")
        else:
            print(f"   {key}: {value}")
    
    print("\n✅ VERIFICAÇÃO DOS TIPOS:")
    print("-" * 30)
    for key, value in cleaned_data.items():
        if key != "Código":
            print(f"   {key}: {type(value).__name__} = {value}")

def test_individual_cleaners():
    """Testa funções individuais de limpeza"""
    print("\n" + "="*50)
    print("🔧 TESTE DAS FUNÇÕES INDIVIDUAIS")
    print("="*50)
    
    tests = [
        ("Moeda simples", DataCleaner.clean_currency_to_float, "R$ 25,50", 25.50),
        ("Moeda com escala M", DataCleaner.clean_currency_with_scale_to_float, "R$ 150,30 M", 150300000.00),
        ("Moeda com escala B", DataCleaner.clean_currency_with_scale_to_float, "R$ 2,5 B", 2500000000.00),
        ("Percentual positivo", DataCleaner.clean_percentage_to_float, "15,30%", 15.30),
        ("Percentual negativo", DataCleaner.clean_percentage_to_float, "-5,25%", -5.25),
        ("Ratio/Múltiplo", DataCleaner.clean_ratio_to_float, "8,50", 8.50),
        ("Número inteiro", DataCleaner.clean_integer, "1.250.000.000", 1250000000),
    ]
    
    for test_name, func, input_val, expected in tests:
        result = func(input_val)
        status = "✅" if result == expected else "❌"
        print(f"{status} {test_name}: '{input_val}' -> {result} (esperado: {expected})")

def test_real_scraping_with_cleaning():
    """Teste com scraping real de uma ação"""
    print("\n" + "="*50)
    print("🌐 TESTE COM SCRAPING REAL (LIMPEZA AUTOMÁTICA)")
    print("="*50)
    
    scraper = StocksScraper(use_selenium=False, max_workers=1, batch_size=1)
    
    # Testa com uma ação conhecida
    test_code = "PETR4"
    print(f"🔍 Testando scraping de {test_code} com limpeza automática...")
    
    result = scraper.scrape_stock_data(test_code)
    
    if "Erro" in result:
        print(f"❌ Erro: {result['Erro']}")
        return
    
    print(f"✅ {test_code}: {len(result)} campos extraídos e limpos")
    
    # Mostra alguns campos importantes limpos
    important_fields = [
        "Último Preço de Fechamento",
        "Indicador - Preço/Lucro", 
        "Indicador - Dividend Yield",
        "DRE 12M - Receita Líquida",
        "Earnings Yield (%)",
        "Balanço - Ações Ordinárias"
    ]
    
    print(f"\n📊 AMOSTRA DE CAMPOS LIMPOS:")
    print("-" * 30)
    for field in important_fields:
        if field in result:
            value = result[field]
            type_name = type(value).__name__
            print(f"   {field}: {value} ({type_name})")

if __name__ == "__main__":
    # Teste 1: Limpeza de dados fictícios
    test_data_cleaning()
    
    # Teste 2: Funções individuais
    test_individual_cleaners()
    
    # Teste 3: Scraping real com limpeza
    test_real_scraping_with_cleaning()
    
    print("\n🎉 Todos os testes concluídos!")
