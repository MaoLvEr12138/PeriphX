import typer
import yaml
from pathlib import Path
from mlr.builder import run_altera_flow

app = typer.Typer(help="PeriphX 管理工具 (Mlr)")

def get_userWorkspace() -> Path:
    return Path(__file__).resolve().parent.parent / "userSpace"

@app.command(help="从 userSpace/manifest.yaml 读取配置并拉起编译")
def build():
    workspace_dir = get_userWorkspace()
    manifest_path = workspace_dir / "manifest.yaml"
    
    if not manifest_path.exists():
        typer.echo(f"❌ 错误: 找不到配置文件 {manifest_path}", err=True)
        raise typer.Exit(code=1)
        
    with open(manifest_path, "r", encoding="utf-8") as file:
        try:
            data = yaml.safe_load(file)
        except Exception as e:
            typer.echo(f"❌ YAML 文件语法解析失败: {e}", err=True)
            raise typer.Exit(code=1)
            
    # 引导进入平台适配编译流
    run_altera_flow(workspace_dir, data)

if __name__ == "__main__":
    app()