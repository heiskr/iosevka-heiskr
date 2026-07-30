# Iosevka Heiskr

> [!NOTE]
> GitHub Copilot created this repository, with review from @heiskr. The font customization choices are human.

My custom [Iosevka](https://github.com/be5invis/Iosevka) build, rebuilt automatically whenever upstream ships a new release.

Download under [releases](https://github.com/heiskr/iosevka-heiskr/releases).

## What gets built

`private-build-plans.toml` defines two families, both humanist, single-storey, serifless, at a single Semi-Expanded (548 unit) width:

| Family | Spacing | For |
|---|---|---|
| `Iosevka Heiskr` | `normal` | Text editors |
| `Iosevka Heiskr Term` | `term` | Terminals |

Nine weights x upright/italic = 18 TTFs per family.

The two plans share `widths`, `variants`, `weights`, and `slopes` via `inherits`, so they can't drift apart.

## Install

```sh
./install.sh
```

Downloads the latest release and copies the TTFs into `~/Library/Fonts`. Same end state as installing each file through Font Book, without the duplicate-resolution dialogs on every upgrade. Restart your apps afterward.

## How the automation works

`.github/workflows/build.yml` runs weekly and on any change to the build plan.

1. **check**: [`.github/scripts/check_upstream.py`](.github/scripts/check_upstream.py) reads upstream's latest release tag, resolves it to a commit SHA, compares the tag against this repo's most recent release, and parses the TOML for build plan names. Adding a family needs no workflow edit.
2. **build**: one runner per family, in parallel. Checks out upstream at the pinned **SHA** (not the tag, so a retag or a mid-build release can't change what compiles), copies the build plan in, runs `npm run build -- ttf::<Plan> --jCmd=2`, and zips the TTFs.
3. **release**: publishes a release tagged with the upstream version, e.g. `v34.8.0`, with one zip per family.

## Changing the fonts

Edit `private-build-plans.toml` and push to `main`. That triggers a rebuild and republishes the release for the current upstream version. Then run `./install.sh`.

Variant names like `single-storey-serifless` are listed in upstream's [character variants doc](https://github.com/be5invis/Iosevka/blob/main/doc/character-variants.md). Build plan options are in [`doc/custom-build.md`](https://github.com/be5invis/Iosevka/blob/main/doc/custom-build.md).
