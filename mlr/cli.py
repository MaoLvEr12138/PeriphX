import typer

app = typer.Typer()

@app.command()
def validate():
    print("validate")


@app.command()
def build():
    print("build")