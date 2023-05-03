import click
from contextlib import contextmanager
from requests.exceptions import HTTPError

from .apt import check_apt_repo
from .utils import RepoErrors, destroy_gpg, initialize_gpg, output_result, get_repo_urls
from .yum import check_yum_repo

recursive_option = click.option(
    "--recursive",
    "-r",
    is_flag=True,
    help=(
        "Attempt to recursively check repos. Requires URL to point to a directory "
        "listing with links to the repos."
    ),
)

file_option = click.option(
    "--output",
    "-o",
    help=(
        "Output results to a specified json file (e.g. output.json)"
    ),
)

pubkey_option = click.option(
    "--pubkeys",
    "-p",
    help=(
        "Comma separated list of the url of public keys. "
        "When provided, signatures will be verified to make "
        "sure they match one of the public keys."
    )
)

apt_sources_option = click.option(
    "--apt-source",
    "-a",
    required=False,
    help=(
        "Supply apt sources.list file. When provided, all entries"
        "will be parsed for repo urls and their respective dists."
    )
)

def apt_helper(recursive: bool, url: str, dists: str, output: str, pubkeys: str) -> None:
    """Helps apt function validate an apt repository at url"""
    if recursive:
        urls = get_repo_urls(url)
    else:
        urls = [url]

    if dists:
        dist_set = set(dists.split(","))
    else:
        dist_set = None

    errors = RepoErrors()

    with _gpg_cmdline(pubkeys) as gpg:
        try:
            for repo_url in urls:
                check_apt_repo(repo_url, dist_set, gpg, errors)
        except KeyboardInterrupt:
            pass

    output_result(errors, output)

@contextmanager
def _gpg_cmdline(pubkeys: str):
    gpg = None
    if pubkeys:
        try:
            gpg = initialize_gpg(pubkeys.split(","))
        except HTTPError as e:
            raise click.ClickException(
                f"{e}\n"
                "Please check the url for the public key"
            )
    try:
        yield gpg
    finally:
        destroy_gpg(gpg)


@click.group()
def main() -> None:
    """Audit a repo by validating its repo metadata and packages."""
    pass


@main.command()
@recursive_option
@click.argument("url")
@click.option("--dists", help="Comma separated list of distributions.")
@apt_sources_option
@file_option
@pubkey_option
def apt(recursive: bool, url: str, dists: str, apt_source: str, output: str, pubkeys: str) -> None:
    """Validate an apt repository at URL."""
    if apt_source:
        with open(apt_source, "r") as f:
            lines = [line.strip() for line in f if line.startswith("deb")]
            for line in lines:
                fields = line.split(" ")
                _url = fields[1]
                _dists = ','.join(fields[slice(2, len(fields))])
                apt_helper(recursive, _url, _dists, output, pubkeys)
    else:
        apt_helper(recursive, url, dists, output, pubkeys)


@main.command()
@recursive_option
@click.argument("url")
@file_option
@pubkey_option
def yum(recursive: bool, url: str, output: str, pubkeys: str) -> None:
    """Validate a yum repository at URL."""
    if recursive:
        urls = get_repo_urls(url)
    else:
        urls = [url]

    errors = RepoErrors()

    with _gpg_cmdline(pubkeys) as gpg:
        try:
            for repo_url in urls:
                check_yum_repo(repo_url, gpg, errors)
        except KeyboardInterrupt:
            pass

    output_result(errors, output)
