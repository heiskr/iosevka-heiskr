#!/usr/bin/env python3
"""Decide whether a new Iosevka build is needed, and describe what to build.

Emits these GitHub Actions step outputs:

    upstream  the upstream repo, so the workflow has a single source of truth
    tag       upstream release tag, e.g. "v34.8.0"
    sha       commit that tag points at, so the build is pinned to an exact tree
    version   tag without the leading "v", used in artifact filenames
    plans     JSON array of build plan names read from private-build-plans.toml
    build     "true" or "false"

Every API call raises on a non-2xx response, so a transient GitHub outage fails
the step rather than being misread as "nothing to build".

Requires Python 3.11 or newer for tomllib. GitHub's ubuntu runners ship 3.12.
"""

from __future__ import annotations

import json
import os
import re
import sys
import tomllib
import urllib.request

UPSTREAM = "be5invis/Iosevka"
PLAN_FILE = "private-build-plans.toml"
SAFE_PLAN_NAME = re.compile(r"[A-Za-z0-9._-]+")


def api(path: str):
    """GET a GitHub API path and parse the JSON body."""
    request = urllib.request.Request(
        f"https://api.github.com{path}",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {os.environ['GITHUB_TOKEN']}",
            "User-Agent": "iosevka-heiskr",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.load(response)


def upstream_release() -> tuple[str, str]:
    """Return the latest upstream release tag and the commit it points at."""
    tag = api(f"/repos/{UPSTREAM}/releases/latest")["tag_name"]
    # Pin to the commit rather than the tag. A retag upstream, or a new release
    # landing mid-build, would otherwise change what we actually compile.
    sha = api(f"/repos/{UPSTREAM}/commits/{tag}")["sha"]
    return tag, sha


def last_built(repo: str) -> str:
    """Return the tag of our most recent real release, or "none" if there is none."""
    # Listing rather than /releases/latest avoids a 404 on the very first run.
    # per_page stays small: large pages time out with HTTP 504 on repos that
    # have long release histories.
    releases = api(f"/repos/{repo}/releases?per_page=10")
    return next(
        (r["tag_name"] for r in releases if not r["draft"] and not r["prerelease"]),
        "none",
    )


def build_plans() -> list[str]:
    """Read plan names from the TOML so adding a family needs no workflow edit."""
    with open(PLAN_FILE, "rb") as handle:
        plans = sorted(tomllib.load(handle).get("buildPlans", {}))
    if not plans:
        sys.exit(f"{PLAN_FILE} defines no [buildPlans.*] sections")
    unsafe = [name for name in plans if not SAFE_PLAN_NAME.fullmatch(name)]
    if unsafe:
        sys.exit(f"{PLAN_FILE} has plan names unsafe as shell arguments: {unsafe}")
    return plans


def should_build(tag: str, last: str, event: str, force: bool) -> bool:
    if tag != last:
        return True
    if event == "push":
        return True
    return event == "workflow_dispatch" and force


def write_kv(path_var: str, text: str) -> None:
    with open(os.environ[path_var], "a") as handle:
        handle.write(text)


def main() -> None:
    tag, sha = upstream_release()
    last = last_built(os.environ["GITHUB_REPOSITORY"])
    plans = build_plans()
    build = should_build(
        tag,
        last,
        os.environ["GITHUB_EVENT_NAME"],
        os.environ.get("FORCE") == "true",
    )

    print(f"upstream:   {tag} ({sha[:7]})")
    print(f"last built: {last}")
    print(f"plans:      {plans}")
    print(f"build:      {build}")

    write_kv(
        "GITHUB_OUTPUT",
        f"upstream={UPSTREAM}\n"
        f"tag={tag}\n"
        f"sha={sha}\n"
        f"version={tag.removeprefix('v')}\n"
        f"plans={json.dumps(plans)}\n"
        f"build={str(build).lower()}\n",
    )
    write_kv(
        "GITHUB_STEP_SUMMARY",
        f"### Building Iosevka `{tag}`\n"
        if build
        else f"### Already up to date at `{last}`\n",
    )


if __name__ == "__main__":
    main()
