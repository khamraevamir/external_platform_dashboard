from integrations.utils.numbers import parse_number


def calculate_converted_total_usd(usd, uzs, sell_rate):
    usd = parse_number(usd)
    uzs = parse_number(uzs)
    sell_rate = parse_number(sell_rate)

    if sell_rate <= 0:
        raise ValueError("Invalid sell rate")

    return round(usd + (uzs / sell_rate), 2)