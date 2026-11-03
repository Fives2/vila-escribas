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


# ---------------------------------------------------------------------
#  O Mestre abre e encerra a temporada
# ---------------------------------------------------------------------
@sio.on("vila.abertura_solicitada")
async def abrir_vila(sid, dados=None):
    pedido = "vila.abertura_solicitada"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode abrir a temporada", pedido)
        return
    if estado["fase"] != "aguardando":
        await recusar(sid, "A temporada já foi aberta", pedido)
        return
    estado["fase"] = "aberta"
    await sio.emit("vila.iniciada", fato(pedido))          # para todos
    # Os temporizadores começam DEPOIS de avisar que a vila abriu, para que
    # nenhum fato do tempo chegue antes do vila.iniciada.
    sio.start_background_task(producao)
    sio.start_background_task(gerador_encomendas)


@sio.on("vila.encerramento_solicitado")
async def encerrar_vila(sid, dados=None):
    pedido = "vila.encerramento_solicitado"
    if jogadores[sid]["papel"] != "mestre":
        await recusar(sid, "Só o Mestre pode encerrar a temporada", pedido)
        return
    if estado["fase"] != "aberta":
        await recusar(sid, "A temporada não está aberta", pedido)
        return
    estado["fase"] = "encerrada"
    # os temporizadores em andamento percebem a fase e param sozinhos
    await sio.emit("vila.encerrada", fato(pedido, ouro_final=estado["ouro"]))


# ---------------------------------------------------------------------
#  Scriptorium: escrever (pedido -> fato -> temporizador -> fato)
# ---------------------------------------------------------------------
@sio.on("escrita.solicitada")
async def escrever(sid, dados=None):
    pedido = "escrita.solicitada"
    # Valide TUDO antes de alterar o estado e sem await no meio.
    if jogadores[sid]["papel"] != "jogador":
        motivo = "Só jogadores escrevem"
    elif estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif estado["tinta_papel"] < CUSTO_ESCRITA:
        motivo = "Tinta e Papel insuficientes"
    elif estado["escribas"] >= estado["limite"]:
        motivo = "Sem escriba livre"
    else:
        motivo = None

    if motivo:
        await recusar(sid, motivo, pedido)       # só quem pediu recebe
        return

    estado["tinta_papel"] -= CUSTO_ESCRITA
    estado["escribas"] += 1
    estado["escrevendo"] += 1
    nome = jogadores[sid]["nome"]
    await sio.emit("escrita.iniciada", fato(pedido, por=nome))
    sio.start_background_task(obra_escrita, nome)


async def obra_escrita(nome):
    """Temporizador: a escrita termina sozinha, sem ninguém clicar."""
    await sio.sleep(TEMPO_ESCRITA)
    if estado["fase"] != "aberta":
        return
    estado["escribas"] -= 1
    estado["escrevendo"] -= 1
    estado["manuscritos"] += 1
    await sio.emit("escrita.concluida",
                   fato("escrita.iniciada (temporizador)", por=nome))


# ---------------------------------------------------------------------
#  Bancada de encadernação: manuscrito + cor -> livro na estante
# ---------------------------------------------------------------------
@sio.on("encadernacao.solicitada")
async def encadernar(sid, dados=None):
    pedido = "encadernacao.solicitada"
    cor = (dados or {}).get("cor")
    # A estante conta também os livros que ainda estão sendo encadernados:
    # a vaga é RESERVADA ao iniciar, senão dois pedidos estourariam a estante.
    if jogadores[sid]["papel"] != "jogador":
        motivo = "Só jogadores encadernam"
    elif estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif cor not in CORES:
        motivo = "Escolha uma cor de encadernação"
    elif estado["manuscritos"] < 1:
        motivo = "Sem manuscrito para encadernar"
    elif estado["escribas"] >= estado["limite"]:
        motivo = "Sem escriba livre"
    elif len(estado["estante"]) + estado["encadernando"] >= CAPACIDADE_ESTANTE:
        motivo = "Estante cheia"
    else:
        motivo = None

    if motivo:
        await recusar(sid, motivo, pedido)
        return

    estado["manuscritos"] -= 1
    estado["escribas"] += 1
    estado["encadernando"] += 1
    nome = jogadores[sid]["nome"]
    await sio.emit("encadernacao.iniciada", fato(pedido, por=nome, cor=cor))
    sio.start_background_task(obra_encadernacao, nome, cor)


async def obra_encadernacao(nome, cor):
    await sio.sleep(TEMPO_ENCADERNACAO)
    if estado["fase"] != "aberta":
        return
    estado["escribas"] -= 1
    estado["encadernando"] -= 1
    estado["estante"].append(cor)             # o livro vai para a estante
    await sio.emit("encadernacao.concluida",
                   fato("encadernacao.iniciada (temporizador)", por=nome, cor=cor))


# ---------------------------------------------------------------------
#  Passagem do tempo: produção e encomendas
# ---------------------------------------------------------------------
async def producao():
    while estado["fase"] == "aberta":
        await sio.sleep(INTERVALO)
        if estado["fase"] != "aberta":
            break
        estado["tinta_papel"] += estado["producao"]
        await sio.emit("recurso.produzido", fato("temporizador"))


async def gerador_encomendas():
    """Temporizador que faz chegar encomendas de livros com prazo."""
    while estado["fase"] == "aberta":
        if len(estado["encomendas"]) < MAX_ENCOMENDAS:
            enc = {
                "id": next(ids_encomenda),
                "cor": random.choice(CORES),
                "valor": VALOR_ENCOMENDA,
                "prazo": PRAZO_ENCOMENDA,
                "expira_em": time.time() + PRAZO_ENCOMENDA,
            }
            estado["encomendas"].append(enc)
            await sio.emit("encomenda.criada",
                           fato("temporizador", encomenda_id=enc["id"], cor=enc["cor"]))
            sio.start_background_task(prazo_encomenda, enc["id"])
        await sio.sleep(INTERVALO_ENCOMENDA)


async def prazo_encomenda(id_enc):
    """Temporizador do prazo: se ninguém entregou a tempo, a encomenda expira."""
    await sio.sleep(PRAZO_ENCOMENDA)
    if estado["fase"] != "aberta":
        return
    enc = achar_encomenda(id_enc)
    if enc is None:                # já foi entregue: não há o que expirar
        return
    estado["encomendas"].remove(enc)
    estado["expiradas"] += 1
    await sio.emit("encomenda.expirada",
                   fato("encomenda.criada (temporizador)",
                        encomenda_id=id_enc, cor=enc["cor"]))


# ---------------------------------------------------------------------
#  Entrega: livro da estante -> encomenda -> ouro
# ---------------------------------------------------------------------
@sio.on("entrega.solicitada")
async def entregar(sid, dados=None):
    pedido = "entrega.solicitada"
    enc = achar_encomenda((dados or {}).get("encomenda"))
    if jogadores[sid]["papel"] != "jogador":
        motivo = "Só jogadores entregam"
    elif estado["fase"] != "aberta":
        motivo = "A temporada não está aberta"
    elif enc is None:
        # inclui a DISPUTA: se outro jogador entregou antes, ela não existe mais
        motivo = "Encomenda já entregue ou expirada"
    elif enc["cor"] not in estado["estante"]:
        motivo = "Sem livro " + enc["cor"] + " na estante"
    else:
        motivo = None

    if motivo:
        await recusar(sid, motivo, pedido)
        return

    restante = enc["expira_em"] - time.time()
    bonus = BONUS_RAPIDA if restante > enc["prazo"] / 2 else 0
    ganho = enc["valor"] + bonus
    estado["estante"].remove(enc["cor"])      # remove UM livro dessa cor
    estado["encomendas"].remove(enc)
    estado["ouro"] += ganho
    estado["entregues"] += 1
    nome = jogadores[sid]["nome"]
    await sio.emit("entrega.concluida",
                   fato(pedido, por=nome, cor=enc["cor"], encomenda_id=enc["id"],
                        ganho=ganho, bonus=bonus))
