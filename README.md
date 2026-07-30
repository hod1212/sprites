# 🗡️ RO Sprite Forge

Ferramenta local que busca sprites de **Ragnarok Online** no
[Spriters Resource](https://www.spriters-resource.com/pc_computer/ragnarokonline/),
isola os quadros de animação e os **reimagina com IA (Google Gemini,
Image-to-Image)** em estilos como Dark Fantasy, Cyberpunk, Cel Shading e
outros — mantendo a pose, anatomia e silhueta do sprite original, mas gerando
um design inédito.

```
ETAPA 1 — criar o personagem
  Você digita: "Cavaleiro com lança" + estilo "Dark Fantasy"
       ↓  🔎 busca e baixa o spritesheet do Knight no Spriters Resource
       ↓  ✂️ remove o fundo (e fatia os quadros, se você quiser)
       ↓  ✨ o Gemini devolve UM personagem novo no estilo escolhido
       ↓
ETAPA 2 — animar o personagem
       ↓  🎭 você escolhe o movimento: ataque, defesa, avanço, caminhada...
       ↓  🎬 o Gemini gera as poses desse MESMO personagem
       ↓
⬇️ prévia em GIF + folha de sprites + PNGs individuais (prontos para o jogo)
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
├── requirements.txt      # Dependências Python
├── packages.txt          # Dependências de sistema (Chromium na nuvem)
├── instalar_e_abrir_WINDOWS.bat   # Instalador com 1 clique (Windows)
├── instalar_e_abrir_MAC.command   # Instalador com 1 clique (Mac)
├── .env.example          # Modelo do arquivo de configuração da chave de API
├── data/                 # (criada automaticamente) índice JSON + downloads
│   ├── sprite_index.json
│   └── downloads/
└── output/               # (criada automaticamente) sprites gerados
```

---

## 💻 Instalação fácil (para quem não programa)

Se você nunca usou terminal/linha de comando, use este caminho:

1. **Baixe o projeto**: no topo desta página do GitHub, clique no botão verde
   **"Code"** → **"Download ZIP"**. Extraia o arquivo `.zip` baixado em uma
   pasta do seu computador (ex.: Área de Trabalho).
2. **Instale o Python**, se ainda não tiver: acesse
   [python.org/downloads](https://www.python.org/downloads/) e instale a
   versão mais recente.
   - **Windows**: na tela do instalador, marque a caixinha **"Add Python to
     PATH"** antes de clicar em Instalar. Esse passo é essencial.
   - **Mac**: pode seguir o instalador normalmente, sem opções especiais.
3. **Abra a pasta** onde você extraiu o projeto e dê **dois cliques** no
   arquivo:
   - Windows: `instalar_e_abrir_WINDOWS.bat`
   - Mac: `instalar_e_abrir_MAC.command`
     *(No Mac, se aparecer um aviso de segurança na primeira vez, clique com o
     botão direito no arquivo → "Abrir" → confirme "Abrir".)*
4. Uma janela preta (terminal) vai abrir sozinha e preparar tudo — na
   primeira vez isso demora de 3 a 10 minutos, dependendo da internet. Não
   feche a janela, apenas aguarde.
5. Quando terminar, o aplicativo abre **automaticamente no seu navegador**.
   Pronto — é só usar.

Da próxima vez, para abrir o app de novo, basta dar dois cliques no mesmo
arquivo (`.bat` ou `.command`) — ele já estará instalado e abrirá em segundos.

> Falta a chave da API do Gemini? Veja a seção
> [🔑 Configurar a chave da API do Gemini](#-configurar-a-chave-da-api-do-gemini)
> mais abaixo — ou use o **motor Pollinations** dentro do app, que não exige
> chave nenhuma.

---

## 🚀 Instalação via terminal (para quem já tem experiência)

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
3. Decida entre a **imagem inteira** (recomendado) ou um **quadro específico**
   (o app fatia os quadros automaticamente e mostra um mapa numerado).
4. Selecione o **filtro de estilo** entre os 13 disponíveis (ou descreva o seu)
   e o **grau de alteração** de 1 a 10 (veja a seção abaixo).
5. Clique em **"✨ Transformar sprite com Gemini"** e compare o antes/depois.
6. Baixe o PNG final com fundo transparente — ou siga para a **Etapa 2** e crie
   as animações de movimento a partir dele.

---

## 🤖 Motores de IA: Gemini x Pollinations (grátis)

O app tem um seletor **"Motor de IA"** com duas opções:

| | ✨ Gemini (padrão) | 🆓 Pollinations.ai |
| --- | --- | --- |
| **Custo** | Grátis com **cota diária** (chave do aistudio.google.com, sem cartão) | Grátis, com ou sem chave |
| **Chave** | Obrigatória | **Opcional** |
| **Qualidade** | Melhor | Boa (modelo FLUX Kontext) |
| **Velocidade** | ~10-30 s | ~30-120 s (serviço comunitário, oscila) |
| **Confiabilidade** | Alta | Média — pode ficar fora do ar em picos |

> ⚠️ **Correção importante:** uma versão anterior deste README descrevia o
> Pollinations como "100% grátis, sem chave nenhuma" — isso estava impreciso.
> Segundo a
> [documentação oficial](https://github.com/pollinations/pollinations/blob/master/APIDOCS.md),
> o serviço tem três níveis: **anônimo** (sem chave, mas com marca d'água nas
> imagens e limite de ~1 geração a cada 15s — o parâmetro que remove a marca
> é documentado como *"needs account"*), **Seed** (chave gratuita via
> cadastro em `auth.pollinations.ai`, sem marca d'água e limite de ~1 a cada
> 5s) e **Flower/Nectar** (pago, para uso intenso). O app funciona sem
> nenhuma chave, mas agora deixa isso explícito e oferece um campo opcional
> para colar uma chave gratuita do Pollinations, se você tiver uma.

**Quando usar o Pollinations:** quando a cota diária gratuita do Gemini
acabar. Sem chave, funciona mas com marca d'água — para removê-la, crie uma
conta grátis em `auth.pollinations.ai` e cole a chave no campo que aparece
ao selecionar este motor no app. Se uma geração falhar por sobrecarga, espere
1-2 minutos e tente de novo — ou volte ao Gemini.

**Privacidade no modo Pollinations:** para o serviço enxergar seu sprite, o
app o envia temporariamente ao hospedeiro **tmpfiles.org** (o arquivo é
apagado automaticamente em ~60 minutos) e ao **Pollinations.ai**. O app avisa
isso na tela. Se preferir que a imagem não saia do circuito Google, use o
Gemini.

> Por que não outras IAs? O pipeline depende de *edição de imagem guiada por
> instruções* ("mantenha a pose, troque a armadura"). O img2img clássico do
> Stable Diffusion não obedece esse tipo de regra — ele repinta a imagem toda.
> Os modelos gratuitos que obedecem são raros; o FLUX Kontext (via
> Pollinations) é o melhor deles hoje.

---

## 🎚️ Grau de alteração (1 a 10)

Antes de gerar, você define **quanto** o sprite deve ser alterado. Isso dá
controle real sobre o resultado, em vez de aceitar o que a IA decidir:

| Grau | Nome | O que acontece |
| :--: | --- | --- |
| 1 | Praticamente idêntico | Só um leve tratamento de cor. O sprite continua o mesmo. |
| 2 | Retoque leve | Mesmo personagem, com acabamento e sombreamento melhores. |
| 3 | Ajuste sutil | Mesmas peças de equipamento, cores puxadas para o estilo. |
| 4 | Reestilização branda | Mesmo equipamento, materiais e ornamentos repaginados. |
| 5 | Equilibrado | Silhueta e tipo de equipamento preservados, visual novo. |
| 6 | Reimaginação moderada | Mesma classe e silhueta, roupas e cores redesenhadas. |
| 7 | Reimaginação forte | Só pose e proporções se mantêm; o resto é novo. *(padrão)* |
| 8 | Personagem novo | Outro personagem, na mesma pose e silhueta. |
| 9 | Reinvenção | Design totalmente novo; a pose serve só de esqueleto. |
| 10 | Completamente diferente | Personagem inédito; mantém apenas a postura corporal. |

**Como funciona por dentro:** cada grau tem a sua **própria instrução** enviada
ao modelo (você pode lê-la no app, em *"Ver a regra exata enviada à IA"*), e a
temperatura acompanha em segundo plano (0,15 no grau 1 até 1,15 no grau 10).
Mexer só na temperatura não resolveria — ela controla a aleatoriedade, não o
quanto o desenho muda; é a instrução que faz esse trabalho.

> ⚖️ Nos graus **1 e 2** o resultado fica muito próximo do sprite original da
> Gravity. É útil para testar um estilo, mas o app exibe um aviso: evite uso
> comercial nesses graus.

---

## 🎬 Etapa 2 — Animações de movimento (para usar em jogo)

Um sprite parado não serve para animar um personagem num jogo. O fluxo é em
**duas etapas**, e essa separação é o que faz a animação funcionar:

```
ETAPA 1 ─ folha com várias poses ──► Gemini ──► UM personagem novo
                                                      │
ETAPA 2 ─ esse personagem + "ataque" ──► Gemini ──► tira com N poses dele
                                                      │
                                          GIF + folha de sprites + PNGs
```

### Por que duas etapas (e não tudo de uma vez)

A primeira tentativa foi transformar cada quadro do sprite original
separadamente, usando o personagem já estilizado como referência de identidade
e o quadro original como referência de pose. **Não funcionou:** com duas
imagens de estilos diferentes na mesma chamada, o modelo mistura as duas e o
personagem muda de um quadro para o outro.

A abordagem atual elimina a causa: na Etapa 2 o personagem gerado é a **única**
imagem enviada, e a pose vem de **texto**. Não há um segundo estilo competindo.

**A Etapa 2 trabalha sempre com fidelidade máxima** (não há grau de alteração
aqui — quem define o visual é a Etapa 1). Para segurar o desenho no lugar:

- a instrução trata a imagem como uma **folha de modelo** e enumera item por
  item o que deve ser copiado (cor exata de cada peça, formato do capacete,
  tipo e cor da arma, acessórios, paleta, tom de pele, proporções);
- inclui uma lista explícita de **proibições** (trocar a arma, mudar cores,
  acrescentar ou remover elementos, alterar proporções ou estilo);
- a temperatura cai para **0,12** — o mínimo prático, já que aqui não queremos
  criatividade nenhuma;
- a **imagem é enviada antes do texto**, o que ancora melhor a geração na
  referência visual.

Além disso, o método recomendado gera **todos os quadros em uma única chamada**,
como uma tira horizontal que o app depois fatia. Uma geração única não tem como
divergir de si mesma — é a forma mais confiável de manter a consistência.

### Como usar

1. Faça a Etapa 1 e gere o personagem (ou pule direto para a Etapa 2 e envie um
   sprite pronto).
2. Na Etapa 2, escolha um dos **16 movimentos clássicos de jogos 2D** — ou
   descreva um movimento próprio:

   | Locomoção | Combate | Reação |
   | --- | --- | --- |
   | 🧍 Parado (idle) | ⚔️ Ataque de corte (arma branca) | 💥 Recebendo dano |
   | 🚶 Andar | 🗡️ Estocada (lança/adaga) | ☠️ Queda / morte |
   | 🏃 Correr | 👊 Ataque desarmado (soco/chute) | 🏆 Vitória / comemoração |
   | 🦘 Pular | 🔫 Tiro (arma de fogo) | |
   | 💨 Investida / dash | 🏹 Disparo de arco | |
   | 🤸 Esquiva / rolamento | ✨ Conjurar magia | |
   | | 🛡️ Defesa / bloqueio | |

   **Escolha o ataque compatível com a arma do personagem** — um soldado com
   rifle usa "Tiro (arma de fogo)", um cavaleiro com espada usa "Ataque de
   corte". Cada movimento tem uma coreografia profissional quadro a quadro
   (visível no app), e o número de quadros recomendado é sugerido
   automaticamente. Duas regras extras seguram o movimento no lugar: os
   quadros são tratados como fotogramas consecutivos de um único movimento
   fluido, e a ação é sempre executada com a arma que o personagem já possui
   (nunca trocada).
3. Escolha a quantidade de quadros (2 a 8) e o método:
   - **🧷 Tira única** — 1 chamada à API, mais consistente (**recomendado**);
   - **🔢 Quadro a quadro** — N chamadas, mais controle sobre cada pose, útil
     se a tira sair com os quadros mal separados.
4. Clique em **"🎬 Gerar animação"**, confira a **prévia em GIF** e baixe.

### O que você baixa

Um `.zip` contendo:

| Arquivo | Para que serve |
| --- | --- |
| `spritesheet.png` | Folha em grade uniforme — o app informa o **tamanho exato da célula** para importar em Unity, Godot ou GameMaker. |
| `quadros/frame_XX.png` | Cada pose em PNG separado, fundo transparente. |
| `previa.gif` | O movimento animado, para conferir o resultado. |
| `LEIA-ME.txt` | Movimento, número de quadros e tamanho da célula. |

Os quadros são alinhados **pelos pés** (ancoragem inferior), o que evita o
personagem "pular" durante a animação.

### Dicas práticas

- **Gere uma animação por ação**, sempre a partir do **mesmo** personagem da
  Etapa 1 — assim ataque, defesa e caminhada ficam consistentes entre si.
- **Comece com 4 quadros.** Muitos quadros numa tira só deixam cada um pequeno
  e com menos detalhe; se precisar de mais fluidez, use o modo quadro a quadro.
- Se a tira vier com quadros colados, o app divide a largura em partes iguais
  automaticamente — mas vale tentar de novo ou reduzir o número de quadros.

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
