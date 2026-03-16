from bs4 import BeautifulSoup


class RouteAnalysisParser:
    @staticmethod
    def clean_text(value):
        return " ".join(str(value or "").replace("\xa0", " ").split()).strip()

    @classmethod
    def parse(cls, html):
        soup = BeautifulSoup(html, "html.parser")
        table = soup.find("table", class_="bsr-table")

        if not table:
            raise ValueError("Route analysis table not found")

        rows = table.find_all("tr")
        if not rows:
            raise ValueError("Route analysis rows not found")

        title = ""
        data_rows = []
        header_found = False

        for tr in rows:
            cells = tr.find_all("td")
            if not cells:
                continue

            texts = [cls.clean_text(td.get_text(" ", strip=True)) for td in cells]
            normalized = [text.lower() for text in texts if text]

            if not title:
                joined = " ".join(texts)
                if "анализ-маршрута" in joined.lower():
                    title = joined

            if not header_found and "штат" in normalized and "результативность %" in normalized:
                header_found = True
                continue

            if not header_found:
                continue

            first_text = texts[0] if texts else ""
            if first_text.startswith("Итоговое количество визитов по плану"):
                break

            if len(cells) < 10:
                continue

            staff = cls.clean_text(cells[2].get_text(" ", strip=True)) if len(cells) > 2 else ""
            if not staff:
                continue

            # Последние 10 колонок:
            # Количество визитов | План визитов | U | UD | P | PD | X | O | Результативность % | Результативные визиты
            tail_cells = cells[-10:]

            p_value = cls.clean_text(tail_cells[4].get_text(" ", strip=True))
            pd_value = cls.clean_text(tail_cells[5].get_text(" ", strip=True))

            data_rows.append({
                "staff": staff,
                "p": p_value or "0",
                "pd": pd_value or "0",
            })

        return {
            "title": title,
            "rows": data_rows,
        }