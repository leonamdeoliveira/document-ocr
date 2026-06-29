---
name: document-ocr
description: Leitura de PDFs, imagens, DOCX, PPTX e HTML usando OCR via LM Studio ou extracao nativa de texto. Converte documentos para Markdown/HTML/JSON estruturado. Use quando o usuario pedir para "ler PDF", "extrair texto de imagem", "converter documento", "ler DOCX", "ler PPT", "ler HTML", "OCR" ou "transformar PDF em markdown".
---

# Document OCR - Pipeline de Leitura de Documentos

Converte PDFs e imagens em texto estruturado (Markdown/HTML/JSON) usando OCR multimodal via LM Studio local, consumido via API OpenAI-compatible.

## Quando Usar (Disparo Automatico)

Esta skill DEVE ser ativada automaticamente SEMPRE que:

- Usuario pede "leia este PDF", "leia esta imagem", "extraia o texto desse PDF", "converta PDF para markdown"
- Usuario menciona "ler" + "PDF", "ler" + "imagem", "ler" + "documento", "extrair texto", "OCR"
- Usuario **envia/cola/arrasta** um arquivo no chat com extensao `.pdf`, `.png`, `.jpg`, `.jpeg`, `.docx`, `.pptx`, `.html`, `.htm`
- Usuario pede "leia este DOCX", "leia este PowerPoint", "leia este HTML", "extraia texto do DOCX"
- Usuario quer OCR de documentos com preservacao de estrutura (tabelas, listas, titulos)
- Usuario menciona "Chandra OCR", "LM Studio", "OCR documento"

**Nao pergunte ao usuario se ele quer usar OCR. Simplesmente ative a skill e processe o arquivo.**

**Nota:** Para `.docx`, `.pptx` e `.html`, a extracao de texto e **nativa** (sem OCR), pois esses formatos ja possuem texto selecionavel. Para PDFs e imagens, usa OCR via LM Studio.

## Estrutura da Skill

```
SKILL_DIR/
├── SKILL.md                   # Este arquivo
├── main.py                    # CLI principal (ponto de entrada)
├── native_extractor.py        # Extracao nativa de DOCX, PPTX, HTML
├── ocr_pipeline.py            # Orquestracao do pipeline
├── pdf_utils.py               # Renderizacao e extracao de texto
├── lmstudio_client.py         # Cliente HTTP OpenAI-compatible
├── requirements.txt           # Dependencias
├── .env.example               # Template de configuracao
├── README.md                  # Documentacao
└── models/                    # Modelos de OCR
    ├── chandra-ocr-2/         # Chandra OCR 2 (retorna HTML)
    │   ├── config.json
    │   ├── prompts.py
    │   └── __init__.py
    ├── glm-ocr/               # GLM-OCR (retorna Markdown)
    │   ├── config.json
    │   ├── prompts.py
    │   └── __init__.py
    └── template/              # Template para novos modelos
        ├── config.json
        ├── prompts.py
        └── __init__.py
```

## Instalacao (para um usuario novo)

### 1. Instalar Python 3.11+

Verifique se tem Python instalado:

```bash
python --version
# Deve mostrar: Python 3.11.x ou superior
```

Se nao tiver, baixe em: https://www.python.org/downloads/

### 2. Instalar LM Studio e modelos de OCR

Baixe o LM Studio em: https://lmstudio.ai/

Apos instalar e abrir:
1. Vá na aba "Search" e busque pelo modelo desejado (ex: `chandra-ocr-2`, `glm-ocr`)
2. Baixe o modelo
3. Repita para cada modelo que quiser usar

**Importante:** O LM Studio carrega apenas **um modelo por vez** no servidor. Para alternar entre modelos:

- Abra o LM Studio
- Vá na aba "Local Inference Server"
- No dropdown "Model", selecione o modelo desejado (ex: `glm-ocr`)
- Se o modelo nao aparecer, va na aba "My Models" e confirme se foi baixado
- Clique **"Start Server"** (ou "Restart Server" se ja estiver rodando)
- Confirme que o servidor esta online em `http://localhost:1234/v1`

O nome exato do modelo no dropdown do LM Studio deve bater com o campo `lmstudio_model` no `config.json` do modelo dentro de `models/`. Para descobrir o nome, va no LM Studio > "Local Inference Server" > veja o nome ao lado do dropdown "Model".

### 3. Instalar dependencias do pipeline

Abra o terminal na pasta da skill e rode:

```bash
# Windows:
pip install -r requirements.txt
# Linux/Mac:
# pip3 install -r requirements.txt
```

Se preferir usar ambiente virtual (recomendado):

```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/Mac:
# source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configurar (opcional)

Se precisar alterar URL, modelo ou API key, copie o arquivo de exemplo:

```bash
# Windows:
copy .env.example .env
# Linux/Mac:
# cp .env.example .env
```

Edite o `.env` se necessario. Os valores padrao ja funcionam para a instalacao tipica do LM Studio.

## Variavel SKILL_DIR

**IMPORTANTE:** Antes de executar QUALQUER comando, determine o caminho absoluto desta skill.

O caminho absoluto de `SKILL_DIR` e o diretorio onde este arquivo `SKILL.md` esta localizado.

Exemplo:
- Tipico no Windows: `C:\Users\SeuUsuario\.agents\skills\document-ocr`

**Voce, agente, DEVE substituir `SKILL_DIR` pelo caminho real em todos os comandos abaixo.**

**Nota sobre Python:** No Windows use `python`, no Linux/Mac pode ser `python3`. Ajuste conforme o sistema.

## Pipeline de Execucao (Passo a Passo)

### Passo 0: Verificar Dependencias

Verifique se as dependencias estao instaladas. Se nao estiverem, instale:

```bash
pip install -r "SKILL_DIR/requirements.txt"
```

Se o LM Studio nao estiver rodando, informe o usuario que precisa inicia-lo primeiro (veja secao "Instalacao" acima).

### Passo 1: Determinar o Input

O usuario forneceu um arquivo. O caminho deste arquivo sera chamado de `INPUT_PATH`.

- Formatos suportados:
  - **OCR** (via LM Studio): `.pdf`, `.png`, `.jpg`, `.jpeg`
  - **Extracao nativa** (sem OCR): `.docx`, `.pptx`, `.html`, `.htm`
- Se for um caminho relativo, resolva para absoluto
- Se o usuario fez upload, o arquivo ja esta no sistema de arquivos
- Valide que o arquivo existe antes de prosseguir
- Para formatos nativos (.docx, .pptx, .html), o pipeline extrai o texto diretamente sem usar o LM Studio

### Passo 2: Executar o Pipeline

Execute o comando abaixo, substituindo `SKILL_DIR`, `INPUT_PATH` e `DIR_DO_INPUT` pelos valores reais. `DIR_DO_INPUT` e o diretorio onde o arquivo de entrada esta localizado (ex: `C:\Users\SeuUsuario\Desktop\OCR PDF`).

Para output padrao (Markdown, modo text-first, 200 DPI):

```bash
python "SKILL_DIR/main.py" "INPUT_PATH"
```

Isso salva em `DIR_DO_INPUT/saida_ocr/` automaticamente.

Para especificar formato ou diretorio customizado:

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --out "DIR_DO_INPUT/saida_ocr" --format markdown
```

Para saida multipla (Markdown + HTML + JSON):

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --out "DIR_DO_INPUT/saida_ocr" --format markdown html json
```

Para forcar OCR ignorando texto nativo:

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --out "DIR_DO_INPUT/saida_ocr" --format markdown --mode ocr-only
```

Para maior fidelidade (aumente DPI se o texto estiver pequeno):

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --out "DIR_DO_INPUT/saida_ocr" --format markdown --dpi 300
```

**Regras para escolha dos parametros:**
- Se o usuario nao especificou formato, use `--format markdown`
- Se o usuario nao especificou modo, use `--mode text-first`
- Se o usuario nao especificou DPI, use `--dpi 200`
- Se o usuario nao especificou diretorio de saida, use o padrao: `DIR_DO_INPUT/saida_ocr` (onde `DIR_DO_INPUT` e o diretorio do arquivo de entrada). NUNCA salve dentro da pasta da skill.
- Se o usuario nao especificou `--model`, pergunte: **"Qual o modelo de IA voce quer usar para extrair o texto?"** e liste as opcoes disponiveis (ex: chandra-ocr-2, glm-ocr)
- Se o PDF tiver muitas paginas ou o modelo for lento, aumente `--timeout` para 300-600
- Use `--resume` apenas se ja houver processamento parcial e o usuario quiser retomar

**Comportamento incremental:** O pipeline escreve no arquivo de saida (`.md`, `.html`) a cada pagina processada. Se o processo for interrompido, o arquivo ja contem todo o texto extraido ate aquele ponto. Arquivos temporarios (`.partial`, `.metadata.json`) sao removidos automaticamente ao final se tudo der certo.

**Verificacao automatica:** Ao terminar, o pipeline checa paginas faltantes, vocabulario preservado, numeros preservados e estrutura de cabecalhos.

### Passo 3: Ler o Resultado

Apos a execucao, leia o arquivo de saida gerado. O nome do arquivo sera o mesmo do input (ex: `texto.pdf` gera `texto.md`), dentro de `DIR_DO_INPUT/saida_ocr/`:

```bash
# Se formato for markdown:
cat "DIR_DO_INPUT/saida_ocr/NOME_DO_INPUT.md"        # Linux/Mac
type "DIR_DO_INPUT/saida_ocr/NOME_DO_INPUT.md"       # Windows
# Se formato for html:
cat "DIR_DO_INPUT/saida_ocr/NOME_DO_INPUT.html"
# Se formato for json:
cat "DIR_DO_INPUT/saida_ocr/NOME_DO_INPUT.json"
```

O modelo retorna o texto extraido em HTML ou Markdown (dependendo do modelo escolhido). O pipeline converte HTML → Markdown automaticamente se necessario e salva no `.md`.

**Voce, agente, DEVE limpar e formatar o arquivo .md final** ao apresentar o resultado ao usuario:

O pipeline ja converte HTML -> Markdown automaticamente via `_html_to_markdown()`, mas voce deve **revisar e polir** o resultado:

1. Leia o arquivo `DIR_DO_INPUT/saida_ocr/NOME_DO_INPUT.md`
2. Verifique se a **primeira pagina** esta presente (titulo, autores, abstract)
3. Remova residuos HTML que possam ter escapado (`<div>`, `<p>`, `<br/>`, `data-bbox`, etc.)
4. Ajuste cabecalhos para formato Markdown limpo (`#`, `##`, `###`)
5. Verifique se **tabelas** foram convertidas corretamente (formato `| celula | celula |`)
6. Remova linhas de raciocinio do modelo ("The image shows...", "The user wants...")
7. Junte linhas quebradas por `<br>` em paragrafos coesos
8. Preserve TUDO — numeros, nomes, valores, texto, referencias
9. Se houver `[unclear]`, mantenha como marcacao de texto duvidoso

**Verificacao de fidelidade inteligente:** Ao final, o pipeline analisa:
- **Paginas presentes/ausentes**: alerta se faltar pagina
- **Vocabulario preservado**: % de palavras significativas do texto original que aparecem na saida (threshold: 80%)
- **Numeros preservados**: % de numeros (estatisticas, anos, valores) do original que aparecem na saida (threshold: 90%)
- **Estrutura**: total de cabecalhos (# ## ###) detectados na saida
- Resultado consolidado: **PASS** (tudo OK) ou **PARTIAL** (com lista do que falhou)

**Nota:** O score de vocabulario e numeros agora e mais preciso, pois o HTML e convertido para Markdown antes da verificacao. Confie na **verificacao de paginas** e na **inspecao visual** que voce fara ao apresentar o resultado.

Leia o conteudo do arquivo de saida e apresente-o ao usuario formatado corretamente.

### Passo 4: Verificar Fidelidade

Leia a secao "Fidelity:" no log do pipeline. O resultado sera **PASS** ou **PARTIAL**.

- **PASS** → tudo ok, va para o Passo 5
- **PARTIAL** → veja abaixo o que fazer

O log mostra exatamente o que falhou:
- `missing pages` → paginas que nao foram processadas (timeout/erro)
- `vocabulary recall X% < 80%` → palavras do original ausentes na saida
- `number preservation X% < 90%` → numeros do original ausentes na saida

### Passo 5: Corrigir se Necessario

Se o resultado for **PARTIAL**, aplique as correcoes abaixo e repita o Passo 2 + Passo 4 (ciclo de correcao).

**Caso 1: Faltam paginas**
As paginas que falharam estao listadas nos metadados com status `error`. Rode novamente com `--resume` para processar apenas as faltantes. Se continuarem falhando, aumente `--timeout`:

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --out "DIR_DO_INPUT/saida_ocr" --format markdown --timeout 600 --resume
```

Se ainda falharem, tente `--mode ocr-only` para essas paginas (pode ser que o texto nativo esteja corrompido):

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --out "DIR_DO_INPUT/saida_ocr" --format markdown --mode ocr-only --dpi 300 --resume
```

**Caso 2: Vocabulario baixo (<80%)**
Aumente `--dpi` para 300-400 e rode novamente com `--resume`:

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --out "DIR_DO_INPUT/saida_ocr" --format markdown --dpi 400 --resume
```

Se o problema persistir, o PDF pode ter texto nativo de baixa qualidade. Tente `--mode ocr-only`.

**Caso 3: Numeros baixos (<90%)**
Numeros sao os indicadores mais uteis de perda de conteudo. Aumente `--dpi` para 400 e tente `--mode ocr-only`:

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --out "DIR_DO_INPUT/saida_ocr" --format markdown --mode ocr-only --dpi 400 --resume
```

**Apos corrigir:** repita o Passo 2 e depois o Passo 4 para re-verificar.

**Se ainda for PARTIAL apos todas as tentativas:** informe o usuario com transparencia:
- Quantas paginas foram extraidas com sucesso
- Quais paginas falharam (numeros)
- Score de vocabulario e numeros
- Sugira que o usuario tente manualmente com parametros mais agressivos ou outro modelo

### Passo 6: Informar Metricas

As metricas sao exibidas no log do pipeline ao final da execucao:

- Paginas processadas com sucesso / total
- Vocabulario preservado (se texto nativo disponivel)
- Numeros preservados (se texto nativo disponivel)
- Resultado: **PASS** ou **PARTIAL**

## Opcoes Completas do CLI

| Argumento | Descricao | Default |
|-----------|-----------|---------|
| `input` | Caminho do PDF, imagem, DOCX, PPTX ou HTML | obrigatorio |
| `--model` | Modelo de OCR (ex: `chandra-ocr-2`). Lista os disponiveis em `models/` | perguntado interativamente |
| `--out` | Diretorio de saida | `DIR_DO_INPUT/saida_ocr` (diretorio do arquivo + /saida_ocr)
| `--output-name` | Nome do arquivo de saida (sem extensao). Padrao: mesmo nome do input | (nome do input) |
| `--format` | Formato(s): `markdown`, `html`, `json` | `markdown` |
| `--mode` | `text-first` ou `ocr-only` | `text-first` |
| `--dpi` | Resolucao de renderizacao do PDF | `200` (ou o default do modelo) |
| `--resume` | Retoma processamento interrompido | `false` |
| `--lmstudio-url` | URL base da API do LM Studio | `http://localhost:1234/v1` |
| `--lmstudio-model` | Nome do modelo no LM Studio (overrides config do modelo) | do `config.json` do modelo |
| `--lmstudio-api-key` | Chave de API (se necessario) | vazio |
| `--timeout` | Timeout por requisicao (segundos) | `300` (ou o default do modelo) |
| `--retries` | Numero de tentativas por pagina | `3` |

## Estrutura de Saida

Se o input for `documento.pdf` com `--format markdown`, a saida sera:

```
DIR_DO_INPUT/
└── saida_ocr/
    └── documento.md          # Consolidado final em Markdown
```

Se `--format markdown html`:

```
DIR_DO_INPUT/
└── saida_ocr/
    ├── documento.md          # Consolidado final em Markdown
    └── documento.html        # Consolidado final em HTML
```

Arquivos temporarios (`.partial`, `.metadata.json`) sao removidos automaticamente ao final com sucesso.

## Comportamento do OCR

O comportamento depende do modelo escolhido e do formato de saida solicitado:

### Abordagem de Prompts Minimos

Os prompts sao propositalmente enxutos ("Extract all text from this document image faithfully.") porque:

- **Modelos especializados** (ex: Chandra OCR 2, GLM-OCR) foram fine-tunados com formatos de saida proprios
- Instrucoes detalhadas no prompt confundem o modelo e o fazem cair para formatos alternativos (JSON) ou adicionar raciocinio
- O modelo sabe seu formato nativo melhor do que instrucoes no prompt

### Fluxo de Trabalho

1. **Pipeline** extrai o texto bruto do modelo e salva no arquivo de saida
2. **Chat agent (voce)** le o arquivo de saida bruto e formata para apresentacao ao usuario:
   - Modelos HTML (Chandra): saida com `data-bbox`, `data-label` em HTML — voce converte para leitura limpa
   - Modelos Markdown (GLM-OCR): saida em Markdown — voce ajusta formatacao se necessario
   - Remova ruido como raciocinio do modelo, JSON extra, etc.
   - Devolva ao usuario o texto formatado de forma legivel

### Formato Markdown (`--format markdown`) — padrao

- Saida em texto legivel, sem preocupacao com estilo visual (fontes, cores, alinhamento)
- **Modelos HTML** (ex: `chandra-ocr-2`): retornam HTML, e o pipeline converte para Markdown via `_html_to_markdown()`
- **Modelos Markdown** (ex: `glm-ocr`): retornam Markdown diretamente
- Ideal para leitura, extracao de dados, copiar texto

### Formato HTML (`--format html`) — copia fiel

- Saida bruta do modelo em HTML com tags semanticas
- Modelos como Chandra OCR 2 podem incluir atributos nativos (`data-bbox`, `data-label`) — faz parte do formato em que foram treinados
- Ideal para copia fiel do layout do documento, preservacao de estrutura, visualizacao em navegador
- **Voce (chat agent) deve ler o HTML bruto e converter para leitura limpa ao apresentar ao usuario**

O pipeline entao:
1. Salva o resultado bruto em arquivos parciais (`page_*.html.partial` ou `page_*.markdown.partial`)
2. Se o formato for markdown e o modelo retornou HTML, converte para Markdown via `_html_to_markdown()`
3. Salva o resultado consolidado em `NOME.md` ou `NOME.html` conforme o formato escolhido

**O arquivo `.md` final ja vem processado.** No entanto, o agente (voce) DEVE revisar e polir o resultado (veja secao "Verificacao de fidelidade inteligente" acima).

O modelo de OCR:
- Nao inventa texto inexistente (quando segue as instrucoes)
- Preserva ordem natural de leitura
- Mantem tabelas de forma legivel
- Nao resume nem traduz
- Mantem o idioma original

## Modos de Processamento

### text-first (padrao)
1. Extrai texto nativo do PDF (via PyMuPDF) como referencia
2. SEMPRE renderiza a pagina como imagem e faz OCR multimodal
3. O texto nativo extraido e enviado como contexto adicional (imagem e a fonte de verdade)
- Mais preciso porque o modelo ve a imagem e pode verificar o texto extraido
- O texto nativo ajuda o modelo a resolver ambiguidades

### ocr-only
- Ignora o texto embutido no PDF
- Renderiza cada pagina como imagem e envia para o modelo
- Recomendado para PDFs escaneados ou com texto nativo corrompido

## Adicionar Novo Modelo

Para adicionar um novo modelo de OCR:

1. Crie uma pasta em `models/` com o nome do modelo (ex: `models/meu-modelo/`)
2. Copie os arquivos do `models/template/` para dentro dela
3. Edite `config.json`:
   - `name`: identificador unico (igual ao nome da pasta)
   - `label`: nome legivel para exibicao
   - `description`: descricao curta do modelo
   - `lmstudio_model`: nome do modelo no servidor LM Studio
   - `default_prompt_format`: `"html"` se o modelo retorna HTML (recomendado), ou `"markdown"` se retorna Markdown direto
   - `supports_formats`: formatos suportados
   - `use_system_prompt`: `true` se o modelo precisa de system prompt, `false` caso contrario
   - `use_native_text_reference`: `true` para enviar texto nativo como referencia (recomendado para modelos HTML), `false` para enviar apenas a imagem (recomendado para modelos Markdown como GLM-OCR)
   - `default_timeout` / `default_dpi`: valores padrao
4. Edite `prompts.py` com prompts otimizados para o modelo
5. O modelo aparecera automaticamente na lista ao rodar `main.py`

## Troubleshooting

**"LM Studio endpoint offline"**: O servidor nao esta rodando. Pec,a ao usuario que abra o LM Studio, carregue o modelo e clique em "Start Server". A URL padrao e `http://localhost:1234/v1`.

**"Request failed after X attempts"**: LM Studio esta rodando mas nao respondeu a tempo. Aumente `--timeout` ou pec,a ao usuario para verificar se o modelo terminou de carregar.

**"Model error"**: O modelo retornou um erro. Verifique se `--lmstudio-model` corresponde exatamente ao nome do modelo no servidor do LM Studio. Para descobrir o nome exato, va no LM Studio > aba "Local Inference Server" > veja o nome ao lado de "Model".

**Saida vazia ou incorreta**: Aumente `--dpi` para 300-400 para capturar mais detalhes.

**Primeira pagina faltando**: O pipeline SEMPRE envia a imagem para o modelo agora (mesmo em modo text-first). Se ainda assim faltar, aumente `--dpi` e `--timeout`.

**Modelo inventa conteudo (hallucination)**: O system prompt (se habilitado) possui instrucoes explicitas contra inventar. Se o problema persistir, tente `--mode ocr-only` para ignorar o texto nativo de referencia.

**HTML com data-bbox na saida**: O prompt markdown agora proibe explicitamente tags HTML e atributos data-*. O `_html_to_markdown()` tambem remove `data-*` automaticamente como fallback.

**"Fidelity: PARTIAL"**: O pipeline detectou que algo ficou de fora. Siga o Passo 5 (Corrigir se Necessario) para diagnosticar e resolver.

**Saida vazia mesmo apos processamento**: O modelo pode estar retornando o conteudo no campo `reasoning_content` em vez de `content`. O `lmstudio_client.py` ja captura de ambos automaticamente.

**GPU AMD**: A aceleracao AMD e gerenciada pelo LM Studio. O pipeline Python e puramente cliente HTTP, sem CUDA.
