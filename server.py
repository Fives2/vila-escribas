import copy
import itertools
import random
import time

import socketio

sio = socketio.AsyncServer(async_mode="asgi", cors_allowed_origins="*")
app = socketio.ASGIApp(sio, static_files={
    "/": "client/index.html",
    "/assets": "client/assets",      # mapa, tileset e sprites da vila
})

# =====================================================================
#  VILA DOS ESCRIBAS - servidor (fonte da verdade)
#
#  Tinta e Papel -> Scriptorium (escrever) -> manuscrito
#                -> Bancada (encadernar, escolhendo a cor) -> livro na Estante
#                -> Entrega de uma encomenda com prazo -> ouro
#
#  Regra de ouro: o servidor decide TUDO. O cliente só pede e mostra.
#  Validar e alterar o estado SEM await no meio: assim o servidor decide
#  um pedido por vez, mesmo que dois cheguem "ao mesmo tempo".
# =====================================================================

# ----- regras (iguais às de docs/especificacao.md) -----
CORES = ["vermelho", "azul", "verde", "preto"]
CUSTO_ESCRITA = 30          # Tinta e Papel gastos para escrever 1 manuscrito
TEMPO_ESCRITA = 6           # segundos até o Scriptorium terminar de escrever
TEMPO_ENCADERNACAO = 5      # segundos até a Bancada terminar de encadernar
INTERVALO = 5               # segundos entre as produções de Tinta e Papel
PRODUCAO = 10               # Tinta e Papel produzidos a cada INTERVALO
LIMITE_ESCRIBAS = 4         # escribas que podem trabalhar ao mesmo tempo
CAPACIDADE_ESTANTE = 6      # livros que cabem na estante
INTERVALO_ENCOMENDA = 25    # segundos entre uma encomenda e outra
PRAZO_ENCOMENDA = 45        # segundos que o cliente espera pelo livro
MAX_ENCOMENDAS = 3          # encomendas abertas ao mesmo tempo
VALOR_ENCOMENDA = 60        # ouro por livro entregue
BONUS_RAPIDA = 20           # ouro extra se entregue na primeira metade do prazo

estado = {
    "fase": "aguardando",     # aguardando -> aberta -> encerrada
    "tinta_papel": 100,       # UM recurso só (tinta e papel juntos)
    "producao": PRODUCAO,
    "intervalo": INTERVALO,
    "escribas": 0,            # ocupados agora (compartilhados)
    "limite": LIMITE_ESCRIBAS,
    "manuscritos": 0,         # escritos no Scriptorium, esperando encadernação
    "escrevendo": 0,          # obras em andamento no Scriptorium
    "encadernando": 0,        # obras em andamento na Bancada
    "estante": [],            # cores dos livros encadernados (ex.: ["azul", "preto"])
    "capacidade": CAPACIDADE_ESTANTE,
    "cores": CORES,
    "custo_escrita": CUSTO_ESCRITA,
    "tempo_escrita": TEMPO_ESCRITA,
    "tempo_encadernacao": TEMPO_ENCADERNACAO,
    "encomendas": [],         # {"id", "cor", "valor", "prazo", "expira_em"}
    "ouro": 0,                # os pontos da vila
    "entregues": 0,
    "expiradas": 0,
}
jogadores = {}                # sid -> {"nome": ..., "papel": ...}
ids_encomenda = itertools.count(1)


def fato(causa, **extras):
    """Monta o payload de um FATO: o estado atual, a CAUSA (o pedido ou o
    temporizador que gerou o fato) e dados extras (sempre valores simples)."""
    foto = copy.deepcopy(estado)
    agora = time.time()
    for enc in foto["encomendas"]:
        # tempo restante no momento do fato (o cliente só mostra a contagem)
        enc["restante"] = max(0, round(enc.pop("expira_em") - agora))
    return {"estado": foto, "causa": causa, **extras}


async def recusar(sid, motivo, causa):
    """Responde só a quem pediu."""
    await sio.emit("operacao.recusada", {"motivo": motivo, "causa": causa}, to=sid)


def achar_encomenda(id_enc):
    return next((e for e in estado["encomendas"] if e["id"] == id_enc), None)


# ---------------------------------------------------------------------
#  Conexão
# ---------------------------------------------------------------------
@sio.event
async def connect(sid, environ, auth):
    auth = auth or {}
    jogadores[sid] = {
        "nome": auth.get("nome", "Anônimo"),
        "papel": auth.get("papel", "jogador"),
    }
    # servidor -> UM cliente: quem já estava conectado já tem o estado
    await sio.emit("estado.sincronizado", fato("conexao"), to=sid)


@sio.event
async def disconnect(sid):
    jogadores.pop(sid, None)


