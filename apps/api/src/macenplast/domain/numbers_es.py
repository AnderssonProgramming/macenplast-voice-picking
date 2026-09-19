"""Spanish (Colombia) number-to-speech, 0-999, nominal form only.

Per `PLAN.md` section 6's phrase-writing rule, this always produces the
*nominal* (counting) form — "veintiuno", "doscientos" — never a noun-phrase
form with gender/number agreement ("veintiún cajas", "doscientas
unidades"). That sidesteps Spanish grammatical gender entirely: the
catalog only ever needs one clip per number, reused regardless of what's
being counted.
"""

from __future__ import annotations

_UNITS = (
    "cero",
    "uno",
    "dos",
    "tres",
    "cuatro",
    "cinco",
    "seis",
    "siete",
    "ocho",
    "nueve",
)

_TEENS = (
    "diez",
    "once",
    "doce",
    "trece",
    "catorce",
    "quince",
    "dieciséis",
    "diecisiete",
    "dieciocho",
    "diecinueve",
)

_TWENTIES = (
    "veinte",
    "veintiuno",
    "veintidós",
    "veintitrés",
    "veinticuatro",
    "veinticinco",
    "veintiséis",
    "veintisiete",
    "veintiocho",
    "veintinueve",
)

_TENS = {
    30: "treinta",
    40: "cuarenta",
    50: "cincuenta",
    60: "sesenta",
    70: "setenta",
    80: "ochenta",
    90: "noventa",
}

_HUNDREDS = {
    100: "cien",
    200: "doscientos",
    300: "trescientos",
    400: "cuatrocientos",
    500: "quinientos",
    600: "seiscientos",
    700: "setecientos",
    800: "ochocientos",
    900: "novecientos",
}

MIN_SUPPORTED = 0
MAX_SUPPORTED = 999


def number_to_es(n: int) -> str:
    """Render `n` (0-999) as a spoken Spanish nominal number.

    Raises:
        ValueError: if `n` is outside 0-999.
    """
    if not (MIN_SUPPORTED <= n <= MAX_SUPPORTED):
        raise ValueError(f"number_to_es only supports {MIN_SUPPORTED}-{MAX_SUPPORTED}, got {n}")

    if n < 10:
        return _UNITS[n]
    if n < 20:
        return _TEENS[n - 10]
    if n < 30:
        return _TWENTIES[n - 20]
    if n < 100:
        tens_word = _TENS[(n // 10) * 10]
        remainder = n % 10
        return tens_word if remainder == 0 else f"{tens_word} y {_UNITS[remainder]}"
    if n == 100:
        return "cien"

    hundreds_base = (n // 100) * 100
    remainder = n % 100
    # "cien" only stands alone (n == 100, handled above); 101-199 use the
    # "ciento" prefix ("ciento uno", not "cien uno").
    hundreds_word = "ciento" if hundreds_base == 100 else _HUNDREDS[hundreds_base]
    return hundreds_word if remainder == 0 else f"{hundreds_word} {number_to_es(remainder)}"
