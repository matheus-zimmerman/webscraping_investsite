"""
Demonstração do sistema otimizado - versão limitada para demonstração
"""
import sys
import os
sys.path.append(os.path.dirname(__file__))

from stocks import StocksScraper
import time

def demo_otimizado():
    """Demonstração das otimizações"""
    print("🚀 DEMONSTRAÇÃO DO SISTEMA OTIMIZADO")
    print("=" * 50)
    
    # Lista de ações para teste
    test_codes = ["PETR4", "VALE3", "ITUB4", "BBDC4", "ABEV3", "WEGE3", "MGLU3", "VIVT3"]
    
    print(f"📊 Testando com {len(test_codes)} ações: {', '.join(test_codes)}")
    print()
    
    # Teste 1: Sequencial (original)
    print("🐌 TESTE 1: MODO SEQUENCIAL (Original)")
    print("-" * 40)
    scraper1 = StocksScraper(use_selenium=False, max_workers=1, batch_size=1)
    
    start_time = time.time()
    scraper1.scrape_all_stocks_legacy(test_codes)
    sequential_time = time.time() - start_time
    
    print(f"⏱️ Tempo sequencial: {sequential_time:.1f} segundos")
    
    # Reset para próximo teste
    scraper1.stocks_data = []
    
    print("\n" + "="*50)
    
    # Teste 2: Paralelo otimizado
    print("⚡ TESTE 2: MODO PARALELO OTIMIZADO")
    print("-" * 40)
    scraper2 = StocksScraper(use_selenium=False, max_workers=4, batch_size=4)
    
    start_time = time.time()
    scraper2.scrape_all_stocks(test_codes)
    parallel_time = time.time() - start_time
    
    print(f"⏱️ Tempo paralelo: {parallel_time:.1f} segundos")
    
    # Comparação
    improvement = sequential_time / parallel_time if parallel_time > 0 else 1
    
    print("\n" + "="*50)
    print("📈 RESULTADO DA OTIMIZAÇÃO")
    print("-" * 40)
    print(f"   🐌 Modo sequencial: {sequential_time:.1f}s")
    print(f"   ⚡ Modo paralelo: {parallel_time:.1f}s")
    print(f"   🚀 Melhoria: {improvement:.1f}x mais rápido")
    print(f"   💰 Tempo economizado: {sequential_time - parallel_time:.1f} segundos")
    
    # Mostra sample dos dados coletados
    print(f"\n📊 AMOSTRA DOS DADOS COLETADOS")
    print("-" * 40)
    for i, stock in enumerate(scraper2.stocks_data[:3], 1):
        if "Erro" not in stock:
            print(f"{i}. {stock.get('Código', 'N/A')}")
            print(f"   🏢 {stock.get('Empresa', 'N/A')}")
            print(f"   💰 Preço: {stock.get('Último Preço de Fechamento', 'N/A')}")
            print(f"   📊 P/L: {stock.get('Indicador - Preço/Lucro', 'N/A')}")
            print(f"   🆕 Earnings Yield: {stock.get('Earnings Yield (%)', 'N/A')}")
            print()

if __name__ == "__main__":
    demo_otimizado()
