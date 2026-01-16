"""
PRECATÓRIO HUNTER PRO WEB - Aplicação Principal Flask
Versão Web Otimizada para Render
"""

from flask import Flask, render_template, request, jsonify, redirect, url_for
import asyncio
import os
import logging
from datetime import datetime
import json

# Importa nossos módulos
try:
    import sys
    sys.path.append('.')
    from arquivo import DatabaseManager
    from arquivo_2 import WebPrecatorioCollector  
    from arquivo_3 import WebAIAnalyzer
except ImportError as e:
    print(f"❌ Erro ao importar módulos: {e}")

# Configuração da aplicação Flask
app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'precatorio-hunter-pro-2024')

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("PrecatorioHunterWeb")

# Variáveis globais para os serviços
db_manager = None
collector = None
ai_analyzer = None

# Configurações do ambiente
DATABASE_URL = os.environ.get('DATABASE_URL', 'postgresql://localhost/precatorios')
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY', '')

async def inicializar_servicos():
    """Inicializa todos os serviços da aplicação"""
    global db_manager, collector, ai_analyzer
    
    try:
        # Database Manager
        db_manager = DatabaseManager(DATABASE_URL)
        await db_manager.initialize()
        
        # Web Collector
        collector = WebPrecatorioCollector()
        
        # AI Analyzer
        ai_analyzer = WebAIAnalyzer(GEMINI_API_KEY)
        
        logger.info("✅ Todos os serviços inicializados com sucesso")
        
    except Exception as e:
        logger.error(f"❌ Erro ao inicializar serviços: {e}")
        raise

@app.route('/')
def index():
    """Página inicial"""
    return render_template('index.html')

@app.route('/dashboard')
def dashboard():
    """Dashboard principal"""
    try:
        # Executa operações assíncronas
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Busca estatísticas
        stats = loop.run_until_complete(db_manager.obter_estatisticas())
        
        # Busca leads recentes
        leads_recentes = loop.run_until_complete(
            db_manager.buscar_leads(limit=10)
        )
        
        loop.close()
        
        return render_template('dashboard.html', 
                             stats=stats, 
                             leads=leads_recentes)
    
    except Exception as e:
        logger.error(f"Erro no dashboard: {e}")
        return render_template('dashboard.html', 
                             stats={}, 
                             leads=[], 
                             erro=str(e))

@app.route('/api/coletar', methods=['POST'])
def api_coletar():
    """API para executar coleta de precatórios"""
    try:
        data = request.get_json()
        tribunais_selecionados = data.get('tribunais', [])
        
        # Executa coleta
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        precatorios_coletados = loop.run_until_complete(
            collector.coletar_todos_tribunais()
        )
        
        # Filtra por tribunais selecionados se especificado
        if tribunais_selecionados:
            precatorios_coletados = [
                p for p in precatorios_coletados 
                if p.get('tribunal') in tribunais_selecionados
            ]
        
        # Processa cada precatório com IA
        precatorios_processados = []
        
        for precatorio in precatorios_coletados:
            # Análise IA
            precatorio_analisado = loop.run_until_complete(
                ai_analyzer.analisar_completo(precatorio)
            )
            
            # Salva no banco
            sucesso = loop.run_until_complete(
                db_manager.salvar_lead(precatorio_analisado)
            )
            
            if sucesso:
                precatorios_processados.append(precatorio_analisado)
        
        loop.close()
        
        return jsonify({
            'sucesso': True,
            'total_coletados': len(precatorios_coletados),
            'total_salvos': len(precatorios_processados),
            'leads': precatorios_processados[:5]  # Primeiros 5 para preview
        })
    
    except Exception as e:
        logger.error(f"Erro na coleta: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@app.route('/api/leads')
def api_leads():
    """API para buscar leads"""
    try:
        # Parâmetros de filtro
        limit = int(request.args.get('limit', 50))
        filtro_prioridade = request.args.get('prioridade')
        filtro_tribunal = request.args.get('tribunal')
        filtro_status = request.args.get('status')
        
        # Busca leads
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        leads = loop.run_until_complete(
            db_manager.buscar_leads(
                limit=limit,
                filtro_prioridade=filtro_prioridade,
                filtro_tribunal=filtro_tribunal,
                filtro_status=filtro_status
            )
        )
        
        loop.close()
        
        return jsonify({
            'sucesso': True,
            'leads': leads,
            'total': len(leads)
        })
    
    except Exception as e:
        logger.error(f"Erro ao buscar leads: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@app.route('/api/lead/<lead_id>')
def api_lead_detalhes(lead_id):
    """API para buscar detalhes de um lead"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        lead = loop.run_until_complete(
            db_manager.buscar_lead_por_id(lead_id)
        )
        
        loop.close()
        
        if lead:
            return jsonify({
                'sucesso': True,
                'lead': lead
            })
        else:
            return jsonify({
                'sucesso': False,
                'erro': 'Lead não encontrado'
            }), 404
    
    except Exception as e:
        logger.error(f"Erro ao buscar lead {lead_id}: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@app.route('/api/lead/<lead_id>/status', methods=['PUT'])
def api_atualizar_status(lead_id):
    """API para atualizar status de um lead"""
    try:
        data = request.get_json()
        novo_status = data.get('status')
        
        if not novo_status:
            return jsonify({
                'sucesso': False,
                'erro': 'Status é obrigatório'
            }), 400
        
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        sucesso = loop.run_until_complete(
            db_manager.atualizar_status_lead(lead_id, novo_status)
        )
        
        loop.close()
        
        return jsonify({
            'sucesso': sucesso,
            'mensagem': 'Status atualizado' if sucesso else 'Erro ao atualizar'
        })
    
    except Exception as e:
        logger.error(f"Erro ao atualizar status: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@app.route('/api/stats')
def api_estatisticas():
    """API para estatísticas do sistema"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        stats = loop.run_until_complete(db_manager.obter_estatisticas())
        
        loop.close()
        
        return jsonify({
            'sucesso': True,
            'estatisticas': stats
        })
    
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        return jsonify({
            'sucesso': False,
            'erro': str(e)
        }), 500

@app.route('/health')
def health_check():
    """Health check para monitoramento"""
    try:
        # Verifica se os serviços estão funcionais
        status = {
            'aplicacao': 'ok',
            'database': 'ok' if db_manager and db_manager.pool else 'erro',
            'collector': 'ok' if collector else 'erro',
            'ai_analyzer': 'ok' if ai_analyzer else 'erro',
            'timestamp': datetime.now().isoformat()
        }
        
        return jsonify(status)
    
    except Exception as e:
        return jsonify({
            'aplicacao': 'erro',
            'erro': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.errorhandler(404)
def nao_encontrado(e):
    """Página de erro 404"""
    return render_template('404.html'), 404

@app.errorhandler(500)
def erro_interno(e):
    """Página de erro 500"""
    logger.error(f"Erro interno: {e}")
    return render_template('500.html'), 500

# Inicialização da aplicação
def inicializar_aplicacao():
    """Inicializa a aplicação de forma síncrona"""
    try:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        loop.run_until_complete(inicializar_servicos())
        loop.close()
        logger.info("🚀 Aplicação inicializada com sucesso")
    except Exception as e:
        logger.error(f"❌ Erro na inicialização: {e}")

# Inicializa serviços quando a aplicação carrega
with app.app_context():
    try:
        inicializar_aplicacao()
    except Exception as e:
        logger.error(f"Erro na inicialização: {e}")

if __name__ == '__main__':
    # Configuração para produção no Render
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    
    logger.info(f"🚀 Iniciando Precatório Hunter Pro Web na porta {port}")
    
    app.run(
        host='0.0.0.0',
        port=port,
        debug=debug,
        threaded=True
    )
