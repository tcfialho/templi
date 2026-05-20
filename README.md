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

### 3. Executar Testes
```bash
python -m pytest tests/
```

## Estrutura do Projeto
*   `src/templi`: Código fonte.
*   `tests`: Testes automatizados (197 testes).
*   `specs`: Especificações detalhadas.

## Relatórios de Compatibilidade
Consulte `COMPATIBILITY_REPORT.md` e `FINAL_COMPATIBILITY_REPORT.md` na raiz do workspace para detalhes sobre a cobertura de funcionalidades.
