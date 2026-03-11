from bs4 import BeautifulSoup


class SalesSummaryParser:

    @staticmethod
    def parse(html: str):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="bsr-table")

        if not table:
            return {
                "meta": {},
                "columns": [],
                "rows": [],
                "totals": {},
            }

        text_rows = []

        for row in table.find_all("tr"):
            cells = row.find_all(["td", "th"])
            values = [cell.get_text(" ", strip=True) for cell in cells]

            if values:
                text_rows.append(values)

        meta = {
            "status": text_rows[0][0].replace("Статус:", "").strip() if len(text_rows) > 0 else "",
            "inventory_kind": text_rows[1][0].replace("Тип ТМЦ:", "").strip() if len(text_rows) > 1 else "",
            "date_range": text_rows[2][0].replace("Дата заказа:", "").strip() if len(text_rows) > 2 else "",
        }

        columns = []

        if len(text_rows) >= 5:
            top_header = text_rows[3]
            second_header = text_rows[4]

            if len(top_header) >= 4 and len(second_header) >= 4:
                columns = [
                    second_header[0],
                    top_header[1],
                    top_header[2],
                    top_header[3],
                ]

        rows = []
        totals = {}

        for row in text_rows[5:]:
            if len(row) < 4:
                continue

            item = {
                "sales_manager": row[0],
                "usd": row[1],
                "uzs": row[2],
                "total": row[3],
            }

            if row[0].strip().upper() == "ИТОГО":
                totals = item
            else:
                rows.append(item)

        return {
            "meta": meta,
            "columns": columns,
            "rows": rows,
            "totals": totals,
        }