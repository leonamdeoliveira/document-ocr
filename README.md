# Document OCR + Pipeline Hibrido

Pipeline OCR completo para converter PDFs, imagens, DOCX, PPTX e HTML em Markdown/HTML/JSON estruturado. Suporta **OCR clasico** (Tesseract, PaddleOCR) para documentos simples e **OCR por IA** (LM Studio) para documentos complexos, com roteamento inteligente entre eles.

## Arquitetura

### OCR Hibrido (novo)

```
                    ┌──────────────┐
                    │  OCRRouter   │
                    └──────┬───────┘
                           │
              ┌────────────┼────────────┐
              ▼            ▼            ▼
        ┌──────────┐ ┌──────────┐ ┌──────────┐
        │ Tesseract│ │ PaddleOCR│ │ AIEngine │
        │ (rapido) │ │ (medio)  │ │ (GLM-OCR)│
        └──────────┘ └──────────┘ └──────────┘
              │            │            │
              ▼            ▼            ▼
        ┌─────────────────────────────────────┐
        │        QualityScorer                │
        │  (heuristica de qualidade do texto) │
        └─────────────────────────────────────┘
              │
              ▼
        ┌─────────────────────────────────────┐
        │        OutputNormalizer             │
        │  (limp eza d e ruido de OCR)         │
        └─────────────────────────────────────┘
```

### Fluxo Original (legado)

```
PDF/Imagem → PyMuPDF (render) → LM Studio (API multimodal) → HTML/Markdown
DOCX/PPTX/HTML → Extracao nativa (python-docx / python-pptx / html2text) → Markdown
```

## Modos de Operacao

| Modo | Descricao | Quando usar |
|------|-----------|-------------|
| `legacy` | IA via LM Studio (comportamento original) | Documentos complexos, compatibilidade total |
| `hybrid` | Tenta Tesseract, fallback para IA | Uso geral, equilibrio velocidade/qualidade |
| `classic_only` | So OCR clasico (Tesseract/Paddle) | Documentos simples, sem IA disponivel |
| `ai_only` | So IA (como legacy) | Documentos complexos |

## Instalacao

### Dependencias principais

```bash
pip install -r requirements.txt
```

### OCR Clasico (opcional)

```bash
# Tesseract (Windows):
winget install -e --id UB-Mannheim.TesseractOCR
pip install pytesseract

# PaddleOCR (opcional):
pip install paddleocr
```

### OCR por IA

Baixe o LM Studio em: https://lmstudio.ai/

## Uso

```bash
# Modo legado (comportamento original):
python main.py documento.pdf

# Modo hibrido (Tesseract com fallback para IA):
python main.py documento.pdf --ocr-mode hybrid

# Modo classico (so Tesseract, sem LM Studio):
python main.py documento.pdf --ocr-mode classic_only

# Modo IA (como legacy):
python main.py documento.pdf --ocr-mode ai_only

# Com parametros customizados:
python main.py documento.pdf \
    --ocr-mode hybrid \
    --classic-engine tesseract \
    --ocr-langs por+eng \
    --quality-threshold 0.70 \
    --dpi 300

# Formatos multiplos:
python main.py documento.pdf --format markdown html json

# DOCX/PPTX/HTML (extracao nativa, sem OCR):
python main.py documento.docx
python main.py apresentacao.pptx
python main.py pagina.html
```

## Argumentos CLI

| Argumento | Descricao | Default |
|-----------|-----------|---------|
| `input` | Caminho do PDF, imagem, DOCX, PPTX ou HTML | obrigatorio |
| `--model` | Modelo de OCR (ex: `chandra-ocr-2`) | perguntado interativamente |
| `--out` | Diretorio de saida | `DIR_DO_INPUT/saida_ocr` |
| `--output-name` | Nome do arquivo de saida (sem extensao) | (nome do input) |
| `--format` | Formato(s): `markdown`, `html`, `json` | `markdown` |
| `--mode` | `text-first` ou `ocr-only` | `text-first` |
| `--dpi` | Resolucao de renderizacao do PDF | `200` |
| `--resume` | Retoma processamento interrompido | `false` |
| `--ocr-mode` | `legacy`, `hybrid`, `classic_only`, `ai_only` | `legacy` |
| `--classic-engine` | Motor clasico: `tesseract`, `paddle` | `tesseract` |
| `--ocr-langs` | Idiomas para OCR clasico (ex: `por+eng`) | `por+eng` |
| `--quality-threshold` | Score minimo para aceitar OCR clasico (0-1) | `0.70` |
| `--timeout` | Timeout por requisicao (s) | `300` |
| `--retries` | Maximo de tentativas por pagina | `3` |

## Estrutura do Projeto

```
document-ocr/
├── main.py                    # CLI principal
├── model_loader.py            # Carregamento de modelos
├── native_extractor.py        # Extracao nativa DOCX, PPTX, HTML
├── ocr_pipeline.py            # Orquestracao do pipeline
├── pdf_utils.py               # Renderizacao de PDF (PyMuPDF)
├── lmstudio_client.py         # Cliente HTTP LM Studio
├── ocr_engine/                # Motores de OCR
│   ├── base.py                # Interface OCREngineBase
│   ├── config.py              # HybridOCRConfig
│   ├── quality.py             # QualityScorer
│   ├── normalizer.py          # OutputNormalizer
│   ├── router.py              # OCRRouter
│   ├── ai_engine.py           # AIEngine (GLM-OCR)
│   ├── tesseract_engine.py    # TesseractEngine
│   └── paddle_engine.py       # PaddleEngine (opcional)
├── models/                    # Configuracoes dos modelos
│   ├── chandra-ocr-2/
│   ├── glm-ocr/
│   └── template/
├── tests/                     # Testes
│   ├── test_quality.py
│   ├── test_normalizer.py
│   ├── test_router.py
│   ├── test_regression.py
│   └── test_config.py
└── tasks/                     # Planos de implementacao
```

## Modelos Disponiveis

| Modelo | Formato | System Prompt | Ref. Texto Nativo |
|--------|---------|---------------|-------------------|
| `chandra-ocr-2` | HTML → convertido para MD | Sim | Sim |
| `glm-ocr` | Markdown diretamente | Nao | Nao |

Para adicionar um novo modelo, copie `models/template/` e edite `config.json` e `prompts.py`.

## Testes

```bash
python tests/test_quality.py
python tests/test_normalizer.py
python tests/test_config.py
python tests/test_router.py
python tests/test_regression.py
```

## Troubleshooting

**Tesseract not found**: Instale o binary e/ou defina `TESSERACT_CMD` environment variable apontando para o executavel.

**LM Studio offline**: Se estiver no modo `hybrid` com Tesseract, o sistema tenta OCR clasico antes de fallback.

**Fidelity PARTIAL**: Aumente `--dpi` para 300-400 ou use `--ocr-mode hybrid` para fallback para IA.
