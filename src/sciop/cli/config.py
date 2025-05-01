import secrets
import sys
from pathlib import Path

import click
import yaml as pyyaml
from pydantic import ValidationError
from rich import print
from rich.console import Group
from rich.markdown import Markdown
from rich.panel import Panel
from ruamel.yaml import YAML

from sciop.cli.common import config_option
from sciop.config import Config
from sciop.helpers import flatten_dict, merge_dicts, unflatten_dict, validate_field


@click.group("config", invoke_without_command=True)
@click.pass_context
@config_option
def config(ctx: click.Context, config: Path | None = None) -> None:
    """
    Get and set sciop config variables.

    Shows current configuration, reading from local config file
    and showing defaults.
    """
    if ctx.invoked_subcommand is not None:
        return

    cfg = Config.load(Path(config)) if config else Config()

    # flatten and unflatten the dict to separate defaults from explicitly set
    all_cfg = cfg.model_dump(mode="json")
    all_flat = flatten_dict(all_cfg)

    no_defaults = cfg.model_dump(exclude_defaults=True, mode="json")
    no_defaults_flat = flatten_dict(no_defaults)

    defaults_flat = {k: all_flat[k] for k in all_flat.keys() - no_defaults_flat.keys()}
    defaults = unflatten_dict(defaults_flat)

    panels = []
    if no_defaults:
        if config:
            config_file = str(config)
        elif Path(".env").exists() and Path("sciop.yaml").exists():
            config_file = "sciop.yaml + .env"
        elif Path(".env").exists():
            config_file = ".env"
        elif Path("sciop.yaml").exists():
            config_file = "sciop.yaml"
        else:
            # should be impossible but...
            config_file = ""

        no_def_yaml = pyyaml.dump(no_defaults, sort_keys=True, default_flow_style=False, indent=2)

        panels.append(
            Panel(
                Markdown(
                    f"""```yaml
{no_def_yaml}
```"""
                ),
                title=config_file,
            )
        )

    def_yaml = pyyaml.safe_dump(defaults, sort_keys=True, default_flow_style=False, indent=2)
    panels.append(
        Panel(
            Markdown(
                f"""```yaml
{def_yaml}
```"""
            ),
            title="Defaults",
        )
    )

    print(Group(*panels))


@config.command("set")
@config_option
@click.argument("args", nargs=-1)
def config_set(args: list[str], config: Path | None = None) -> None:
    """
    Set a config variable in sciop.yaml

    See the [Config docs][sciop.config.Config] for all available options

    Set values as key/value pairs like

    ```
    sciop config set env=dev base_url=https://example.com
    ```

    Nested keys can be passed with '.' as a delimiter:

    ```
    sciop config set logs.level=INFO
    ```
    """
    if not args:
        click.echo("No args set!")
        sys.exit(0)

    yaml = YAML(typ="rt")
    yaml.default_flow_style = False

    if config is None:
        config = Path.cwd() / "sciop.yaml"

    kwargs_flat = dict(item.split("=") for item in args)

    # validate against individual fields
    for k, v in kwargs_flat.items():
        try:
            kwargs_flat[k] = validate_field(k, v, Config)
        except ValidationError as e:
            # show without traceback
            print(e)
            sys.exit(1)

    kwargs = unflatten_dict(kwargs_flat)

    cfg = yaml.load(config) if config.exists() else {}
    # don't flatten dict to merge, want to preserve comments
    cfg = merge_dicts(cfg, kwargs)

    with open(config, "w") as f:
        yaml.dump(cfg, f)

    print("Updated config:")
    print(kwargs)


@config.command("copy")
@click.option(
    "-o",
    "--output",
    type=click.Path(dir_okay=False),
    required=False,
    help="Path to output sciop.yaml file. If none, use cwd",
)
@click.option(
    "-f", "--force", default=False, is_flag=True, help="Force overwrite of existing config file"
)
@click.option(
    "-e",
    "--env",
    default="dev",
    show_default=True,
    type=click.Choice(["dev", "prod", "test"]),
    help="Environment to copy",
)
def config_copy(output: Path | None = None, force: bool = False, env: str = "dev") -> None:
    """
    Create a new sciop.yaml config from the defaults,
    autogenerating a secret key and using env=dev by default.

    After creating a config, `use sciop config set` to set values
    (or, yno, edit it in a text editor)
    """
    secret_key = secrets.token_hex(32)
    output = Path.cwd() / "sciop.yaml" if output is None else Path(output)

    if output.exists() and not force:
        raise FileExistsError(f"{output} already exists, use --force to overwrite")

    cfg = Config(secret_key=secret_key, env=env)
    dumped = cfg.model_dump(mode="json")
    # we actually do want to include the secret keys here
    dumped["secret_key"] = cfg.secret_key.get_secret_value()
    dumped["root_password"] = cfg.root_password.get_secret_value()
    with open(output, "w") as f:
        pyyaml.safe_dump(dumped, f, sort_keys=False)

    click.echo(f"Created default config at {str(output.resolve())}")
