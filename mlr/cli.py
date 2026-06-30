import typer
import yaml
from pathlib import Path

app = typer.Typer()

@app.command()
def validate():
    with open(Path(__file__).resolve().parent.parent / "tests" / "manifest.yaml", "r", encoding="utf-8") as file:
        data = yaml.safe_load(file)

    print(data)


@app.command()
def build():
    print("build")


if __name__ == "__main__":
    app()