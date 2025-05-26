from pathlib import Path
from typing import Any, Optional

import click

from sciop.cli.common import ensure_nonroot, model_options
from sciop.models.system import GunicornConfig, NginxConfig


@click.group("generate")
def generate() -> None:
    """Generate configurations and other sciop artifacts :)"""
    pass


@model_options(NginxConfig)
@click.option(
    "-f", "--force", is_flag=True, default=False, help="Overwrite if the output file exists"
)
@click.option(
    "-o",
    "--output",
    default=None,
    required=False,
    type=click.Path(),
    show_default=True,
    help="Write output to file. If None (default), print to stdout",
)
@generate.command("nginx")
def nginx(output: Optional[Path] = None, force: bool = False, **kwargs: Any) -> None:
    """
    Generate an nginx configuration file for sciop.

    This template assumes that you will be using certbot to get your ssl keys,
    see certbot documentation: https://certbot.eff.org/

    ----------------- Usage -----------------

    Generate the nginx config to some file that the nonroot user can write to,
    then use a root or otherwise acceptable permissioned user to...

    - Copy the generated config to an nginx config directory

        `cp ./sciop.conf /etc/nginx/sites-available/`

    - Symlink the generated config to an enabled directory

        `ln -s /etc/nginx/sites-available/sciop.conf /etc/nginx/sites-enabled/sciop.conf`

    - Test the nginx config and fix any problems!

        `nginx -t`

    - Restart nginx

        `systemctl restart nginx`

    - Generate SSL certificates with certbot:

        `certbot --nginx -d {{ host }}
    """
    if output is not None and output.exists() and not force:
        raise click.ClickException("Output file already exists, use -f to overwrite.")

    ensure_nonroot()
    model = NginxConfig(**kwargs)
    result = model.render()
    if output is None:
        click.echo(result)
    else:
        with open(output, "w") as ofile:
            ofile.write(result)


@model_options(GunicornConfig)
@click.option(
    "-f", "--force", is_flag=True, default=False, help="Overwrite if the output file exists"
)
@click.option(
    "-o",
    "--output",
    default=None,
    required=False,
    type=click.Path(),
    show_default=True,
    help="Write output to file. If None (default), print to stdout",
)
@generate.command("gunicorn")
def gunicorn(output: Optional[Path] = None, force: bool = False, **kwargs: Any) -> None:
    """
    Generate a systemd service file to run gunicorn for production deployment.

    This template should be generated and then installed to systemd in two steps,
    aka do not run this as root, as you should not run anything in sciop as root.

    After generation...

    - Copy the generated config to the systemd services directory
      (e.g. /etc/systemd/system/sciop.service)
    - Enable the service (`systemctl enable sciop`)
    - Start the service (`systemctl start sciop`)

    This template is a relatively standard gunicorn invocation script,
    except it uses the `--preload` flag to ensure that the module-level semaphors
    and other objects are loaded and run only once
    (e.g. to avoid running a separate APscheduler instance in every worker)
    """
    if output is not None and output.exists() and not force:
        raise click.ClickException("Output file already exists, use -f to overwrite.")

    ensure_nonroot()
    kwargs = {k: v for k, v in kwargs.items() if v is not None}
    model = GunicornConfig(**kwargs)
    result = model.render()
    if output is None:
        click.echo(result)
    else:
        with open(output, "w") as ofile:
            ofile.write(result)
