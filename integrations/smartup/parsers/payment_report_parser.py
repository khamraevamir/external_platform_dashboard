from bs4 import BeautifulSoup


class PaymentReportParser:
    @staticmethod
    def clean_text(value):
        return " ".join(str(value or "").replace("\xa0", " ").split()).strip()

    @classmethod
    def parse(cls, html):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="bsr-table")

        if not table:
            raise ValueError("Payment report table not found")

        rows = table.find_all("tr")
        if not rows:
            raise ValueError("Payment report rows not found")

        title = ""
        columns = []
        data_rows = []
        totals = {}

        header_found = False
        totals_started = False

        for tr in rows:
            cells = tr.find_all("td")
            if not cells:
                continue

            texts = [cls.clean_text(td.get_text(" ", strip=True)) for td in cells]

            if not title and len(cells) == 1:
                maybe_title = texts[0]
                if maybe_title.startswith("Оплаты с"):
                    title = maybe_title
                    continue

            if not header_found:
                normalized = [text.lower() for text in texts if text]
                if "ид клиента" in normalized and "сумма" in normalized:
                    columns = [
                        # cls.clean_text(cells[0].get_text(" ", strip=True)),
                        cls.clean_text(cells[1].get_text(" ", strip=True)),
                        cls.clean_text(cells[2].get_text(" ", strip=True)),
                        cls.clean_text(cells[3].get_text(" ", strip=True)),
                        cls.clean_text(cells[4].get_text(" ", strip=True)),
                        cls.clean_text(cells[5].get_text(" ", strip=True)),
                        cls.clean_text(cells[6].get_text(" ", strip=True)),
                        cls.clean_text(cells[7].get_text(" ", strip=True)),
                    ]
                    header_found = True
                    continue

            if not header_found:
                continue

            first_text = texts[0] if len(texts) > 0 else ""
            if first_text == "ИТОГО":
                totals_started = True

            if totals_started:
                if len(cells) >= 8:
                    currency = cls.clean_text(cells[6].get_text(" ", strip=True))
                    amount = cls.clean_text(cells[7].get_text(" ", strip=True))

                    if currency:
                        totals[currency] = amount
                continue

            if len(cells) < 8:
                continue

            row = {
                "client_id": cls.clean_text(cells[0].get_text(" ", strip=True)),
                "client": cls.clean_text(cells[1].get_text(" ", strip=True)),
                "tin": cls.clean_text(cells[2].get_text(" ", strip=True)),
                "payment_date": cls.clean_text(cells[3].get_text(" ", strip=True)),
                "collector": cls.clean_text(cells[4].get_text(" ", strip=True)),
                "payment_method": cls.clean_text(cells[5].get_text(" ", strip=True)),
                "currency": cls.clean_text(cells[6].get_text(" ", strip=True)),
                "amount": cls.clean_text(cells[7].get_text(" ", strip=True)),
            }

            if any(row.values()):
                data_rows.append(row)

        return {
            "title": title,
            "columns": columns,
            "rows": data_rows,
            "totals": totals,
        }