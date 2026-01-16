from flask import Flask, render_template, jsonify, request
import os
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()

app = Flask(__name__, template_folder='../frontend')
app.secret_key = os.getenv('SECRET_KEY', 'chave-temporaria-123')

@app.route('/')
def home():
    """Página inicial do sistema"""
    return render_template('dashboard.html')

@app.route('/buscar-precatorios')
def buscar_precatorios():
    """Busca precatórios nos tribunais"""
    return jsonify({
        "status": "Sistema funcionando!",
        "tribunais": ["TRF1", "TRF2", "TRF3"],
        "total_encontrados": 0
    })

@app.route('/gerar-oferta', methods=['POST'])
def gerar_oferta():
    """Gera oferta personalizada"""
    dados_precatorio = request.json
    
    # Por enquanto, uma oferta simples sem IA
    oferta_template = f"""
PROPOSTA DE AQUISIÇÃO DE PRECATÓRIO

Prezado(a) {dados_precatorio.get('beneficiario', 'Beneficiário')},

Somos uma empresa especializada na aquisição de precatórios e temos interesse em adquirir seu direito creditório no valor de R$ {dados_precatorio.get('valor', 0):,.2f}, referente ao processo junto ao {dados_precatorio.get('tribunal', 'tribunal')}.

NOSSA PROPOSTA:
• Pagamento à vista
• Processo transparente e seguro
• Documentação completa
• Assessoria jurídica especializada

Para mais informações, entre em contato conosco.

Atenciosamente,
Equipe de Aquisição de Precatórios
"""
    
    return jsonify({"oferta": oferta_template})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
