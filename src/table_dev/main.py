import supervisely as sly

from src.components.project_table.project_table import ProjectTable

__import__("dotenv").load_dotenv("local.env")
api = sly.Api.from_env()
project_table = ProjectTable(team_id=sly.env.team_id())
layout = sly.app.widgets.Container([project_table])
app = sly.Application(layout, static_dir="./src/components/project_table/static/")
