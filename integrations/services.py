from integrations.client import GreenwhiteClient


class GreenwhiteService:
    def __init__(self):
        self.client = GreenwhiteClient()

    def get_raw_session_data(self):
        return self.client.get_session_data()

    def get_session_summary(self):
        data = self.get_raw_session_data()

        project_code = None
        filials = []

        projects = data.get("projects", [])
        if projects:
            first_project = projects[0]
            project_code = first_project.get("code")

            raw_filials = first_project.get("filials", [])
            for item in raw_filials:
                if len(item) >= 2:
                    filials.append({
                        "id": item[0],
                        "name": item[1],
                    })

        return {
            "user": data.get("user", {}),
            "company_name": data.get("company_name"),
            "company_code": data.get("company_code"),
            "init_project": data.get("settings", {}).get("init_project"),
            "init_filial": data.get("settings", {}).get("init_filial"),
            "project_code": project_code,
            "filials": filials,
        }

    def get_info(self):
        data = self.get_raw_session_data()

        return {
            "company_name": data.get("company_name"),
            "company_code": data.get("company_code"),
            "lang_code": data.get("lang_code"),
            "country_code": data.get("country_code"),
        }

    def get_sections(self):
        data = self.get_session_summary()

        return {
            "project_code": data.get("project_code"),
            "filials": data.get("filials", []),
        }