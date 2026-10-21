"""
Sistema de Diário Escolar Individual da Professora.
Desenvolvido em Python com Flask e SQLite.
Interface responsiva moderna (Azul e Branco) para Windows e Mobile.
"""

import os
import socket
from datetime import date
from flask import Flask, render_template, request, redirect, url_for, flash, jsonify
import database

app = Flask(__name__)
app.secret_key = "diario-escolar-professora-chave-secreta-2026"

# Inicializa o banco de dados e carrega os 15 alunos e matérias iniciais caso não existam
database.init_db()

def get_local_ip():
    """Obtém o IP local da máquina para acesso no celular na mesma rede Wi-Fi."""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "127.0.0.1"

# Injeta a data atual e matérias em todos os templates
@app.context_processor
def inject_globals():
    return {
        "hoje": date.today().strftime("%Y-%m-%d"),
        "materias_globais": database.listar_materias(),
        "total_alunos_ativos": len(database.listar_alunos(apenas_ativos=True))
    }

# --- Rotas Principais ---

@app.route("/")
def index():
    """Painel principal (Dashboard)."""
    stats = database.obter_estatisticas_gerais()
    ultimas_aulas = database.listar_aulas(limite=5)
    alunos = database.listar_alunos()
    return render_template("index.html", stats=stats, ultimas_aulas=ultimas_aulas, alunos=alunos)

# --- Gerenciamento de Aulas & Chamada ---

@app.route("/aulas")
def aulas():
    """Lista todas as aulas registradas."""
    todas_aulas = database.listar_aulas(limite=100)
    return render_template("aulas.html", aulas=todas_aulas)

@app.route("/aulas/nova", methods=["GET", "POST"])
def nova_aula():
    """Registra um novo dia/aula com conteúdo e chamada de presença."""
    alunos = database.listar_alunos(apenas_ativos=True)
    materias = database.listar_materias()

    if request.method == "POST":
        data = request.form.get("data")
        materia_id = request.form.get("materia_id")
        conteudo = request.form.get("conteudo")
        observacoes = request.form.get("observacoes", "")

        if not data or not materia_id or not conteudo:
            flash("Por favor, preencha a data, selecione a matéria e informe o conteúdo da aula.", "danger")
            return render_template("nova_aula.html", alunos=alunos, materias=materias)

        presencas_dict = {}
        for aluno in alunos:
            status = request.form.get(f"status_{aluno['id']}", "presente")
            presencas_dict[aluno["id"]] = status

        try:
            aula_id = database.registrar_aula_com_chamada(data, materia_id, conteudo, observacoes, presencas_dict)
            flash("Aula e chamada registradas com sucesso!", "success")
            return redirect(url_for("detalhe_aula", aula_id=aula_id))
        except Exception as e:
            flash(f"Erro ao salvar aula: {str(e)}", "danger")

    return render_template("nova_aula.html", alunos=alunos, materias=materias)

@app.route("/aulas/<int:aula_id>")
def detalhe_aula(aula_id):
    """Visualiza detalhes de uma aula específica e sua lista de presença."""
    aula, presencas = database.obter_aula_detalhada(aula_id)
    if not aula:
        flash("Aula não encontrada.", "warning")
        return redirect(url_for("aulas"))
    return render_template("aula_detalhe.html", aula=aula, presencas=presencas)

@app.route("/aulas/<int:aula_id>/excluir", methods=["POST"])
def excluir_aula(aula_id):
    """Exclui um registro de aula."""
    database.excluir_aula(aula_id)
    flash("Registro de aula excluído com sucesso.", "info")
    return redirect(url_for("aulas"))

# --- Gerenciamento de Alunos ---

@app.route("/alunos")
def alunos():
    """Lista e gerencia os alunos."""
    lista_alunos = database.listar_alunos(apenas_ativos=False)
    return render_template("alunos.html", alunos=lista_alunos)

@app.route("/alunos/adicionar", methods=["POST"])
def adicionar_aluno():
    nome = request.form.get("nome")
    numero = request.form.get("numero_chamada")
    if nome and numero:
        database.adicionar_aluno(int(numero), nome)
        flash(f"Aluno {nome} cadastrado com sucesso!", "success")
    else:
        flash("Preencha o número e o nome do aluno.", "danger")
    return redirect(url_for("alunos"))

@app.route("/alunos/<int:aluno_id>/editar", methods=["POST"])
def editar_aluno(aluno_id):
    nome = request.form.get("nome")
    numero = request.form.get("numero_chamada")
    ativo = 1 if request.form.get("ativo") == "1" else 0
    if nome and numero:
        database.atualizar_aluno(aluno_id, int(numero), nome, ativo)
        flash("Dados do aluno atualizados!", "success")
    return redirect(url_for("alunos"))

@app.route("/alunos/<int:aluno_id>/excluir", methods=["POST"])
def excluir_aluno(aluno_id):
    database.excluir_aluno(aluno_id)
    flash("Aluno removido do diário.", "info")
    return redirect(url_for("alunos"))

# --- Histórico Individual do Aluno ---

@app.route("/alunos/<int:aluno_id>/historico")
def historico_aluno(aluno_id):
    """Consulta o histórico individual do aluno (conteúdos, presenças e faltas)."""
    aluno, stats, historico = database.obter_historico_aluno(aluno_id)
    if not aluno:
        flash("Aluno não encontrado.", "warning")
        return redirect(url_for("alunos"))
    
    todos_alunos = database.listar_alunos(apenas_ativos=True)
    return render_template("aluno_historico.html", aluno=aluno, stats=stats, historico=historico, todos_alunos=todos_alunos)

# --- Gerenciamento de Matérias ---

@app.route("/materias", methods=["GET", "POST"])
def materias():
    """Gerencia as matérias cadastradas."""
    if request.method == "POST":
        nome = request.form.get("nome")
        cor_tag = request.form.get("cor_tag", "#2563eb")
        if nome:
            try:
                database.adicionar_materia(nome, cor_tag)
                flash(f"Matéria '{nome}' adicionada com sucesso!", "success")
            except Exception:
                flash("Essa matéria já existe ou houve um erro no cadastro.", "danger")
        return redirect(url_for("materias"))

    lista_materias = database.listar_materias()
    return render_template("materias.html", materias=lista_materias)

@app.route("/materias/<int:materia_id>/excluir", methods=["POST"])
def excluir_materia(materia_id):
    try:
        database.excluir_materia(materia_id)
        flash("Matéria removida com sucesso.", "info")
    except Exception as e:
        flash("Não foi possível excluir a matéria (pode haver aulas vinculadas).", "danger")
    return redirect(url_for("materias"))

# --- Estatísticas e Relatórios ---

@app.route("/estatisticas")
def estatisticas():
    """Exibe painel de estatísticas completas da turma e das matérias."""
    dados = database.obter_estatisticas_gerais()
    return render_template("estatisticas.html", stats=dados)

if __name__ == "__main__":
    local_ip = get_local_ip()
    port = 5000
    print("=" * 60)
    print(" 📘 DIÁRIO ESCOLAR DA PROFESSORA - SISTEMA INICIADO")
    print("=" * 60)
    print(f" 💻 No seu computador (Windows): http://localhost:{port}")
    print(f" 📱 No celular (mesmo Wi-Fi):   http://{local_ip}:{port}")
    print("=" * 60)
    print(" Pressione Ctrl+C na janela para parar o sistema quando desejar.")
    print("=" * 60)
    app.run(host="0.0.0.0", port=port, debug=True)
