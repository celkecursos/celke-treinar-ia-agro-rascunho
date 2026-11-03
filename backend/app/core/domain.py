"""Dados fixos do domínio: unidades da federação e culturas, com as janelas de safra e os códigos do IBGE."""

import unicodedata
from dataclasses import dataclass


@dataclass(frozen=True)
class State:
    code: int
    acronym: str
    name: str


STATES = [
    State(12, "AC", "Acre"),
    State(27, "AL", "Alagoas"),
    State(16, "AP", "Amapá"),
    State(13, "AM", "Amazonas"),
    State(29, "BA", "Bahia"),
    State(23, "CE", "Ceará"),
    State(53, "DF", "Distrito Federal"),
    State(32, "ES", "Espírito Santo"),
    State(52, "GO", "Goiás"),
    State(21, "MA", "Maranhão"),
    State(51, "MT", "Mato Grosso"),
    State(50, "MS", "Mato Grosso do Sul"),
    State(31, "MG", "Minas Gerais"),
    State(15, "PA", "Pará"),
    State(25, "PB", "Paraíba"),
    State(41, "PR", "Paraná"),
    State(26, "PE", "Pernambuco"),
    State(22, "PI", "Piauí"),
    State(33, "RJ", "Rio de Janeiro"),
    State(24, "RN", "Rio Grande do Norte"),
    State(43, "RS", "Rio Grande do Sul"),
    State(11, "RO", "Rondônia"),
    State(14, "RR", "Roraima"),
    State(42, "SC", "Santa Catarina"),
    State(35, "SP", "São Paulo"),
    State(28, "SE", "Sergipe"),
    State(17, "TO", "Tocantins"),
]
STATES_BY_ACRONYM = {s.acronym: s for s in STATES}
STATES_BY_CODE = {s.code: s for s in STATES}

BRAZIL_CODE = 1


@dataclass(frozen=True)
class Crop:
    """Cultura analisada.

    A janela é o período de chuva que mais pesa na safra do ano `ano` da PAM: meses com `offset = -1` são do ano
    anterior (a soja colhida em 2024 é plantada em outubro de 2023). É uma escolha de método, explicada no README.
    """

    key: str
    name: str
    of: str  # "da soja", "do milho"
    window: tuple[tuple[int, int], ...]  # (deslocamento do ano, mês)
    planting_month: tuple[int, int]
    pam_code: int
    # Produtos da estimativa de safra (LSPA). O milho vem em 1ª e 2ª safra.
    lspa_codes: tuple[int, ...]

    def window_months(self, year: int) -> list[tuple[int, int]]:
        return [(year + offset, month) for offset, month in self.window]


CROPS = {
    "soja": Crop(
        key="soja",
        name="Soja",
        of="da soja",
        window=((-1, 10), (-1, 11), (-1, 12), (0, 1), (0, 2), (0, 3)),
        planting_month=(-1, 10),
        pam_code=40124,
        lspa_codes=(39443,),
    ),
    # Milho somado (1ª e 2ª safra) na PAM; a janela segue a 2ª safra, que é a maior no Centro-Oeste: plantio em
    # janeiro e fevereiro, floração e enchimento até abril. Maio e junho ficam de fora porque são secos todo ano.
    "milho": Crop(
        key="milho",
        name="Milho",
        of="do milho",
        window=((0, 1), (0, 2), (0, 3), (0, 4)),
        planting_month=(0, 2),
        pam_code=40122,
        lspa_codes=(39441, 39442),
    ),
}
CROP_BY_PAM_CODE = {c.pam_code: c for c in CROPS.values()}

LSPA_PRODUCTS = {39441: "milho_1", 39442: "milho_2", 39443: "soja"}
LSPA_PRODUCT_NAMES = {"milho_1": "Milho 1ª safra", "milho_2": "Milho 2ª safra", "soja": "Soja"}

MONTH_NAMES = [
    "janeiro",
    "fevereiro",
    "março",
    "abril",
    "maio",
    "junho",
    "julho",
    "agosto",
    "setembro",
    "outubro",
    "novembro",
    "dezembro",
]
MONTH_ABBR = ["jan", "fev", "mar", "abr", "mai", "jun", "jul", "ago", "set", "out", "nov", "dez"]

# Dia sem chuva para o veranico: menos de 1 mm.
DRY_DAY_MM = 1.0


def normalize(text: str) -> str:
    """Sem acentos, minúsculas e espaços simples: "São  Paulo" == "sao paulo"."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return " ".join(plain.lower().split())


# Vai nos prompts do chat, das descobertas e dos alertas: o modelo não pode confundir os termos.
GLOSSARY = """Termos e fases, para não errar na interpretação:
- Veranico: dias seguidos sem chuva (menos de 1 mm por dia) dentro da janela da safra. É falta de chuva, nunca excesso.
- Desvio da tendência: quanto o rendimento do ano ficou acima ou abaixo da reta de tendência, que sobe com a tecnologia.
- Soja (janela de outubro a março): plantio em outubro e novembro; floração e enchimento de grãos de dezembro a \
fevereiro; colheita a partir de janeiro e fevereiro. Chuva demais na colheita atrasa a colheita e piora o grão.
- Milho 2ª safra (janela de janeiro a abril): plantio em janeiro e fevereiro, logo depois da soja; floração e \
enchimento de grãos em março e abril. Chuva até abril é decisiva; maio e junho são secos todo ano.
- O milho da PAM soma a 1ª e a 2ª safra."""
