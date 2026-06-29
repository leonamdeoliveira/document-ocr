---
name: document-ocr
description: Leitura de PDFs, imagens, DOCX, PPTX e HTML usando OCR via LM Studio, OCR clasico (Tesseract/PaddleOCR) ou extracao nativa de texto. Converte documentos para Markdown/HTML/JSON estruturado. Use quando o usuario pedir para "ler PDF", "extrair texto de imagem", "converter documento", "ler DOCX", "ler PPT", "ler HTML", "OCR" ou "transformar PDF em markdown".
---

# Document OCR - Pipeline de Leitura de Documentos

Converte PDFs e imagens em texto estruturado (Markdown/HTML/JSON) usando pipeline hibrido: OCR clasico (Tesseract, PaddleOCR) para documentos simples ou IA multimodal via LM Studio para documentos complexos.

## Quando Usar (Disparo Automatico)

Esta skill DEVE ser ativada automaticamente SEMPRE que:

- Usuario pede "leia este PDF", "leia esta imagem", "extraia o texto desse PDF", "converta PDF para markdown"
- Usuario menciona "ler" + "PDF", "ler" + "imagem", "ler" + "documento", "extrair texto", "OCR"
- Usuario **envia/cola/arrasta** um arquivo no chat com extensao `.pdf`, `.png`, `.jpg`, `.jpeg`, `.docx`, `.pptx`, `.html`, `.htm`
- Usuario pede "leia este DOCX", "leia este PowerPoint", "leia este HTML", "extraia texto do DOCX"
- Usuario quer OCR de documentos com preservacao de estrutura (tabelas, listas, titulos)
- Usuario menciona "Chandra OCR", "LM Studio", "OCR documento", "Tesseract", "OCR clasico"

**Nao pergunte ao usuario se ele quer usar OCR. Simplesmente ative a skill e processe o arquivo.**

**Nota:** Para `.docx`, `.pptx` e `.html`, a extracao de texto e **nativa** (sem OCR), pois esses formatos ja possuem texto selecionavel.

## Estrutura da Skill

```
SKILL_DIR/
├── SKILL.md                   # Este arquivo
├── main.py                    # CLI principal (ponto de entrada)
├── model_loader.py            # Carregamento de config/prompts dos modelos
├── native_extractor.py        # Extracao nativa de DOCX, PPTX, HTML
├── ocr_pipeline.py            # Orquestracao do pipeline
├── pdf_utils.py               # Renderizacao e extracao de texto
├── lmstudio_client.py         # Cliente HTTP OpenAI-compatible
├── ocr_engine/                # Motores de OCR (novo)
│   ├── __init__.py            # Exports publicos
│   ├── base.py                # Interface OCREngineBase + EngineResult
│   ├── config.py              # HybridOCRConfig
│   ├── quality.py             # QualityScorer (heuristica de qualidade)
│   ├── normalizer.py          # OutputNormalizer (limpeza de OCR)
│   ├── router.py              # OCRRouter (roteamento inteligente)
│   ├── ai_engine.py           # AIEngine (LM Studio / GLM-OCR)
│   ├── tesseract_engine.py    # TesseractEngine (Tesseract + OCRmyPDF)
│   └── paddle_engine.py       # PaddleEngine (PaddleOCR, opcional)
├── requirements.txt           # Dependencias
├── .env.example               # Template de configuracao
├── README.md                  # Documentacao
├── tasks/                     # Planos de implementacao
└── models/                    # Modelos de OCR
    ├── chandra-ocr-2/         # Chandra OCR 2 (retorna HTML)
    ├── glm-ocr/               # GLM-OCR (retorna Markdown)
    └── template/              # Template para novos modelos
```

## Instalacao (para um usuario novo)

### 1. Instalar Python 3.10+

```bash
python --version
# Deve mostrar: Python 3.10.x ou superior
```

### 2. Instalar LM Studio e modelos de OCR (para modo IA)

Baixe o LM Studio em: https://lmstudio.ai/

Apos instalar e abrir:
1. Va na aba "Search" e busque pelo modelo desejado (ex: `chandra-ocr-2`, `glm-ocr`)
2. Baixe o modelo
3. Va em "Local Inference Server", selecione o modelo e clique "Start Server"

### 3. Instalar Tesseract (para OCR clasico, Windows)

```powershell
winget install -e --id UB-Mannheim.TesseractOCR
```

Ou baixe manualmente de: https://github.com/UB-Mannheim/tesseract/wiki

### 4. Instalar dependencias do pipeline

```bash
pip install -r requirements.txt

# Opcionais para OCR clasico:
pip install pytesseract
# pip install ocrmypdf     # Para processamento de PDFs
# pip install paddleocr    # Para PaddleOCR (fallback alternativo)
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

- Formatos suportados:
  - **OCR via IA** (LM Studio): `.pdf`, `.png`, `.jpg`, `.jpeg`
  - **OCR clasico** (Tesseract/PaddleOCR): `.pdf`, `.png`, `.jpg`, `.jpeg`
  - **Extracao nativa** (sem OCR): `.docx`, `.pptx`, `.html`, `.htm`
- Valide que o arquivo existe antes de prosseguir

### Passo 2: Escolher o Modo de OCR

O pipeline tem **4 modos de operacao**:

| Modo | Descricao | Quando usar |
|------|-----------|-------------|
| `legacy` (padrao) | IA via LM Studio (comportamento original) | Documentos complexos, quando LM Studio esta rodando |
| `hybrid` | Tenta Tesseract primeiro, fallback para IA se qualidade baixa | Uso geral, equilibrio entre velocidade e qualidade |
| `classic_only` | So OCR clasico (Tesseract/Paddle), sem IA | Documentos simples, quando LM Studio nao esta disponivel |
| `ai_only` | So IA (como legacy) | Documentos complexos, mesma prioridade do legacy |

**Regra de decisao para o agente:**

- Se LM Studio **nao estiver rodando** e Tesseract estiver disponivel: use `--ocr-mode classic_only`
- Se LM Studio estiver rodando e o documento for **simples** (texto claro, layout padrao): use `--ocr-mode hybrid`
- Se LM Studio estiver rodando e o documento for **complexo** (tabelas, colunas, qualidade baixa): use `legacy` (padrao) ou `--ocr-mode ai_only`
- Se nao souber, use o padrao (`legacy`) que mantem compatibilidade total

### Passo 3: Executar o Pipeline

**Modo legado (comportamento original, LM Studio obrigatorio):**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH"
```

**Modo hibrido (Tesseract com fallback para IA):**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --ocr-mode hybrid
```

**Modo classico (so Tesseract, sem IA):**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --ocr-mode classic_only
```

**Com parametros customizados:**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" \
    --out "DIR_DO_INPUT/saida_ocr" \
    --format markdown \
    --ocr-mode hybrid \
    --classic-engine tesseract \
    --ocr-langs por+eng \
    --quality-threshold 0.70
```

**Regras para escolha dos parametros:**
- Se o usuario nao especificou formato, use `--format markdown`
- Se o usuario nao especificou modo de OCR, use `legacy` (padrao historico)
- Se o usuario nao especificou `--model`, pergunte: **"Qual o modelo de IA voce quer usar para extrair o texto?"** e liste as opcoes disponiveis
- Diretorio de saida padrao: `DIR_DO_INPUT/saida_ocr`. NUNCA salve dentro da pasta da skill.
- Use `--resume` apenas se ja houver processamento parcial e o usuario quiser retomar

**Comportamento incremental:** O pipeline escreve no arquivo a cada pagina.

### Passo 4: Ler o Resultado

```bash
# Windows:
type "DIR_DO_INPUT/saida_ocr/NOME_DO_INPUT.md"
```

**Voce, agente, DEVE limpar e formatar o arquivo .md final** ao apresentar ao usuario:

1. Leia o arquivo de saida
2. Verifique se o conteudo esta completo e legivel
3. Remova residuos de OCR (caracteres estranhos, linhas de raciocinio)
4. Ajuste cabecalhos e tabelas se necessario
5. Preserve TUDO — numeros, nomes, valores, referencias
6. Se houver `[unclear]`, mantenha como marcacao de texto duvidoso

### Passo 5: Verificar Fidelidade

O pipeline exibe metricas de qualidade ao final:
- Score de qualidade do OCR clasico (quando usado)
- Paginas processadas com sucesso / total
- Resultado: **PASS** ou **PARTIAL**

Se o resultado for **PARTIAL** com OCR clasico, tente aumentar `--dpi` para 300-400 ou mude para `--ocr-mode hybrid` para ativar fallback para IA.

## Opcoes Completas do CLI

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
| `--timeout` | Timeout por requisicao (segundos) | `300` |
| `--retries` | Numero de tentativas por pagina | `3` |

## Estrutura de Saida

```
DIR_DO_INPUT/
└── saida_ocr/
    └── documento.md          # Consolidado final em Markdown
    └── documento.html        # (se --format html)
    └── documento.json        # (se --format json)
```

Arquivos temporarios (`.partial`, `.metadata.json`) sao removidos automaticamente ao final com sucesso.

## Arquitetura Hibrida (OCR Engine)

```
                    ┌──────────────┐
                    │  OCRRouter   │
                    │  (roteador)  │
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
        │  (limpeza de ruido de OCR)          │
        └─────────────────────────────────────┘
```

### Fluxo de Decisao do Router (modo hybrid)

1. Se texto nativo tem qualidade suficiente (`has_meaningful_text`): **usa texto nativo** (gratis, instantaneo)
2. Tenta **Tesseract** (mais rapido): se score >= threshold, aceita
3. Se Tesseract falhar ou score baixo: tenta **PaddleOCR** (se disponivel)
4. Se todos os clasicos falharem: **fallback para IA (GLM-OCR)**

### QualityScorer

Analisa 6 sinais objetivos:
- `alphanumeric_ratio` (35%): proporcao de letras/numeros
- `symbol_ratio` (20%): proporcao de simbolos estranhos
- `avg_line_length` (15%): media de chars por linha
- `empty_line_ratio` (10%): linhas vazias
- `repeated_chars` (10%): repeticoes suspeitas
- `engine_confidence` (10%): confianca do motor (se disponivel)

Thresholds configuracao:
- `>= 0.70`: texto OK, aceitar
- `>= 0.40`: texto mediano, tentar proximo motor
- `< 0.40`: texto ruim, fallback obrigatorio

## Troubleshooting

**"Tesseract not available"**: Instale o Tesseract binary (veja secao Instalacao) e/ou o pacote Python: `pip install pytesseract`

**"Tesseract not in PATH"**: O engine busca automaticamente em `C:\Program Files\Tesseract-OCR\tesseract.exe`. Se instalou em outro local, defina a variavel de ambiente `TESSERACT_CMD`.

**"LM Studio endpoint offline"**: O servidor nao esta rodando. Se estiver no modo `hybrid` com Tesseract disponivel, ele usa OCR clasico. Caso contrario, inicie o LM Studio.

**"Request failed after X attempts"**: Aumente `--timeout` ou verifique se o modelo terminou de carregar no LM Studio.

**"Fidelity: PARTIAL"**: Score de qualidade do OCR clasico abaixo do threshold. Aumente `--dpi` para 300-400 ou use `--ocr-mode hybrid` para ativar fallback para IA.

**"Saida vazia ou incorreta"**: Aumente `--dpi` para 300-400. Se for OCR clasico, tente `--ocr-mode hybrid`.

**GPU AMD**: A aceleracao AMD e gerenciada pelo LM Studio. O pipeline Python e puramente cliente HTTP, sem CUDA.
