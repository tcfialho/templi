# Templi (Python Implementation)

Uma implementação em Python para aplicar plugins YAML em projetos.

## Funcionalidades
*   Compatível com schema v2 e v3 de plugins YAML.
*   **Fallback V2:** Detecta e renderiza automaticamente `templates/` para plugins legados sem hooks.
*   **Script Runner:** Executa scripts Python usando um mock de `templateframework` para compatibilidade com plugins legados.
*   Suporta hooks: `run-script`, `render-templates`, `edit`.
*   Suporta inputs interativos e não-interativos.
*   Validação de compatibilidade com plugins legados e fixtures completas.
*   Correções de lacunas como `line: -N` e `replace-by: snippet`.

## Como Usar

### 1. Aplicar Plugin
```bash
python -m templi.main apply plugin "c:\caminho\para\o\plugin"
```

### 2. Opções CLI
*   `-s`, `--skip-warning`: Ignorar aviso de workspace.
*   `-q`, `--non-interactive`: Modo não interativo (requer inputs via linha de comando ou JSON).
*   `--input-name valor`: Passar inputs diretamente.
*   `--inputs-json '{"key": "value"}'`: Passar inputs em JSON.

### 3. Nome de Compatibilidade
Por padrão, o Templi mantém o estado local em `.templi/manifest.yaml` e injeta as variáveis de runtime `TEMPLI_PLUGIN_DIR` e `TEMPLI_PROJECT_DIR` em hooks `run-script`.

Para compatibilidade com outro nome de runtime, defina `TEMPLI_COMPAT_NAME`. Quando configurado, o valor é usado em minúsculas para o diretório local e em maiúsculas para o prefixo das variáveis de ambiente:

```bash
TEMPLI_COMPAT_NAME=minha_ferramenta
```

Resultado:

```text
.minha_ferramenta/manifest.yaml
MINHA_FERRAMENTA_PLUGIN_DIR
MINHA_FERRAMENTA_PROJECT_DIR
```

Se `TEMPLI_COMPAT_NAME` não existir ou estiver vazio, o comportamento padrão continua sendo `.templi/` e `TEMPLI_*`. O valor deve começar com letra e conter apenas letras, números ou `_`.

### 4. Executar Testes
```bash
python -m pytest tests/
```

## Estrutura do Projeto
*   `src/templi`: Código fonte.
*   `tests`: Testes automatizados (237 testes).
*   `specs`: Especificações detalhadas.

## Relatórios de Compatibilidade
Consulte `COMPATIBILITY_REPORT.md` e `FINAL_COMPATIBILITY_REPORT.md` na raiz do workspace para detalhes sobre a cobertura de funcionalidades.
