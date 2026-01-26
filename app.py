from flask import Flask, render_template, request, jsonify
import google.generativeai as genai
import os
import psycopg2
from psycopg2.extras import RealDictCursor
import re

app = Flask(__name__)

# Configurar Gemini
GOOGLE_API_KEY = os.environ.get('GOOGLE_API_KEY')
if GOOGLE_API_KEY:
    genai.configure(api_key=GOOGLE_API_KEY)
    model = genai.GenerativeModel('gemini-pro')

# Configurar Banco de Dados
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db_connection():
    """Cria conexão com o banco de dados"""
    conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
    return conn

def init_db():
    """Inicializa as tabelas do banco de dados"""
    conn = get_db_connection()
    cur = conn.cursor()
    
    # Tabela de precatórios
    cur.execute('''
        CREATE TABLE IF NOT EXISTS precatorios (
            id SERIAL PRIMARY KEY,
            trf VARCHAR(10) NOT NULL,
            ordem INTEGER,
            numero_precatorio VARCHAR(50) NOT NULL,
            valor DECIMAL(15,2),
            preferencia_legal VARCHAR(100),
            nome_beneficiario VARCHAR(255),
            telefone VARCHAR(50),
            email VARCHAR(255),
            status VARCHAR(50) DEFAULT 'novo',
            data_importacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(trf, numero_precatorio)
        )
    ''')
    
    # Tabela de ofertas geradas
    cur.execute('''
        CREATE TABLE IF NOT EXISTS ofertas (
            id SERIAL PRIMARY KEY,
            precatorio_id INTEGER REFERENCES precatorios(id),
            texto_oferta TEXT,
            deságio_percentual DECIMAL(5,2),
            valor_oferta DECIMAL(15,2),
            data_geracao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    conn.commit()
    cur.close()
    conn.close()

# Inicializar banco ao iniciar app
try:
    if DATABASE_URL:
        init_db()
        print("✅ Banco de dados inicializado com sucesso!")
except Exception as e:
    print(f"⚠️ Erro ao inicializar banco: {e}")

def parse_valor(valor_str):
    """Converte string de valor para float"""
    if not valor_str:
        return 0.0
    # Remove espaços e caracteres especiais
    valor_str = valor_str.strip()
    # Remove R$ se existir
    valor_str = valor_str.replace('R$', '').strip()
    # Remove pontos de milhar e troca vírgula por ponto
    valor_str = valor_str.replace('.', '').replace(',', '.')
    try:
        return float(valor_str)
    except:
        return 0.0

def parse_tabela(texto, trf):
    """Faz o parse da tabela colada pelo usuário"""
    linhas = texto.strip().split('\n')
    precatorios = []
    
    for linha in linhas:
        # Pula linhas vazias ou cabeçalhos
        linha = linha.strip()
        if not linha:
            continue
        if 'ORDEM' in linha.upper() or 'PRECATÓRIO' in linha.upper() or 'VALOR' in linha.upper():
            continue
        if 'PODER JUDICIÁRIO' in linha.upper() or 'TRIBUNAL' in linha.upper():
            continue
        if 'ALIMENTAR' in linha.upper() or 'RELAÇÃO' in linha.upper():
            continue
            
        # Tenta extrair dados da linha
        # Padrão esperado: ORDEM | PRECATÓRIO | VALOR | PREFERÊNCIA
        partes = re.split(r'\t+|\s{2,}', linha)
        partes = [p.strip() for p in partes if p.strip()]
        
        if len(partes) >= 3:
            try:
                ordem = int(partes[0]) if partes[0].isdigit() else None
                numero = partes[1] if len(partes[1]) > 10 else partes[0]
                
                # Procura o valor (contém vírgula e números)
                valor = 0.0
                preferencia = '-'
                
                for i, parte in enumerate(partes):
                    if ',' in parte and any(c.isdigit() for c in parte):
                        valor = parse_valor(parte)
                    elif 'maior' in parte.lower() or 'idade' in parte.lower() or 'doença' in parte.lower():
                        preferencia = parte
                    elif i == len(partes) - 1 and valor > 0:
                        preferencia = parte if parte != '-' else preferencia
                
                if numero and len(numero) > 10:
                    precatorios.append({
                        'trf': trf,
                        'ordem': ordem,
                        'numero_precatorio': numero,
                        'valor': valor,
                        'preferencia_legal': preferencia
                    })
            except Exception as e:
                print(f"Erro ao parsear linha: {linha} - {e}")
                continue
    
    return precatorios

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/importar', methods=['POST'])
def importar_tabela():
    """Importa tabela de precatórios"""
    try:
        data = request.json
        trf = data.get('trf', 'TRF1')
        tabela_texto = data.get('tabela', '')
        
        if not tabela_texto:
            return jsonify({'success': False, 'error': 'Nenhuma tabela fornecida'})
        
        # Parse da tabela
        precatorios = parse_tabela(tabela_texto, trf)
        
        if not precatorios:
            return jsonify({'success': False, 'error': 'Não foi possível extrair dados da tabela. Verifique o formato.'})
        
        # Salvar no banco
        conn = get_db_connection()
        cur = conn.cursor()
        
        inseridos = 0
        atualizados = 0
        
        for p in precatorios:
            try:
                cur.execute('''
                    INSERT INTO precatorios (trf, ordem, numero_precatorio, valor, preferencia_legal)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (trf, numero_precatorio) 
                    DO UPDATE SET valor = EXCLUDED.valor, preferencia_legal = EXCLUDED.preferencia_legal
                    RETURNING (xmax = 0) AS inserted
                ''', (p['trf'], p['ordem'], p['numero_precatorio'], p['valor'], p['preferencia_legal']))
                
                result = cur.fetchone()
                if result['inserted']:
                    inseridos += 1
                else:
                    atualizados += 1
            except Exception as e:
                print(f"Erro ao inserir precatório: {e}")
                continue
        
        conn.commit()
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'message': f'Importação concluída! {inseridos} novos precatórios inseridos, {atualizados} atualizados.',
            'total': len(precatorios)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/precatorios')
def listar_precatorios():
    """Lista precatórios do banco"""
    try:
        trf = request.args.get('trf', '')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        if trf:
            cur.execute('''
                SELECT * FROM precatorios 
                WHERE trf = %s 
                ORDER BY valor DESC
            ''', (trf,))
        else:
            cur.execute('''
                SELECT * FROM precatorios 
                ORDER BY trf, valor DESC
            ''')
        
        precatorios = cur.fetchall()
        cur.close()
        conn.close()
        
        return jsonify({'success': True, 'precatorios': precatorios})
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/estatisticas')
def estatisticas():
    """Retorna estatísticas dos precatórios"""
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute('''
            SELECT 
                trf,
                COUNT(*) as total,
                SUM(valor) as valor_total,
                AVG(valor) as valor_medio
            FROM precatorios
            GROUP BY trf
            ORDER BY trf
        ''')
        
        stats = cur.fetchall()
        
        cur.execute('SELECT COUNT(*) as total, SUM(valor) as valor_total FROM precatorios')
        total_geral = cur.fetchone()
        
        cur.close()
        conn.close()
        
        return jsonify({
            'success': True, 
            'por_trf': stats,
            'total_geral': total_geral
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/gerar-oferta', methods=['POST'])
def gerar_oferta():
    """Gera oferta personalizada usando IA"""
    try:
        data = request.json
        precatorio_id = data.get('precatorio_id')
        
        # Buscar dados do precatório
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute('SELECT * FROM precatorios WHERE id = %s', (precatorio_id,))
        precatorio = cur.fetchone()
        cur.close()
        conn.close()
        
        if not precatorio:
            return jsonify({'success': False, 'error': 'Precatório não encontrado'})
        
        # Gerar oferta com IA
        prompt = f"""
        Você é um especialista em compra de precatórios federais. Gere uma proposta comercial 
        profissional e persuasiva para aquisição do seguinte precatório:

        - Tribunal: {precatorio['trf']}
        - Número do Precatório: {precatorio['numero_precatorio']}
        - Valor: R$ {precatorio['valor']:,.2f}
        - Preferência Legal: {precatorio['preferencia_legal']}
        
        A proposta deve:
        1. Ser cordial e profissional
        2. Explicar brevemente as vantagens de antecipar o recebimento
        3. Oferecer um deságio de 20% a 35% dependendo do perfil
        4. Mencionar que o pagamento é rápido (até 48h após assinatura)
        5. Ser concisa (máximo 200 palavras)
        
        Formato: texto pronto para enviar por WhatsApp/Email.
        """
        
        response = model.generate_content(prompt)
        oferta_texto = response.text
        
        return jsonify({
            'success': True,
            'oferta': oferta_texto,
            'precatorio': dict(precatorio)
        })
        
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

if __name__ == '__main__':
    app.run(debug=True)
