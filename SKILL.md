---
name: document-ocr
description: Leitura de PDFs, imagens, DOCX, PPTX, HTML, XLSX, EPUB, CSV e mais usando OCR hibrido (layout + Tesseract + IA via LM Studio) com modelo de documento hierarquico. Converte documentos para Markdown/HTML/JSON estruturado. Use quando o usuario pedir para "ler PDF", "extrair texto de imagem", "converter documento", "ler DOCX", "ler PPT", "ler HTML", "ler XLSX", "ler EPUB", "OCR" ou "transformar PDF em markdown". Compativel com opencode, Claude Code, Cursor, GitHub Copilot, Windsurf e outros assistentes de IA.
---

# Document OCR - Pipeline de Leitura de Documentos

Converte PDFs e imagens em texto estruturado (Markdown/HTML/JSON) usando pipeline hibrido com analise de layout (PyMuPDF), Tesseract e fallback automatico para IA multimodal via LM Studio (GLM-OCR, Chandra OCR, GraniteDocling GGUF).

## Quando Usar (Disparo Automatico)

Esta skill DEVE ser ativada automaticamente SEMPRE que:

- Usuario pede "leia este PDF", "leia esta imagem", "extraia o texto desse PDF", "converta PDF para markdown"
- Usuario menciona "ler" + "PDF", "ler" + "imagem", "ler" + "documento", "extrair texto", "OCR"
- Usuario **envia/cola/arrasta** um arquivo com extensao `.pdf`, `.png`, `.jpg`, `.jpeg`, `.docx`, `.pptx`, `.html`, `.htm`, `.xlsx`, `.xlsm`, `.epub`, `.csv`, `.md`, `.tex`, `.txt`
- Usuario pede "leia este DOCX", "leia este PowerPoint", "leia este HTML", "leia este EPUB", "leia esta planilha"
- Usuario quer OCR de documentos com preservacao de estrutura (tabelas, listas, titulos, imagens)
- Usuario menciona "Chandra OCR", "LM Studio", "OCR documento", "Tesseract", "OCR clasico", "GraniteDocling"

**Nao pergunte ao usuario se ele quer usar OCR. Simplesmente ative a skill e processe o arquivo.**

**Nota:** Para `.docx`, `.pptx`, `.html`, `.xlsx`, `.epub`, `.csv`, `.md`, `.tex` e `.txt`, a extracao de texto e **nativa** (sem OCR), pois esses formatos ja possuem texto selecionavel.

## Estrutura da Skill

```
SKILL_DIR/
├── SKILL.md                   # Este arquivo
├── main.py                    # CLI principal (ponto de entrada)
├── model_loader.py            # Carregamento de config/prompts dos modelos
├── native_extractor.py        # Extracao nativa (11 formatos)
├── document_model.py          # Modelo de documento estruturado (DocItem, Document)
├── ocr_pipeline.py            # Orquestracao do pipeline com 3 estagios
├── pdf_utils.py               # Renderizacao, layout, tabelas, imagens
├── lmstudio_client.py         # Cliente HTTP OpenAI-compatible
├── ocr_engine/                # Motores de OCR
│   ├── __init__.py            # Exports publicos
│   ├── base.py                # Interface OCREngineBase + EngineResult
│   ├── config.py              # HybridOCRConfig
│   ├── quality.py             # QualityScorer + ItemQualityReport (per-item)
│   ├── router.py              # OCRRouter (Tesseract -> fallback IA)
│   ├── ai_engine.py           # AIEngine (LM Studio multi-modelo)
│   ├── tesseract_engine.py    # TesseractEngine (image_to_data)
│   ├── layout_engine.py       # LayoutEngine (PyMuPDF)
│   └── text_stats.py          # Tokenizacao e estatisticas
├── requirements.txt           # Dependencias Python
├── .env.example               # Template de variaveis de ambiente
├── README.md                  # Documentacao
└── models/                    # Modelos de OCR
    ├── chandra-ocr-2/         # Chandra OCR 2 (retorna HTML)
    ├── glm-ocr/               # GLM-OCR (retorna Markdown)
    ├── granite-docling/       # GraniteDocling 258M GGUF (via LM Studio)
    └── template/              # Template para novos modelos
```

## Instalacao (para um usuario novo)

### 1. Instalar Python 3.10+

```bash
python --version
```

### 2. Instalar LM Studio e modelos de OCR

Baixe o LM Studio em: https://lmstudio.ai/

Modelos recomendados:
- `glm-ocr` — OCR geral, saida Markdown
- `granite-docling` — Baixe o GGUF em: https://huggingface.co/SandLogicTechnologies/granite-docling-258M-GGUF

Apos instalar: aba "Local Inference Server" > selecione o modelo > "Start Server"

### 3. Instalar Tesseract (Windows)

```powershell
winget install -e --id UB-Mannheim.TesseractOCR
```

### 4. Instalar dependencias do pipeline

```bash
pip install -r requirements.txt
```

### 5. Configurar (opcional)

```bash
copy .env.example .env
```

## Variavel SKILL_DIR

**IMPORTANTE:** Antes de executar QUALQUER comando, determine o caminho absoluto desta skill.

O caminho absoluto de `SKILL_DIR` e o diretorio onde este arquivo `SKILL.md` esta localizado.

**Voce, agente, DEVE substituir `SKILL_DIR` pelo caminho real em todos os comandos abaixo.**

## Pipeline de Execucao (Passo a Passo)

### Passo 0: Verificar Dependencias

```bash
pip install -r "SKILL_DIR/requirements.txt"
```

### Passo 1: Determinar o Input

O usuario forneceu um arquivo. O caminho deste arquivo sera chamado de `INPUT_PATH`.

- **OCR hibrido**: `.pdf`, `.png`, `.jpg`, `.jpeg`
- **Extracao nativa** (sem OCR): `.docx`, `.pptx`, `.html`, `.htm`, `.xlsx`, `.xlsm`, `.epub`, `.csv`, `.md`, `.tex`, `.txt`

### Passo 2: Escolher o Modo de OCR

| Modo | Descricao | Quando usar |
|------|-----------|-------------|
| `hybrid` (padrao) | Layout + Tesseract + fallback IA via LM Studio | **Sempre usar como padrao.** |
| `legacy` | IA via LM Studio em todas as paginas | Documentos complexos, LM Studio rodando |
| `classic_only` | So Layout + Tesseract, sem IA | Documentos simples, LM Studio offline |
| `ai_only` | So IA (equivalente ao legacy) | Forcar uso de modelo especifico |

**Regra de decisao para o agente:**

- **Sempre** use `hybrid` primeiro (padrao). O pipeline em 3 estagios:
  1. **Layout Analysis**: PyMuPDF extrai estrutura (titulos, paragrafos, tabelas, imagens)
  2. **OCR**: Para paginas sem texto, tenta Tesseract. Se qualidade < threshold, fallback IA
  3. **Quality Scoring**: Score por item + export Markdown/HTML/JSON + `.document.json` lossless
- Se LM Studio **nao estiver rodando**: o `hybrid` usa Tesseract e avisa se alguma pagina precisar de IA

### Passo 3: Executar o Pipeline

**Modo hibrido (padrao):**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH"
```

**Modo hibrido com modelo especifico (ex: GraniteDocling GGUF no LM Studio):**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --model granite-docling
```

**Sem analise de layout (OCR pagina inteira):**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --no-layout
```

**Modo classico (so Tesseract):**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --ocr-mode classic_only
```

**Modo IA puro (ex: GraniteDocling em todas as paginas):**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --ocr-mode ai_only --model granite-docling
```

**Com parametros customizados:**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" \
    --out "DIR_DO_INPUT/saida_ocr" \
    --format markdown html json \
    --quality-threshold 0.70 \
    --ocr-langs por+eng \
    --dpi 200
```

**Regras para escolha dos parametros:**
- Formato padrao: `--format markdown`
- Modo OCR padrao: `hybrid`
- Modelo padrao: `glm-ocr` (hybrid/classic_only) ou perguntado interativamente (legacy/ai_only)
- Diretorio de saida padrao: `DIR_DO_INPUT/saida_ocr`. NUNCA salve dentro da pasta da skill.
- Use `--resume` para retomar processamento parcial
- Layout analysis ativado por padrao. Use `--no-layout` se houver problemas

### Passo 4: Ler o Resultado

```bash
# Windows:
type "DIR_DO_INPUT/saida_ocr/NOME_DO_INPUT.md"
```

O pipeline gera:
- `.md` — Markdown consolidado
- `.html` — HTML estruturado (se `--format html`)
- `.json` — JSON consolidado (se `--format json`)
- `.document.json` — Modelo lossless com TODOS os itens, bounding boxes, scores, hierarquia

**Voce, agente, DEVE limpar e formatar o arquivo .md final:**
1. Remova residuos de OCR, linhas de raciocinio
2. Ajuste cabecalhos e tabelas se necessario
3. Preserve TUDO — numeros, nomes, valores

### Passo 5: Verificar Fidelidade

Metricas exibidas ao final:
- Metodo por pagina (layout, tesseract, ai:NOME_DO_MODELO)
- Score por item com thresholds adaptativos (5 chars p/ heading, 10 p/ tabela, 20 p/ texto)
- `overall_confidence` media do documento
- Resultado: **PASS** (avg >= 0.80, sem itens LOW) ou **PARTIAL**

## Modelo de Documento Estruturado

O `.document.json` contem o modelo completo:

```json
{
  "filename": "documento.pdf",
  "pages": [{
    "page": 1,
    "width": 595, "height": 842,
    "items": [
      {"id": "abc", "label": "heading", "text": "Introducao", "confidence": 0.875, "bbox": {...}},
      {"id": "def", "label": "text", "text": "Lorem ipsum...", "confidence": 0.994, "bbox": {...}},
      {"id": "ghi", "label": "table", "rows": [...], "headers": [...], "confidence": 0.85}
    ]
  }],
  "items": { "abc": {...}, "def": {...}, "ghi": {...} },
  "body": ["abc", "def", "ghi"],
  "stats": { "total_items": 45, "overall_confidence": 0.92 }
}
```

Tipos de itens: `text`, `heading`, `table`, `picture`, `group`, `list_ul`, `list_ol`, `section`.

## Fluxo de Decisao do Router (modo hybrid)

```
1. Layout Analysis (PyMuPDF) — instantaneo:
   ├─ Blocos de texto, fontes, bold, bounding boxes
   ├─ Tabelas (find_tables)
   ├─ Imagens embutidas
   └─ Se tem estrutura → USA LAYOUT

2. Para paginas sem estrutura extraivel:

   3. Texto nativo >= 50 chars? → USA TEXTO NATIVO

   4. Tenta Tesseract (image_to_data, confianca real)

   5. Avaliacao:
      ├─ Tem texto nativo >= 20 chars? → AVALIACAO POR REFERENCIA
      │   └─ Word recall (70%) + number preservation (30%)
      └─ Sem texto nativo → AVALIACAO HEURISTICA (QualityScorer)
          └─ 6 metricas: alfanumericos, simbolos, linha media,
             linhas vazias, repeticoes, confianca Tesseract

   6. Score >= threshold? → ACEITA
      Score < threshold? → FALLBACK IA (LM Studio)

7. Fallback IA:
   ├─ LM Studio rodando? → processa com modelo carregado
   └─ LM Studio offline? → avisa + preserva parciais para --resume
```

## Opcoes Completas do CLI

| Argumento | Descricao | Default |
|-----------|-----------|---------|
| `input` | Caminho do arquivo | obrigatorio |
| `--model` | Modelo: `glm-ocr`, `chandra-ocr-2`, `granite-docling` | `glm-ocr` (hybrid) |
| `--out` | Diretorio de saida | `DIR_DO_INPUT/saida_ocr` |
| `--output-name` | Nome do arquivo de saida (sem extensao) | (nome do input) |
| `--format` | `markdown`, `html`, `json` | `markdown` |
| `--mode` | `text-first` ou `ocr-only` | `text-first` |
| `--dpi` | Resolucao de renderizacao | `200` |
| `--resume` | Retoma processamento interrompido | `false` |
| `--ocr-mode` | `hybrid`, `legacy`, `classic_only`, `ai_only` | `hybrid` |
| `--classic-engine` | Motor classico: `tesseract` | `tesseract` |
| `--ocr-langs` | Idiomas para OCR classico | `por+eng` |
| `--quality-threshold` | Score minimo para aceitar OCR (0-1) | `0.70` |
| `--timeout` | Timeout por requisicao (s) | `300` |
| `--retries` | Maximo de tentativas por pagina | `3` |
| `--no-layout` | Desativa analise de layout | `false` |
| `--lmstudio-url` | URL do LM Studio | `http://localhost:1234/v1` |
| `--lmstudio-model` | Nome do modelo no LM Studio | (do config) |

## Modelos Disponiveis

| Modelo | Formato | Via | Notas |
|--------|---------|-----|-------|
| `glm-ocr` | Markdown | LM Studio | OCR geral, melhor qualidade |
| `chandra-ocr-2` | HTML → MD | LM Studio | Com system prompt, suporta batch |
| `granite-docling` | DocTags → MD | LM Studio (GGUF) | VLM 258M leve, saida estruturada |

Para adicionar um novo modelo, copie `models/template/` e edite `config.json` e `prompts.py`.

## Estrutura de Saida

```
DIR_DO_INPUT/
└── saida_ocr/
    ├── documento.md              # Markdown consolidado
    ├── documento.html            # (se --format html)
    ├── documento.json            # (se --format json)
    ├── documento.document.json   # Modelo lossless (sempre gerado)
    ├── images/                   # Imagens extraidas
    │   └── page_0001_img_00.png
    └── page_*.partial            # Temporarios (removidos ao final)
```

## Troubleshooting

**"Tesseract not available"**: Instale o binary e/ou `pip install pytesseract`. Defina `TESSERACT_CMD` se necessario.

**"LM Studio endpoint offline"**: O servidor nao esta rodando. No modo `hybrid`, o Tesseract processa o que consegue. Para paginas restantes, inicie o LM Studio e use `--resume`.

**"Request failed after X attempts"**: Aumente `--timeout` ou verifique se o modelo terminou de carregar no LM Studio.

**"Fidelity: PASS"**: Todos os itens processados com sucesso. Confie no resultado.

**"Fidelity: PARTIAL"**: Alguns itens com qualidade baixa.
- Verifique o `.document.json` para ver quais itens tem score baixo
- Aumente `--dpi` para 300-400 ou reduza `--quality-threshold` para 0.60
- Se "LM Studio needed": inicie o LM Studio e execute `--resume`

**"LM Studio needed"**: Execute com `--resume` apos iniciar o LM Studio:
```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --resume
```

**"Saida vazia ou incorreta"**: Aumente `--dpi` para 300-400.

**Layout analysis falhou**: Use `--no-layout` para OCR de pagina inteira.

**GPU AMD**: A aceleracao AMD e gerenciada pelo LM Studio. O pipeline e cliente HTTP, sem CUDA.
