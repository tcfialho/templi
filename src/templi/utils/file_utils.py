"""Utilitários de arquivo para o templi."""

import os
import shutil


def ensure_directory(path: str) -> None:
    """Cria diretório se não existir (incluindo pais)."""
    os.makedirs(path, exist_ok=True)


def read_file(path: str) -> str:
    """Lê conteúdo de arquivo como string UTF-8."""
    with open(path, "r", encoding="utf-8") as file_handle:
        return file_handle.read()


def write_file(path: str, content: str) -> None:
    """Escreve conteúdo em arquivo UTF-8 (cria dirs se necessário)."""
    parent_directory = os.path.dirname(path)
    if parent_directory:
        ensure_directory(parent_directory)
    with open(path, "w", encoding="utf-8") as file_handle:
        file_handle.write(content)


def copy_file(source: str, target: str) -> None:
    """Copia arquivo preservando conteúdo."""
    parent_directory = os.path.dirname(target)
    if parent_directory:
        ensure_directory(parent_directory)
    shutil.copy2(source, target)


def is_binary_file(file_path: str) -> bool:
    """Detecta se arquivo é binário (imagens, etc.)."""
    try:
        with open(file_path, "rb") as file_handle:
            chunk = file_handle.read(8192)
            return b"\x00" in chunk
    except OSError:
        return False


def read_text_or_detect_binary(file_path: str) -> str | None:
    """Lê arquivo uma única vez, decidindo entre texto e binário.

    Returns:
        str decodificada em UTF-8 se texto, com newlines normalizadas
        para "\\n" (equivalente ao universal-newlines do modo texto);
        None se binário (heurística: \\x00 nos primeiros 8KB).
    """
    with open(file_path, "rb") as file_handle:
        head = file_handle.read(8192)
        if b"\x00" in head:
            return None
        rest = file_handle.read()
    text = (head + rest).decode("utf-8")
    return text.replace("\r\n", "\n").replace("\r", "\n")
