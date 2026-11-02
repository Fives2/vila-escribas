# Especificação — Vila dos Escribas

**Integrante(s):** Rafael Schwambach — @Fives2
**Tipo de vila (sorteio):** Escribas

> Documento escrito ANTES do código. Descreve o comportamento na linguagem da vila.

## 1. Regras da vila

- **Recurso:** *Tinta e Papel*, contado como **um único** recurso. É produzido
  sozinho no depósito, no canto superior esquerdo da vila.
- **Produto:** *livros*. Um livro nasce como *manuscrito* (escrito no Scriptorium)
  e vira livro ao ser *encadernado* na Bancada, numa cor à escolha do jogador
  (vermelho, azul, verde ou preto).
- **Estruturas (já existem na vila; não são construídas):**
  - **Scriptorium:** escreve um manuscrito.
  - **Bancada de encadernação:** transforma um manuscrito em livro colorido.
  - **Estante:** guarda os livros encadernados.
- **Escribas (trabalhadores):** no máximo **4** trabalhando ao mesmo tempo, somando
  Scriptorium e Bancada. Cada escrita ou encadernação ocupa 1 escriba até terminar.
- **Escrever:** custa **30** Tinta e Papel, dura **6 s** e gera **1** manuscrito.
- **Encadernar:** consome **1** manuscrito, dura **5 s** e gera **1** livro da cor escolhida.
- **Estante:** guarda no máximo **6** livros. Livros ainda em encadernação já ocupam vaga.
- **Produção automática:** **+10** Tinta e Papel a cada **5 s**, enquanto a temporada está aberta.
  Estoque inicial: 100.
- **Encomendas:** a cada **25 s** chega uma encomenda de um livro de uma cor sorteada
  (no máximo 3 abertas). Cada uma tem **prazo de 45 s**.
- **Entrega:** entregar o livro da cor pedida, antes do prazo, retira o livro da estante
  e dá **60 ouro**. Se for entregue na primeira metade do prazo, ganha **+20 ouro** de bônus.
- **Prazo estourado:** a encomenda é perdida (o ouro já ganho não diminui).
- **Ouro:** é a pontuação da vila, compartilhada por todos os jogadores.
- **Papéis:** o **Mestre** abre e encerra a temporada; o **Jogador** escreve, encaderna e entrega.
- **Temporada:** só com a temporada aberta as ações são aceitas. Depois de encerrada,
  tudo é recusado e os temporizadores param.

## 2. Eventos

Padrão: `objeto.acao_no_passado` para o que o servidor confirma e
`objeto.acao_solicitada` para o que o cliente pede.

| Evento | Emite | Recebe | O que muda no estado |
|---|---|---|---|
| `estado.sincronizado` | Servidor | Só quem conectou | Nada (entrega o estado atual) |
| `vila.abertura_solicitada` | Mestre | Servidor | (é um pedido; nada muda) |
| `vila.iniciada` | Servidor | Todos | A temporada passa a *aberta*; produção e encomendas começam |
| `escrita.solicitada` | Jogador | Servidor | (é um pedido; nada muda) |
| `escrita.iniciada` | Servidor | Todos | −30 Tinta e Papel; +1 escriba ocupado; +1 escrita em andamento |
| `escrita.concluida` | Servidor | Todos | −1 escriba ocupado; +1 manuscrito (causa: temporizador) |
| `encadernacao.solicitada` | Jogador | Servidor | (é um pedido; nada muda) |
| `encadernacao.iniciada` | Servidor | Todos | −1 manuscrito; +1 escriba ocupado; vaga na estante reservada |
| `encadernacao.concluida` | Servidor | Todos | −1 escriba ocupado; +1 livro da cor escolhida na estante (causa: temporizador) |
| `recurso.produzido` | Servidor | Todos | +10 Tinta e Papel (causa: temporizador) |
| `encomenda.criada` | Servidor | Todos | Nova encomenda (cor, prazo, valor) na lista (causa: temporizador) |
| `encomenda.expirada` | Servidor | Todos | A encomenda sai da lista; +1 perdida (causa: temporizador) |
| `entrega.solicitada` | Jogador | Servidor | (é um pedido; nada muda) |
| `entrega.concluida` | Servidor | Todos | −1 livro da cor na estante; a encomenda sai da lista; +ouro |
| `operacao.recusada` | Servidor | Só quem pediu | Nada (só informa o motivo) |
| `vila.encerramento_solicitado` | Mestre | Servidor | (é um pedido; nada muda) |
| `vila.encerrada` | Servidor | Todos | A temporada passa a *encerrada*; novas ações são recusadas |

**Motivos de recusa:** temporada não está aberta · só o Mestre abre/encerra · só jogadores
escrevem, encadernam e entregam · Tinta e Papel insuficientes · sem escriba livre · sem manuscrito ·
cor inválida · estante cheia · sem livro da cor pedida · encomenda já entregue ou expirada.

## 3. Cenários de teste (Dado / Quando / Então, escritos com eventos)

### Recusa
Dado que a temporada está aberta e os 4 escribas estão ocupados, quando o Jogador A emite
`escrita.solicitada`, então o servidor emite `operacao.recusada` ("Sem escriba livre")
apenas para A, e nenhum outro jogador recebe nada.

### Passagem do tempo
Dado que a temporada está aberta, quando passam 5 s, então o servidor emite
`recurso.produzido` para todos, com causa "temporizador". Dado que uma escrita foi iniciada
(`escrita.iniciada`), quando passam 6 s, então o servidor emite `escrita.concluida` para todos,
com causa "escrita.iniciada (temporizador)", e o escriba fica livre.

### Disputa entre dois jogadores
Dado que há uma encomenda de livro azul aberta e apenas 1 livro azul na estante, quando os
jogadores A e B emitem `entrega.solicitada` para essa encomenda ao mesmo tempo, então o
servidor emite `entrega.concluida` para todos (por um deles) e `operacao.recusada`
("Encomenda já entregue ou expirada") apenas para o outro.

## 4. Extras

- Encomendas com **prazo limite** e cor sorteada.
- **Cor da encadernação** escolhida pelo jogador, que precisa combinar com a encomenda.
- **Bônus de rapidez** na entrega.
