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

> Trabalho em andamento. As demais seções serão preenchidas ao longo das etapas.
