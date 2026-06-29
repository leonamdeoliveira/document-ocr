# Document OCR + Pipeline Hibrido

Pipeline OCR completo para converter PDFs, imagens, DOCX, PPTX e HTML em Markdown/HTML/JSON estruturado. Suporta **OCR clasico** (Tesseract) para documentos simples e **OCR por IA** (LM Studio) para documentos complexos, com roteamento inteligente entre eles.

> Esta e uma **skill** compatível com os principais assistentes de IA. O arquivo `SKILL.md` define o comportamento do agente.

## Arquitetura

### OCR Hibrido

```
                    ┌──────────────┐
                    │  OCRRouter   │
                    └──────┬───────┘
                           │
               ┌───────────┴───────────┐
               ▼                       ▼
         ┌──────────┐           ┌──────────┐
         │ Tesseract│           │ AIEngine │
         │ (rapido) │           │ (GLM-OCR)│
         └──────────┘           └──────────┘
               │                       │
               ▼                       ▼
         ┌─────────────────────────────────────┐
         │        QualityScorer                │
         │  (avaliacao referencia/heuristica)  │
         └─────────────────────────────────────┘
               │
               ▼
         ┌─────────────────────────────────────┐
         │        OCRPipeline                  │
         │  (limpeza, normalizacao, saida)     │
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
| `classic_only` | So OCR clasico (Tesseract) | Documentos simples, sem IA disponivel |
| `ai_only` | So IA (como legacy) | Documentos complexos |

## Compatibilidade com Assistentes de IA

| Ferramenta | Como usar |
|---|---|
| **opencode** | Copie a pasta para `~/.agents/skills/document-ocr/` — ativacao automatica |
| **Claude Code** | Copie a pasta para `~/.claude/skills/document-ocr/` — ativacao automatica |
| **Cursor** | Copie o conteudo do `SKILL.md` para `.cursor/rules/document-ocr.mdc` na raiz do projeto |
| **GitHub Copilot** | Copie o conteudo do `SKILL.md` (sem o bloco YAML) para `.github/copilot-instructions.md` |
| **Windsurf** | Copie o conteudo do `SKILL.md` (sem o bloco YAML) para `.windsurfrules` na raiz do projeto |
| **Aider** | Use `--read SKILL.md` ou configure no `.aider.conf.yml` |
| **Outros** | Use o `SKILL.md` como system prompt ou custom instructions da ferramenta |

> **Nota:** Para ferramentas que nao suportam o placeholder `SKILL_DIR`, substitua todas as ocorrencias de `SKILL_DIR` pelo caminho absoluto onde a skill foi instalada.

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
```

### OCR por IA

Baixe o LM Studio em: https://lmstudio.ai/

## Uso

```bash
# Modo hibrido (default: Tesseract com fallback para IA):
python main.py documento.pdf

# Modo classico (so Tesseract, sem LM Studio):
python main.py documento.pdf --ocr-mode classic_only

# Modo IA (so LM Studio):
python main.py documento.pdf --ocr-mode ai_only

# Modo legado (comportamento original):
python main.py documento.pdf --ocr-mode legacy

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
| `--ocr-mode` | `legacy`, `hybrid`, `classic_only`, `ai_only` | `hybrid` |
| `--classic-engine` | Motor clasico: `tesseract` | (env CLASSIC_OCR_ENGINE ou `tesseract`) |
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
├── requirements.txt           # Dependencias Python
├── SKILL.md                   # Definicao da skill (opencode / Claude Code)
├── .env.example               # Template de variaveis de ambiente
├── ocr_engine/                # Motores de OCR
│   ├── base.py                # Interface OCREngineBase
│   ├── config.py              # HybridOCRConfig
│   ├── quality.py             # QualityScorer
│   ├── router.py              # OCRRouter
│   ├── ai_engine.py           # AIEngine (GLM-OCR)
│   ├── tesseract_engine.py    # TesseractEngine
│   └── text_stats.py          # Tokenizacao e estatisticas
├── models/                    # Configuracoes dos modelos
│   ├── chandra-ocr-2/
│   ├── glm-ocr/
│   └── template/
└── saida_ocr/                 # Diretorio de saida (gerado)
```

## Modelos Disponiveis

| Modelo | Formato | System Prompt | Ref. Texto Nativo |
|--------|---------|---------------|-------------------|
| `chandra-ocr-2` | HTML → convertido para MD | Sim | Sim |
| `glm-ocr` | Markdown diretamente | Nao | Nao |

Para adicionar um novo modelo, copie `models/template/` e edite `config.json` e `prompts.py`.

## Troubleshooting

**Tesseract not found**: Instale o binary e/ou defina `TESSERACT_CMD` environment variable apontando para o executavel.

**LM Studio offline**: Se estiver no modo `hybrid` com Tesseract, o sistema tenta OCR clasico antes de fallback.

**Fidelity PARTIAL**: Aumente `--dpi` para 300-400 ou use `--ocr-mode hybrid` para fallback para IA.
