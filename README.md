# Document OCR + LM Studio Pipeline

Pipeline OCR completo para converter PDFs, imagens, DOCX, PPTX e HTML em Markdown/HTML/JSON estruturado. Usa LM Studio para OCR de PDFs/imagens e extracao nativa para DOCX/PPTX/HTML.

## Arquitetura

```
PDF/Imagem → PyMuPDF (render) → LM Studio (API multimodal) → HTML/Markdown
                ↓
         texto nativo (referência, via fitz/PyMuPDF)

DOCX/PPTX/HTML → Extracao nativa (python-docx / python-pptx / html2text) → Markdown
```

### OCR (PDFs e imagens):
1. Renderiza cada pagina do PDF em imagem (via PyMuPDF)
2. Extrai texto nativo como referencia (se disponivel)
3. Codifica a imagem como **JPEG qualidade 95 otimizado** (~5-10x menor que PNG) e envia para o modelo OCR via API multimodal
4. Modelo retorna HTML ou Markdown (dependendo do modelo)
5. Pipeline converte HTML → Markdown se necessario e salva o `.md` final

### Extracao nativa (DOCX, PPTX, HTML):
1. Extrai o texto diretamente do arquivo usando bibliotecas especializadas
2. Preserva estrutura: titulos, paragrafos, tabelas, listas
3. Salva diretamente sem necessidade de OCR ou LM Studio

## Instalação

```bash
python -m venv venv
.\venv\Scripts\activate   # Windows
# source venv/bin/activate  # Linux

pip install -r requirements.txt
```

## Configuração

1. Copie o arquivo `.env.example` para `.env` e ajuste se necessário:

```bash
copy .env.example .env
```

### Usando o LM Studio com múltiplos modelos

O LM Studio carrega **apenas um modelo por vez**. Para alternar:

1. Abra o LM Studio, vá em "Local Inference Server"
2. No dropdown "Model", selecione o modelo desejado (`chandra-ocr-2`, `glm-ocr`, etc.)
3. Clique **"Start Server"** (ou "Restart Server")
4. Confirme que a URL `http://localhost:1234/v1` esta online

O nome exato no dropdown do LM Studio deve bater com o campo `lmstudio_model` no `config.json` do modelo (ex: `models/chandra-ocr-2/config.json` → `"lmstudio_model": "chandra-ocr-2"`).

### Descobrir a URL/Nome do modelo no LM Studio

- **URL**: Na aba "Local Inference Server" — padrão `http://localhost:1234/v1`. Se mudou a porta, ajuste `LMSTUDIO_BASE_URL` no `.env`.
- **Nome do modelo**: Aparece no dropdown ao lado do botão "Start Server". Use esse nome exato em `lmstudio_model` no `config.json` do modelo.

## Uso

```bash
# O modelo e perguntado interativamente se nao especificado:
python main.py documento.pdf --out "DIR_DO_INPUT/saida_ocr" --format markdown

# PDF → Markdown com modelo especifico
python main.py documento.pdf --out "DIR_DO_INPUT/saida_ocr" --format markdown --model chandra-ocr-2

# PDF → Markdown com maior fidelidade (300 DPI)
python main.py documento.pdf --out "DIR_DO_INPUT/saida_ocr" --format markdown --dpi 300

# PDF → HTML + JSON
python main.py documento.pdf --out "DIR_DO_INPUT/saida_ocr" --format html json

# PDF → Markdown, só OCR (ignora texto embutido)
python main.py documento.pdf --out "DIR_DO_INPUT/saida_ocr" --format markdown --mode ocr-only

# Retomar processamento interrompido
python main.py documento.pdf --out "DIR_DO_INPUT/saida_ocr" --format markdown --resume

# Documentos longos (aumenta timeout)
python main.py documento.pdf --out "DIR_DO_INPUT/saida_ocr" --format markdown --timeout 600

# Imagem única
python main.py pagina.png --out "DIR_DO_INPUT/saida_ocr" --format markdown

# Nome personalizado para saída
python main.py documento.pdf --out "DIR_DO_INPUT/saida_ocr" --format markdown --output-name meuarquivo

# DOCX → Markdown (extracao nativa, sem OCR)
python main.py documento.docx --out "DIR_DO_INPUT/saida_ocr" --format markdown

# PPTX → Markdown (extracao nativa)
python main.py apresentacao.pptx --out "DIR_DO_INPUT/saida_ocr" --format markdown

# HTML → Markdown (extracao nativa)
python main.py pagina.html --out "DIR_DO_INPUT/saida_ocr" --format markdown
```
> **Nota:** `DIR_DO_INPUT` e o diretorio onde o arquivo de entrada esta localizado. A saida sempre vai para uma pasta `saida_ocr/` ao lado do arquivo original, nunca dentro da skill.

## Argumentos CLI

| Argumento | Descrição | Default |
|-----------|-----------|---------|
| `input` | Caminho do PDF, imagem (.png/.jpg/.jpeg), DOCX, PPTX ou HTML | obrigatório |
| `--model` | Modelo de OCR (ex: `chandra-ocr-2`) | perguntado interativamente |
| `--out` | Diretório de saída (recomendado: `DIR_DO_INPUT/saida_ocr`) | `output/` |
| `--output-name` | Nome do arquivo de saída (sem extensão) | (nome do input) |
| `--format` | Formato(s): `markdown`, `html`, `json` | `markdown` |
| `--mode` | `text-first` ou `ocr-only` | `text-first` |
| `--dpi` | Resolução de renderização do PDF | `200` |
| `--resume` | Retomar processamento parcial | `false` |
| `--lmstudio-url` | URL base da API | `env` ou `http://localhost:1234/v1` |
| `--lmstudio-model` | Nome do modelo no LM Studio (overrides config) | do `config.json` do modelo |
| `--lmstudio-api-key` | Chave da API | `env` ou vazio |
| `--timeout` | Timeout por requisição (s) | `300` |
| `--retries` | Máximo de tentativas por página | `3` |

## Modelos Disponiveis

Os modelos ficam em `models/`, cada um com seu `config.json` e `prompts.py`.

| Modelo | Descricao |
|--------|-----------|
| `chandra-ocr-2` | Modelo especializado em OCR via LM Studio. Retorna HTML estruturado. |
| `glm-ocr` | GLM-OCR (Zhipu AI). Retorna Markdown diretamente. Nao requer system prompt. |

Para adicionar um novo modelo, copie a pasta `models/template/` e edite `config.json` e `prompts.py`.

## Comportamento do OCR

O comportamento depende do modelo escolhido (veja `models/`):

- **Modelos HTML** (ex: `chandra-ocr-2`): retornam HTML. Pipeline converte para Markdown.
- **Modelos Markdown** (ex: `glm-ocr`): retornam Markdown diretamente. Pipeline salva sem conversao.

**O agente (assistente) deve revisar e polir o `.md` final** (ajustar quebras de linha, verificar tabelas, remover resíduos).

## Saída

Para `documento.pdf` com `--format markdown`, a saida vai para `DIR_DO_INPUT/saida_ocr/`:

```
DIR_DO_INPUT/
└── saida_ocr/
    └── documento.md          # Markdown final
```

Se `--format markdown html`:

```
DIR_DO_INPUT/
└── saida_ocr/
    ├── documento.md
    └── documento.html
```

Onde `DIR_DO_INPUT` e o diretorio do arquivo processado (ex: `C:\Users\...\Desktop`).

Arquivos temporarios (`.partial`, `.metadata.json`) sao removidos automaticamente ao final com sucesso.

## Troubleshooting

**"LM Studio endpoint offline"**: Verifique se o servidor está rodando no LM Studio (botão "Start Server") e se a URL está correta.

**Primeira página faltando**: Se o modelo retornar vazio para a página 1, aumente `--timeout` para 600s. O pipeline sempre envia a imagem agora.

**HTML com data-bbox na saída**: O prompt proíbe atributos HTML e o `_html_to_markdown()` remove `data-*` como fallback.

**Modelo inventa conteúdo**: O system prompt tem regras anti-hallucination. Se persistir, tente `--mode ocr-only`.

**Erro 400 / formato multimodal**: O LM Studio pode exigir ajustes no payload. O pipeline usa **JPEG qualidade 95** para minimizar o tamanho das requisicoes. Se precisar voltar para PNG, edite `lmstudio_client.py`, metodo `_encode_image()`.

**"ModuleNotFoundError: No module named 'docx'"**: Instale as dependencias para formatos nativos: `pip install python-docx python-pptx html2text beautifulsoup4`

**GPU AMD**: A aceleração AMD é gerenciada pelo LM Studio. O pipeline Python é agnóstico de GPU.
