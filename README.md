# 🗡️ RO Sprite Forge

Ferramenta local que busca sprites de **Ragnarok Online** no
[Spriters Resource](https://www.spriters-resource.com/pc_computer/ragnarokonline/),
isola os quadros de animação e os **reimagina com IA (Google Gemini,
Image-to-Image)** em estilos como Dark Fantasy, Cyberpunk, Cel Shading e
outros — mantendo a pose, anatomia e silhueta do sprite original, mas gerando
um design inédito.

```
Você digita: "Preciso de um Cavaleiro com lança" + estilo "Dark Fantasy"
       ↓
🔎 Busca e baixa o spritesheet do Knight no Spriters Resource
       ↓
✂️ Remove o fundo e fatia os quadros de animação (você escolhe qual usar)
       ↓
✨ Gemini gera um novo sprite no estilo escolhido (mesma pose, visual novo)
       ↓
⬇️ Comparação lado a lado + download do PNG com fundo transparente
```

---

## 📁 Estrutura do projeto

```
sprites/
├── app.py                # Módulo D — Interface (Streamlit): conecta tudo
├── scraper.py            # Módulo A — Scraping + indexador local do Spriters Resource
├── sprite_tools.py       # Módulo B — Remoção de fundo e fatiamento de quadros
├── gemini_transform.py   # Módulo C — Pipeline Img2Img com a API do Gemini
├── keywords.py           # Dicionário PT-BR → EN (ex.: "Algoz" → "Assassin Cross")
├── requirements.txt      # Dependências
├── .env.example          # Modelo do arquivo de configuração da chave de API
├── data/                 # (criada automaticamente) índice JSON + downloads
│   ├── sprite_index.json
│   └── downloads/
└── output/               # (criada automaticamente) sprites gerados
```

---

## 🚀 Instalação (passo a passo)

Pré-requisito: **Python 3.10 ou superior** ([download](https://www.python.org/downloads/) —
no Windows, marque a opção *"Add Python to PATH"* durante a instalação).

Abra o terminal (no Windows: `cmd` ou PowerShell) dentro da pasta do projeto e rode:

```bash
# 1. Criar um ambiente isolado (recomendado)
python -m venv .venv

# 2. Ativar o ambiente
#    Windows:
.venv\Scripts\activate
#    Mac/Linux:
source .venv/bin/activate

# 3. Instalar as dependências
pip install -r requirements.txt

# 4. Instalar o navegador usado pelo scraper (necessário 1 única vez)
playwright install chromium
```

> **Por que o Playwright?** O Spriters Resource fica atrás da proteção
> Cloudflare, que bloqueia robôs simples. O Playwright abre um navegador
> Chromium real (invisível) que passa pela verificação como um visitante
> normal. Sem ele, a busca automática pode falhar — mas o app ainda funciona
> pela aba **"Enviar meu próprio sprite"**.

---

## 🔑 Configurar a chave da API do Gemini

1. Acesse **https://aistudio.google.com/apikey** (login com conta Google).
2. Clique em **"Create API key"** e copie a chave (há uma cota gratuita).
3. Na pasta do projeto, copie o arquivo `.env.example` para `.env`:

   ```bash
   # Windows
   copy .env.example .env
   # Mac/Linux
   cp .env.example .env
   ```

4. Abra o `.env` em qualquer editor de texto e cole a sua chave:

   ```
   GEMINI_API_KEY=AIzaSy...sua-chave-aqui
   ```

Alternativa: deixe o `.env` vazio e cole a chave direto na barra lateral do
aplicativo (campo "Chave da API Gemini").

---

## ▶️ Rodar o aplicativo

```bash
streamlit run app.py
```

O navegador abre automaticamente em `http://localhost:8501`. Fluxo de uso:

1. **Busque** o personagem (português ou inglês): "Cavaleiro", "Algoz",
   "Priest", "Poring"...
2. **Escolha** o spritesheet entre os resultados (link para a página original
   incluso).
3. Decida entre o **sheet inteiro** ou um **quadro específico** (o app fatia
   os quadros automaticamente).
4. Selecione o **filtro de estilo** na barra lateral (ou descreva o seu) e o
   **nível de variação**.
5. Clique em **"✨ Transformar sprite com Gemini"** e compare o antes/depois.
6. Baixe o PNG final com fundo transparente.

---

## 🎬 Modo animação (vários quadros para usar em jogo)

Um sprite só não serve para animar um personagem em um jogo — você precisa do
ciclo de movimento inteiro. O modo animação resolve isso:

1. Envie (ou busque) um spritesheet com várias poses.
2. Escolha **"🎬 Animação — vários quadros (para usar em jogo)"**.
3. O app fatia a folha e mostra um **mapa numerado** dos quadros.
4. Selecione o intervalo de quadros de um mesmo movimento (ex.: o ciclo de
   caminhada em uma direção) e qual quadro define o design do personagem.
5. Clique em **"🎬 Gerar animação"** e acompanhe a barra de progresso.

### Como a consistência do personagem é garantida

Este é o ponto crítico: se cada quadro fosse gerado isoladamente, sairia um
personagem diferente em cada um e a animação ficaria inútil. A solução:

- O **primeiro quadro** é transformado normalmente e define o design
  (armadura, cores, arma, cabelo).
- Cada quadro seguinte é gerado com **duas imagens** enviadas juntas: o
  personagem já estilizado (referência de *identidade*) + o quadro original
  (referência de *pose*), com instrução explícita para copiar o design da
  primeira e apenas a pose da segunda.
- Nesses quadros a temperatura do modelo cai para `0.25` — queremos
  fidelidade ao personagem, não criatividade.

### O que você baixa

Um `.zip` contendo:

| Arquivo | Para que serve |
| --- | --- |
| `spritesheet_grade.png` | Folha em **grade uniforme** — o app informa o tamanho exato da célula para você importar em Unity, Godot ou GameMaker. |
| `spritesheet_layout_original.png` | Folha com o **mesmo layout do arquivo enviado**, para substituição direta. |
| `quadros/frame_XX.png` | Cada pose em PNG separado, fundo transparente. |
| `LEIA-ME.txt` | Estilo usado, número de quadros e tamanho da célula. |

Os quadros são alinhados **pelos pés** (ancoragem inferior), o que evita o
personagem "pular" entre os quadros durante a animação.

### Avisos práticos

- **Cada quadro é uma chamada à API.** 6 quadros ≈ 6 chamadas (≈1 minuto). O
  app avisa o custo estimado antes de começar e limita a 24 quadros por vez.
- **Se um quadro falhar** (cota, filtro de segurança), os outros continuam: o
  app mostra quais falharam e você ainda baixa os que deram certo.
- **Dica de qualidade:** selecione quadros de um único movimento e uma única
  direção por vez. Misturar direções na mesma geração piora a consistência.

---

### Uso pelo terminal (opcional, sem interface)

```bash
# Buscar e baixar um sheet
python scraper.py "Cavaleiro"

# Transformar um PNG qualquer
python gemini_transform.py data/downloads/arquivo.png "Sci-Fi / Cyberpunk"
```

---

## 📱 Rodando no celular (Android/iPhone)

O aplicativo é uma página web — então no celular ele roda pelo **navegador**,
sem instalar nada. Duas formas:

### Opção 1 — Publicar na nuvem (recomendada, grátis)

O repositório já vem preparado para o [Streamlit Community Cloud](https://share.streamlit.io):

1. Acesse **https://share.streamlit.io** e faça login com a sua conta do GitHub.
2. Clique em **"Create app"** → **"Deploy a public app from GitHub"**.
3. Selecione o repositório **`hod1212/sprites`**, branch
   `claude/ragnarok-sprite-generator-5cgyoa` (ou `main`, se já tiver feito o
   merge) e o arquivo **`app.py`** → **Deploy**.
4. Em ~3 minutos você recebe uma URL pública (ex.:
   `https://seuapp.streamlit.app`). Abra-a no navegador do celular e, no menu
   do Chrome, use **"Adicionar à tela inicial"** — vira um ícone como o de um
   app nativo.

Observações importantes:

- **A chave da API precisa ser informada no app.** O arquivo `.env` não vai
  para o GitHub (está no `.gitignore`, por segurança), então na nuvem existem
  duas formas:
  - **Recomendado:** cole a chave no campo que aparece no topo da página (ou
    no menu **☰ → Configurações**). Ela vale só para a sua sessão do navegador
    e não é salva em lugar nenhum.
  - **Alternativa (só se o app for privado/seu):** no painel do Streamlit
    Cloud, vá em **Settings → Secrets** e adicione a linha
    `GEMINI_API_KEY = "sua-chave-aqui"`. ⚠️ Atenção: com o app público,
    qualquer pessoa com a URL passa a gastar a sua cota.
- A busca automática no Spriters Resource pode falhar na nuvem, pois o
  Cloudflare costuma bloquear IPs de datacenter mesmo com navegador real.
  Nesse caso use a aba **"Enviar meu próprio sprite"** — baixe o PNG pelo
  navegador do celular e envie; todo o resto (fatiamento + Gemini) funciona
  normalmente.

### Opção 2 — Servir do seu PC para o celular (mesma rede Wi-Fi)

No PC, rode:

```bash
streamlit run app.py --server.address 0.0.0.0
```

Descubra o IP do PC (`ipconfig` no Windows, campo "Endereço IPv4", ex.:
`192.168.0.15`) e abra no navegador do celular:
`http://192.168.0.15:8501`. Aqui a busca automática funciona 100%, pois usa a
sua internet residencial.

---

## 🧠 Decisões de arquitetura (resumo para não-programadores)

| Escolha | Por quê |
| --- | --- |
| **Python + Streamlit** | Interface web pronta com pouquíssimo código; roda local com um comando e não exige saber HTML/JS. |
| **Índice local em JSON** | O site é mapeado **uma única vez**; buscas seguintes são instantâneas e não sobrecarregam o Spriters Resource (scraping educado). |
| **Playwright em vez de só `requests`** | O Cloudflare do site bloqueia clientes HTTP simples (erro 403). Um navegador real resolve o desafio automaticamente. |
| **Aba de upload manual** | Plano B garantido: se o site mudar ou bloquear, você baixa o PNG manualmente no navegador e o resto do fluxo continua funcionando. |
| **Modelo `gemini-2.5-flash-image`** | É o modelo do Gemini especializado em geração/edição de imagem (Img2Img) via prompt multimodal (imagem + texto). |
| **Fundo branco antes da IA + remoção depois** | Modelos de imagem trabalham mal com transparência; enviamos fundo branco sólido e recuperamos o alpha no final. |
| **`temperature` mínima de 0.55** | Impede que o modelo "copie" o sprite: o resultado é sempre uma reinterpretação, nunca um clone. |
| **Imagem de referência no modo animação** | Enviar o personagem já estilizado junto com o quadro original é o que mantém o mesmo personagem em todos os quadros — sem isso, cada quadro viraria um personagem diferente. |
| **Mapa numerado em vez de miniaturas** | Em telas estreitas as miniaturas em colunas empilham e ficam gigantes; uma imagem única com os quadros numerados é legível no celular. |

## ⚖️ Aviso legal

Os sprites originais de Ragnarok Online são propriedade da **Gravity Co., Ltd.**
e os rips do Spriters Resource são disponibilizados para fins de estudo. Use
esta ferramenta para **estudo, prototipagem e inspiração**. Mesmo com a
geração de designs inéditos, evite uso comercial de resultados claramente
derivados de propriedade intelectual alheia sem orientação jurídica.

## 🛠️ Problemas comuns

| Sintoma | Solução |
| --- | --- |
| `403` / "Não consegui acessar o Spriters Resource" | Rode `playwright install chromium`; se persistir, use a aba de upload manual. |
| "Chave da API não encontrada" | Confira o arquivo `.env` (sem espaços em volta do `=`) ou cole a chave na barra lateral. |
| "O modelo respondeu sem imagem" | Filtro de segurança do Google; tente outro quadro, outro estilo ou reduza instruções extras. |
| Resultado muito parecido com o original | Aumente o "Nível de variação" na barra lateral. |
| Resultado com pose diferente | Diminua o "Nível de variação" e use um quadro isolado em vez do sheet inteiro. |
