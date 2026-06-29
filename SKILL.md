---
name: document-ocr
description: Leitura de PDFs, imagens, DOCX, PPTX e HTML usando OCR hibrido (Tesseract + IA via LM Studio) ou extracao nativa de texto. Converte documentos para Markdown/HTML/JSON estruturado. Use quando o usuario pedir para "ler PDF", "extrair texto de imagem", "converter documento", "ler DOCX", "ler PPT", "ler HTML", "OCR" ou "transformar PDF em markdown". Compatível com opencode, Claude Code, Cursor, GitHub Copilot, Windsurf e outros assistentes de IA.
---

# Document OCR - Pipeline de Leitura de Documentos

Converte PDFs e imagens em texto estruturado (Markdown/HTML/JSON) usando pipeline hibrido inteligente: Tesseract para OCR classico com **avaliacao por referencia** (compara contra texto nativo do PDF) e fallback automatico para IA multimodal via LM Studio quando a qualidade nao atinge o threshold.

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
├── ocr_engine/                # Motores de OCR
│   ├── __init__.py            # Exports publicos
│   ├── base.py                # Interface OCREngineBase + EngineResult
│   ├── config.py              # HybridOCRConfig
│   ├── quality.py             # QualityScorer (heuristica de qualidade)
│   ├── router.py              # OCRRouter (roteamento inteligente)
│   ├── ai_engine.py           # AIEngine (LM Studio / GLM-OCR)
│   └── tesseract_engine.py    # TesseractEngine (com confianca real via image_to_data)
├── requirements.txt           # Dependencias
├── .env.example               # Template de configuracao
├── README.md                  # Documentacao
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
1. Va na aba "Search" e busque pelo modelo desejado (ex: `glm-ocr`)
2. Baixe o modelo
3. Va em "Local Inference Server", selecione o modelo e clique "Start Server"

### 3. Instalar Tesseract (para OCR classico, Windows)

```powershell
winget install -e --id UB-Mannheim.TesseractOCR
```

Ou baixe manualmente de: https://github.com/UB-Mannheim/tesseract/wiki

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

- Formatos suportados:
  - **OCR hibrido** (Tesseract + IA): `.pdf`, `.png`, `.jpg`, `.jpeg`
  - **Extracao nativa** (sem OCR): `.docx`, `.pptx`, `.html`, `.htm`
- Valide que o arquivo existe antes de prosseguir

### Passo 2: Escolher o Modo de OCR

O pipeline tem **3 modos de operacao** (PaddleOCR foi removido):

| Modo | Descricao | Quando usar |
|------|-----------|-------------|
| `hybrid` (padrao) | Tenta Tesseract primeiro com **avaliacao por referencia** (compara contra texto nativo do PDF). Se qualidade < threshold, fallback automatico para IA via LM Studio. | **Sempre usar como padrao.** Equilibrio entre velocidade e qualidade. |
| `legacy` | IA via LM Studio em todas as paginas | Documentos complexos (tabelas, colunas, letras pequenas) quando LM Studio esta rodando |
| `classic_only` | So Tesseract, sem IA e sem fallback | Documentos simples com texto claro, quando LM Studio nao esta disponivel |
| `ai_only` | So IA (equivalente ao legacy) | Documentos complexos, mesma prioridade do legacy |

**Regra de decisao para o agente:**

- **Sempre** use `hybrid` primeiro (padrao). O pipeline:
  1. Tenta texto nativo do PDF (instantaneo)
  2. Se insuficiente, roda Tesseract com confianca real via `image_to_data`
  3. Se houver texto nativo (mesmo que pequeno), **compara OCR contra ele** (vocabulario + numeros)
  4. Se nao houver texto nativo, usa QualityScorer heuristico + confianca real do Tesseract
  5. Se a qualidade nao atingir o threshold (0.70), faz fallback automatico para IA
- Se LM Studio **nao estiver rodando**: o `hybrid` usa Tesseract nas paginas que passarem no teste e avisa claramente se alguma pagina precisar de IA
- Se nao souber, use o padrao (`hybrid`)

### Passo 3: Executar o Pipeline

**Modo hibrido (padrao — Tesseract com avaliacao inteligente + fallback IA):**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH"
```

**Modo legado (LM Studio obrigatorio):**

```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --ocr-mode legacy
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
    --quality-threshold 0.70 \
    --ocr-langs por+eng
```

**Regras para escolha dos parametros:**
- Se o usuario nao especificou formato, use `--format markdown`
- Se o usuario nao especificou modo de OCR, use `hybrid` (padrao)
- Se o usuario nao especificou `--model`, usa `glm-ocr` automaticamente em modos hybrid/classic_only, ou pergunta interativamente em modos legacy/ai_only
- Diretorio de saida padrao: `DIR_DO_INPUT/saida_ocr`. NUNCA salve dentro da pasta da skill.
- Use `--resume` para retomar processamento parcial (util quando algumas paginas precisaram de IA e o LM Studio nao estava disponivel)

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
- Metodo usado por pagina (native, tesseract, ai, lm_studio_needed)
- Qualidade do OCR classico: avaliacao **por referencia** (comparacao com texto nativo) ou **heuristica** (QualityScorer)
- Vocabulario e numeros preservados no documento consolidado
- Resultado: **PASS** ou **PARTIAL**

## Fluxo de Decisao do Router (modo hybrid)

```
1. Texto nativo do PDF >= 50 chars?
   ├─ Sim → USA TEXTO NATIVO (instantaneo, gratuita, melhor qualidade)
   └─ Nao → continua
   
2. Tenta Tesseract (com confianca real via image_to_data)
   
3. Tem texto nativo >= 20 chars?
   ├─ Sim → AVALIACAO POR REFERENCIA:
   │         - Tokeniza OCR e nativo, calcula word recall (70%)
   │         - Extrai numeros, calcula number preservation (30%)
   │         - combined >= threshold? → aceita
   │         - senao → fallback IA
   └─ Nao → AVALIACAO HEURISTICA (QualityScorer):
             - 6 metricas: alfanumericos, simbolos, linha media,
               linhas vazias, repeticoes, confianca Tesseract real
             - score >= threshold? → aceita
             - senao → fallback IA

4. Fallback IA (se habilitado):
   ├─ LM Studio rodando? → processa com GLM-OCR
   └─ LM Studio offline? → avisa usuario + preserva parciais para --resume
```

### QualityScorer (fallback heuristico)

Usado apenas quando **nao ha texto nativo** para comparacao (PDF escaneado/imagem). Analisa 6 sinais:

- `alphanumeric_ratio` (35%): proporcao de letras/numeros
- `symbol_ratio` (20%): proporcao de simbolos estranhos
- `avg_line_length` (15%): media de chars por linha
- `empty_line_ratio` (10%): linhas vazias
- `repeated_chars` (10%): repeticoes suspeitas
- `engine_confidence` (10%): confianca real do Tesseract (agora obtida via `image_to_data`)

Threshold: `>= 0.70` aceita, `< 0.70` fallback para IA.

## Opcoes Completas do CLI

| Argumento | Descricao | Default |
|-----------|-----------|---------|
| `input` | Caminho do PDF, imagem, DOCX, PPTX ou HTML | obrigatorio |
| `--model` | Modelo de OCR (ex: `glm-ocr`) | `glm-ocr` (hybrid/classic_only) ou perguntado (legacy/ai_only) |
| `--out` | Diretorio de saida | `DIR_DO_INPUT/saida_ocr` |
| `--output-name` | Nome do arquivo de saida (sem extensao) | (nome do input) |
| `--format` | Formato(s): `markdown`, `html`, `json` | `markdown` |
| `--mode` | `text-first` ou `ocr-only` | `text-first` |
| `--dpi` | Resolucao de renderizacao do PDF | `200` |
| `--resume` | Retoma processamento interrompido | `false` |
| `--ocr-mode` | `hybrid`, `legacy`, `classic_only`, `ai_only` | `hybrid` |
| `--classic-engine` | Motor classico: `tesseract` | `tesseract` |
| `--ocr-langs` | Idiomas para OCR classico (ex: `por+eng`) | `por+eng` |
| `--quality-threshold` | Score minimo para aceitar OCR (0-1) | `0.70` |
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

Arquivos temporarios (`.partial`, `.metadata.json`) sao removidos automaticamente ao final com sucesso. Se alguma pagina precisar de IA (LM Studio offline), os parciais sao preservados para `--resume`.

## Troubleshooting

**"Tesseract not available"**: Instale o Tesseract binary (veja secao Instalacao) e/ou o pacote Python: `pip install pytesseract`

**"Tesseract not in PATH"**: O engine busca automaticamente em `C:\Program Files\Tesseract-OCR\tesseract.exe`. Se instalou em outro local, defina a variavel de ambiente `TESSERACT_CMD`.

**"LM Studio endpoint offline"**: O servidor nao esta rodando. Se estiver no modo `hybrid` com Tesseract disponivel, ele usa OCR classico nas paginas que passarem no teste de qualidade. Para processar as paginas restantes com IA, inicie o LM Studio.

**"Request failed after X attempts"**: Aumente `--timeout` ou verifique se o modelo terminou de carregar no LM Studio.

**"Fidelity: PASS"**: Todas as paginas processadas com sucesso. Voce pode confiar no resultado.

**"Fidelity: PARTIAL"**: Algumas paginas podem ter qualidade abaixo do ideal.
- Se houver mensagem "LM Studio needed": inicie o LM Studio e execute com `--resume`
- Se nao houver: aumente `--dpi` para 300-400 ou use `--quality-threshold 0.60`

**"LM Studio needed"**: Uma ou mais paginas precisam de IA porque o OCR classico nao atingiu a qualidade minima. Inicie o LM Studio com o modelo de OCR carregado e execute novamente com `--resume`:
```bash
python "SKILL_DIR/main.py" "INPUT_PATH" --resume
```

**"Saida vazia ou incorreta"**: Aumente `--dpi` para 300-400.

**GPU AMD**: A aceleracao AMD e gerenciada pelo LM Studio. O pipeline Python e puramente cliente HTTP, sem CUDA.
