# Vila dos Escribas

Vila cooperativa em tempo real, orientada a eventos. Os jogadores transformam
**Tinta e Papel** em **livros** (escrevem no Scriptorium, encadernam na Bancada,
guardam na Estante) e os **entregam** em encomendas com prazo para ganhar **ouro**.

## Integrantes
- Rafael Schwambach — @Fives2 (https://github.com/Fives2)

## Como instalar e executar
1. Instale Python 3 e Git.
2. Dentro da pasta do repositório:
   ```
   python -m venv .venv
   .venv\Scripts\activate          # Windows
   source .venv/bin/activate       # Linux ou macOS
   pip install -r requirements.txt
   uvicorn server:app --reload
   ```
3. Abra **http://localhost:8000** (não abra o arquivo direto, com `file://`).

Linguagem e bibliotecas: Python (python-socketio, uvicorn) no servidor;
JavaScript (Vue 3, Phaser 3 e Socket.IO, por CDN) no navegador.

## Como testar com duas (ou três) abas
1. Aba 1: digite um nome e entre como **Mestre**.
2. Abas 2 e 3: entre como **Jogador A** e **Jogador B**.
3. Jogador clica em **Escrever** antes do Mestre abrir: aparece "A temporada não está aberta" só nessa aba (recusa).
4. Mestre clica em **Abrir temporada**: as três abas mostram a temporada aberta, sem recarregar.
5. Jogador A: **Escrever** → barra no Scriptorium → após 6 s vira manuscrito. Depois escolha uma cor e **Encadernar** → após 5 s o livro aparece na Estante, nas três abas.
6. Veja a Tinta e Papel subir sozinha a cada 5 s e as encomendas chegarem com contagem de prazo.
7. **Disputa:** com 1 livro azul na estante e uma encomenda azul aberta, clique em **Entregar** nas abas A e B quase ao mesmo tempo: só um ganha o ouro, o outro recebe a recusa.
8. Mestre clica em **Encerrar temporada**: a vila escurece e qualquer ação é recusada.

A especificação completa (regras, eventos e cenários) está em `docs/especificacao.md`.

## Perguntas

### 1. Quais eventos o seu sistema emite e escuta?
**O cliente emite (pedidos):** `vila.abertura_solicitada`, `vila.encerramento_solicitado`
(só o Mestre), `escrita.solicitada`, `encadernacao.solicitada` e `entrega.solicitada`.

**O servidor escuta** esses cinco pedidos (mais a conexão e a desconexão) e **emite os fatos**:
`estado.sincronizado` (só para quem conectou), `vila.iniciada`, `escrita.iniciada`,
`escrita.concluida`, `encadernacao.iniciada`, `encadernacao.concluida`, `recurso.produzido`,
`encomenda.criada`, `encomenda.expirada`, `entrega.concluida`, `vila.encerrada` (para todos) e
`operacao.recusada` (só para quem pediu).

**O cliente escuta** todos esses fatos, cada um com uma reação na tela e na vila desenhada.
Cinco desses fatos (`escrita.concluida`, `encadernacao.concluida`, `recurso.produzido`,
`encomenda.criada` e `encomenda.expirada`) nascem de **temporizadores do servidor**,
sem que ninguém clique.

### 2. Como o sistema sabe quando deve atualizar os outros jogadores?
O sistema não "pergunta" nada: ele **reage a eventos**. O cliente só **pede** (por exemplo,
`escrita.solicitada`) e não muda nada sozinho. O servidor valida e altera o estado e, se deu certo,
**emite um fato para todos** (`sio.emit` sem destinatário, como `escrita.iniciada`). Cada fato
leva o estado completo e a causa. Todo cliente conectado, ao receber o fato (`socket.on`), copia o estado e redesenha, então
todos ficam iguais. Quando o pedido é inválido, o servidor emite `operacao.recusada` só para
quem pediu (`to=sid`). Quem entra depois recebe `estado.sincronizado` e já vê a vila no ponto atual.

### 3. Que parte do código mostra claramente o uso do paradigma orientado a eventos?
- Em `server.py`, os tratadores `@sio.on("escrita.solicitada")`, `@sio.on("encadernacao.solicitada")`
  e `@sio.on("entrega.solicitada")`: cada função só roda quando o evento chega.
- Ainda em `server.py`, `obra_escrita`, `obra_encadernacao`, `producao`, `gerador_encomendas` e
  `prazo_encomenda`: ficam dormindo (`sio.sleep`) e depois emitem um evento (`escrita.concluida`,
  `recurso.produzido`, `encomenda.expirada` e outros) **sem nenhum pedido**. Isso é causa por tempo,
  não consulta repetida ao servidor.
- Em `client/index.html`, as funções `ouvir(...)` (agrupadas em `entrar()`) e `pedir(...)`:
  cada `ouvir` é um `on` com a reação do cliente, e cada `pedir` é um `emit`.
- O **painel de eventos** da tela mostra cada `emit` e `on`, a causa e a reação,
  e os contadores por evento.

## Uso de IA
Utilizei o **Claude (Anthropic)** como apoio. Ele ajudou a planejar o trabalho a partir das
instruções, a adaptar o Kit Inicial para o tema Escribas, a escrever o servidor, a tela, os
sprites das estruturas, a especificação e este README. Eu revisei o código, executei o jogo com
várias abas, testei os cenários da especificação (recusa, passagem do tempo e disputa) e fiz os
commits por etapa.

O que mudou em relação ao kit: o recurso único Tinta e Papel; estruturas fixas no mapa
(Scriptorium, Bancada, Estante e Depósito) em vez de obras que nascem; os eventos de escrita,
encadernação, encomenda e entrega; o bloco do Phaser, adaptado para desenhar as estruturas e a
estante; e a correção da cor de "pedido" no painel (o padrão não reconhecia `.solicitada`).

## Extras
- Encomendas com **prazo limite** e cor sorteada (`encomenda.criada` e `encomenda.expirada`).
- **Cor da encadernação** escolhida pelo jogador, que precisa combinar com a encomenda.
- **Bônus de rapidez** de +20 ouro na entrega feita na primeira metade do prazo.
- Sprites das estruturas (Scriptorium, Bancada, Estante e Depósito) em pixel art criada para este trabalho.
- Contadores por evento no painel de eventos.

## Créditos
Tileset e mapa-base: Kit Inicial da disciplina. Sprites das estruturas: criados para este trabalho.
