def calculate_tax(subtotal: float, rate: float) -> float:
    return round(subtotal * rate, 2)


def receipt(subtotal: float, rate: float) -> str:
    tax = calculate_tax(subtotal, rate)
    return f"subtotal {subtotal:.2f} + tax {tax:.2f} = {subtotal + tax:.2f}"


def invoice_total(subtotal: float, rate: float, fee: float) -> float:
    return subtotal + calculate_tax(subtotal, rate) + fee
