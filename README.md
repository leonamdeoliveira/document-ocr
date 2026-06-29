# Document OCR + Pipeline Hibrido com Layout

Pipeline OCR completo para converter PDFs, imagens e documentos em Markdown/HTML/JSON estruturado com modelo de documento hierarquico. Suporta **analise de layout** (PyMuPDF), **OCR clasico** (Tesseract) e **OCR por IA** (LM Studio: GLM-OCR, Chandra OCR, GraniteDocling GGUF), com roteamento inteligente.

> Esta e uma **skill** compativel com os principais assistentes de IA. O arquivo `SKILL.md` define o comportamento do agente.

## Arquitetura

```
                         ┌──────────────────┐
                         │   LayoutEngine   │
                         │   (PyMuPDF)      │
                         └────────┬─────────┘
                                  │ titulos, paragrafos,
                                  │ tabelas, imagens, ordem de leitura
                                  ▼
                         ┌──────────────────┐
                         │    Document      │
                         │  (modelo estruturado) │
                         └────────┬─────────┘
                                  │ paginas sem texto
                                  ▼
                         ┌──────────────────┐
                         │    OCRRouter     │
                         └────────┬────────┘
                                  │
                     ┌────────────┴────────────┐
                     ▼                         ▼
               ┌──────────┐            ┌──────────┐
               │ Tesseract│            │ AIEngine │
               │ (rapido) │  ──fallback──▶ │ (LM Studio)│
               └──────────┘            └──────────┘
                     │                         │
                     └────────────┬────────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │  QualityScorer   │
                         │ (per-item scoring)│
                         └────────┬─────────┘
                                  │
                                  ▼
                         ┌──────────────────┐
                         │   Export         │
                         │ MD / HTML / JSON │
                         │ + .document.json │
                         └──────────────────┘
```

### Fluxo de Decisao

```
1. Layout Analysis (PyMuPDF) — instantaneo, zero custo
   └─ Se tem estrutura → USA LAYOUT, pula OCR

2. Tesseract (OCR classico) — rapido, CPU
   ├─ Avaliacao por referencia (compara com texto nativo)
   └─ Score >= threshold → aceita

3. LM Studio (IA) — maxima qualidade, GPU
   └─ Fallback para documentos complexos ou --ocr-mode ai_only
```

## Modos de Operacao

| Modo | Descricao |
|------|-----------|
| `hybrid` (padrao) | Layout + Tesseract + fallback IA via LM Studio |
| `legacy` | IA via LM Studio em todas as paginas |
| `classic_only` | So Layout + Tesseract, sem IA |
| `ai_only` | So IA via LM Studio |

## Formatos Suportados

### Com OCR (analise de layout + OCR hibrido)
| Formato | Extensoes |
|---------|-----------|
| PDF | `.pdf` |
| Imagens | `.png`, `.jpg`, `.jpeg` |

### Com Extracao Nativa (sem OCR)
| Formato | Extensoes |
|---------|-----------|
| Word | `.docx` |
| PowerPoint | `.pptx` |
| Excel | `.xlsx`, `.xlsm` |
| HTML | `.html`, `.htm` |
| EPUB | `.epub` |
| CSV | `.csv` |
| Markdown | `.md` |
| LaTeX | `.tex` |
| Texto puro | `.txt` |

## Modelos Disponiveis

| Modelo | Formato | Via | Notas |
|--------|---------|-----|-------|
| `glm-ocr` | Markdown | LM Studio | Melhor qualidade geral |
| `chandra-ocr-2` | HTML → MD | LM Studio | System prompt, batch |
| `granite-docling` | DocTags → MD | LM Studio (GGUF) | VLM 258M, saida estruturada |

GraniteDocling GGUF: https://huggingface.co/SandLogicTechnologies/granite-docling-258M-GGUF

## Compatibilidade com Assistentes de IA

| Ferramenta | Como usar |
|---|---|
| **opencode** | Copie para `~/.agents/skills/document-ocr/` |
| **Claude Code** | Copie para `~/.claude/skills/document-ocr/` |
| **Cursor** | Copie `SKILL.md` para `.cursor/rules/document-ocr.mdc` |
| **GitHub Copilot** | Copie `SKILL.md` (sem YAML) para `.github/copilot-instructions.md` |
| **Windsurf** | Copie `SKILL.md` (sem YAML) para `.windsurfrules` |

## Instalacao

```bash
pip install -r requirements.txt

# Tesseract (Windows):
winget install -e --id UB-Mannheim.TesseractOCR
pip install pytesseract

# LM Studio:
# Baixe em: https://lmstudio.ai/
```

## Uso

```bash
# Modo hibrido padrao:
python main.py documento.pdf

# Com modelo especifico (ex: GraniteDocling GGUF no LM Studio):
python main.py documento.pdf --model granite-docling --ocr-mode hybrid

# IA pura (todas as paginas via LM Studio):
python main.py documento.pdf --ocr-mode ai_only --model granite-docling

# Classico (so Tesseract):
python main.py documento.pdf --ocr-mode classic_only

# Sem layout (OCR pagina inteira):
python main.py documento.pdf --no-layout

# Com todos os parametros:
python main.py documento.pdf \
    --ocr-mode hybrid \
    --model granite-docling \
    --ocr-langs por+eng \
    --quality-threshold 0.70 \
    --dpi 200 \
    --format markdown html json

# Formatos nativos:
python main.py documento.docx
python main.py planilha.xlsx
python main.py livro.epub
```

## Argumentos CLI

| Argumento | Descricao | Default |
|-----------|-----------|---------|
| `input` | Caminho do arquivo | obrigatorio |
| `--model` | `glm-ocr`, `chandra-ocr-2`, `granite-docling` | `glm-ocr` (hybrid) |
| `--out` | Diretorio de saida | `DIR_DO_INPUT/saida_ocr` |
| `--output-name` | Nome do arquivo de saida | (nome do input) |
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

## Estrutura do Projeto

```
document-ocr/
├── main.py                    # CLI principal
├── document_model.py          # Modelo de documento estruturado
├── model_loader.py            # Carregamento de modelos
├── native_extractor.py        # Extracao nativa (11 formatos)
├── ocr_pipeline.py            # Orquestracao do pipeline
├── pdf_utils.py               # Layout, tabelas, imagens, renderizacao
├── lmstudio_client.py         # Cliente HTTP LM Studio
├── requirements.txt           # Dependencias Python
├── SKILL.md                   # Definicao da skill
├── README.md                  # Este arquivo
├── .env.example               # Template de variaveis
├── ocr_engine/                # Motores de OCR
│   ├── __init__.py
│   ├── base.py                # Interface OCREngineBase
│   ├── config.py              # HybridOCRConfig
│   ├── quality.py             # QualityScorer + ItemQualityReport
│   ├── router.py              # OCRRouter
│   ├── ai_engine.py           # AIEngine (LM Studio)
│   ├── tesseract_engine.py    # TesseractEngine
│   ├── layout_engine.py       # LayoutEngine (PyMuPDF)
│   └── text_stats.py          # Tokenizacao
├── models/                    # Configuracoes dos modelos
│   ├── chandra-ocr-2/
│   ├── glm-ocr/
│   ├── granite-docling/
│   └── template/
└── saida_ocr/                 # Diretorio de saida (gerado)
```

## Estrutura de Saida

```
DIR_DO_INPUT/
└── saida_ocr/
    ├── documento.md              # Markdown consolidado
    ├── documento.html            # (se --format html)
    ├── documento.json            # (se --format json)
    ├── documento.document.json   # Modelo lossless
    ├── images/                   # Imagens extraidas
    │   └── page_0001_img_00.png
    └── page_*.partial            # Temporarios (removidos)
```

## Troubleshooting

**Tesseract not found**: Instale o binary e/ou defina `TESSERACT_CMD`.

**LM Studio offline**: No modo `hybrid`, o Tesseract processa o que consegue. Para paginas restantes, inicie o LM Studio e use `--resume`.

**Fidelity PARTIAL**: Verifique o `.document.json`. Aumente `--dpi` para 300-400, reduza `--quality-threshold` para 0.60, ou use `--ocr-mode ai_only`.

**Layout analysis falhou**: Use `--no-layout` para OCR de pagina inteira.

**GPU AMD**: A aceleracao e gerenciada pelo LM Studio. O pipeline e cliente HTTP.
