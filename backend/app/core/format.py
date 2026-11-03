"""Números em pt-BR para textos (indicadores, descobertas e alertas)."""


def number(value: float | None, decimals: int = 0) -> str:
    if value is None:
        return "–"
    text = f"{value:,.{decimals}f}"
    return text.replace(",", "X").replace(".", ",").replace("X", ".")


def signed_pct(value: float | None, decimals: int = 1) -> str:
    if value is None:
        return "–"
    return ("+" if value > 0 else "") + number(value, decimals) + "%"
