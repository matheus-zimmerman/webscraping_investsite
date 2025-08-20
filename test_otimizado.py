"""
Teste rápido do sistema otimizado
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from stocks import StocksScraper

def test_earnings_yield():
    """Testa o cálculo do earnings yield"""
    scraper = StocksScraper(max_workers=2, batch_size=5)
    
    # Dados de teste
    test_data = {
        "Código": "TEST4",
        "Último Preço de Fechamento": "R$ 25,50",
        "DRE 12M - Lucro/Ação": "2,50"
    }
    
    earnings_yield = scraper.calculate_earnings_yield(test_data)
    print(f"🧪 Teste Earnings Yield:")
    print(f"   Preço: {test_data['Último Preço de Fechamento']}")
    print(f"   Lucro/Ação: {test_data['DRE 12M - Lucro/Ação']}")
    print(f"   Earnings Yield: {earnings_yield}")
    print(f"   Expected: ~9.80% (2.50/25.50 * 100)")

def test_small_scraping():
    """Teste com poucas ações"""
    print("🧪 Teste de scraping com AÇÕES DE EXEMPLO...")
    
    scraper = StocksScraper(use_selenium=False, max_workers=2, batch_size=2)
    
    # Códigos de teste
    test_codes = ["PETR4", "VALE3"]  # Ações conhecidas
    
    print(f"Testando com: {test_codes}")
    
    # Testa scraping de uma ação
    for code in test_codes:
        print(f"\n🔍 Testando {code}...")
        result = scraper.scrape_stock_data(code)
        
        if "Erro" in result:
            print(f"❌ {code}: {result.get('Erro', 'Erro desconhecido')}")
        else:
            print(f"✅ {code}: {len(result)} campos extraídos")
            if "Earnings Yield (%)" in result:
                print(f"   🆕 Earnings Yield: {result['Earnings Yield (%)']}")
            else:
                print(f"   ⚠️  Earnings Yield não calculado")

if __name__ == "__main__":
    print("🧪 TESTE DO SISTEMA OTIMIZADO")
    print("=" * 40)
    
    # Teste 1: Cálculo do earnings yield
    test_earnings_yield()
    
    print("\n" + "="*40)
    
    # Teste 2: Scraping real (pequeno)
    test_small_scraping()
    
    print("\n🎉 Testes concluídos!")
