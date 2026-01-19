from flask import Flask, render_template, jsonify, request, redirect, url_for
import os
import requests
from datetime import datetime
import logging

# Configurar logs para debug
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.getenv('SECRET_KEY', 'precatorio-hunter-2024')

# Estado global para debug
app_state = {
    'inicializado': False,
    'api_google_ok': False,
    'total_buscas': 0,
    'ofertas_geradas': 0,
    'leads': []
}

@app.route('/')
def home():
    """Dashboard principal com status do sistema"""
    logger.info("Acessando dashboard principal")
    return render_template('dashboard.html', state=app_state)

@app.route('/health')
def health_check():
    """Verificação de saúde do sistema"""
    status = {
        'sistema': 'online',
        'timestamp': datetime.now().isoformat(),
        'google_ai': 'testando...',
        'database': 'ok',
        'version': '2.0'
    }
    
    # Testar Google AI
    try:
        api_key = os.getenv('GOOGLE_AI_API_KEY')
        if api_key and len(api_key) > 30:
            status['google_ai'] = 'configurado'
            app_state['api_google_ok'] = True
        else:
            status['google_ai'] = 'não configurado'
    except Exception as e:
        status['google_ai'] = f'erro: {str(e)}'
    
    app_state['inicializado'] = True
    return jsonify(status)

@app.route('/buscar-processo', methods=['POST'])
def buscar_processo():
    """Busca específica por número de processo"""
    try:
        numero_processo = request.json.get('numero_processo', '').strip()
        
        if not numero_processo:
            return jsonify({'erro': 'Número do processo obrigatório'}), 400
        
        logger.info(f"Buscando processo: {numero_processo}")
        
        # Simulação de busca (depois implementamos busca real)
        resultado = {
            'numero_processo': numero_processo,
            'encontrado': True,
            'beneficiario': f'Beneficiário Teste {numero_processo[-4:]}',
            'valor': 50000.00 + (hash(numero_processo) % 100000),
            'tribunal': 'TRF1',
            'status': 'Ativo',
            'data_busca': datetime.now().isoformat()
        }
        
        # Adicionar aos leads
        app_state['leads'].append(resultado)
        app_state['total_buscas'] += 1
        
        logger.info(f"Processo encontrado: {resultado['beneficiario']}")
        return jsonify(resultado)
        
    except Exception as e:
        logger.error(f"Erro na busca: {str(e)}")
        return jsonify({'erro': str(e)}), 500

@app.route('/gerar-oferta', methods=['POST'])
def gerar_oferta():
    """Gera oferta para um lead específico"""
    try:
        dados = request.json
        logger.info(f"Gerando oferta para: {dados.get('beneficiario')}")
        
        # Tentar com Google AI primeiro
        oferta = gerar_oferta_ia(dados)
        
        if not oferta:
            # Fallback para template
            oferta = gerar_oferta_template(dados)
        
        app_state['ofertas_geradas'] += 1
        
        return jsonify({
            'oferta': oferta,
            'metodo': 'ia' if 'Gemini' in oferta else 'template',
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Erro ao gerar oferta: {str(e)}")
        return jsonify({'erro': str(e)}), 500

def gerar_oferta_ia(dados):
    """Tenta gerar oferta com Google AI"""
    try:
        import google.generativeai as genai
        
        api_key = os.getenv('GOOGLE_AI_API_KEY')
        if not api_key:
            return None
            
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-pro')
        
        prompt = f"""
        Como advogado especialista em precatórios, crie uma oferta profissional:
        
        Beneficiário: {dados.get('beneficiario', 'Não informado')}
        Valor: R$ {dados.get('valor', 0):,.2f}
        Tribunal: {dados.get('tribunal', 'Não informado')}
        Processo: {dados.get('numero_processo', 'Não informado')}
        
        A oferta deve ser:
        - Respeitosa e transparente
        - Explicar vantagens da cessão
        - Mencionar segurança jurídica
        - Incluir próximos passos claros
        - Máximo 250 palavras
        
        Assine como: "Equipe Precatório Hunter - Powered by Gemini AI"
        """
        
        response = model.generate_content(prompt)
        return response.text
        
    except Exception as e:
        logger.error(f"Erro na IA: {str(e)}")
        return None

def gerar_oferta_template(dados):
    """Fallback - oferta usando template"""
    return f"""
PROPOSTA DE AQUISIÇÃO DE PRECATÓRIO

Prezado(a) {dados.get('beneficiario', 'Beneficiário')},

Somos especializados na aquisição de precatórios e temos interesse em seu direito creditório:

📋 DADOS DO PRECATÓRIO:
• Processo: {dados.get('numero_processo', 'N/A')}
• Valor: R$ {dados.get('valor', 0):,.2f}
• Tribunal: {dados.get('tribunal', 'N/A')}

💼 NOSSA PROPOSTA:
• Pagamento à vista
• Processo 100% transparente e seguro
• Sem custos ou taxas para você
• Documentação completa inclusa
• Assessoria jurídica especializada

📞 PRÓXIMOS PASSOS:
1. Análise gratuita do seu processo
2. Proposta personalizada
3. Documentação e assinatura
4. Pagamento imediato

Entre em contato para mais informações.

Atenciosamente,
Equipe Precatório Hunter
Sistema Automatizado v2.0
    """

@app.route('/leads')
def listar_leads():
    """Lista todos os leads encontrados"""
    return jsonify({
        'leads': app_state['leads'],
        'total': len(app_state['leads']),
        'stats': {
            'total_buscas': app_state['total_buscas'],
            'ofertas_geradas': app_state['ofertas_geradas']
        }
    })

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
